/** Parse inert source bytes; no module loading, evaluation, browser or network calls. */
import { parse } from '@babel/parser';
import { pathToFileURL } from 'node:url';

export function analyzeSource(text) {
  const result = {routes: [], requests: [], imports: [], states: [], unknowns: []};
  const unknown = (reason, node) => result.unknowns.push({reason, line: node?.loc?.start.line ?? 1});
  let ast;
  try {
    ast = parse(text, {sourceType: 'unambiguous', plugins: ['jsx', 'typescript'], attachComment: false});
  } catch {
    unknown('parse-failed');
    return result;
  }
  const bindings = new Map(), blocked = new Set();
  const children = node => Object.entries(node).filter(([key]) => !['loc', 'comments', 'tokens', 'errors'].includes(key))
    .flatMap(([, value]) => Array.isArray(value) ? value : [value]).filter(value => value && typeof value.type === 'string');
  const walk = (node, visit) => {
    const pending = [node];
    while (pending.length) {
      const current = pending.pop();
      visit(current);
      pending.push(...children(current).reverse());
    }
  };
  const rootName = node => {
    while (node?.type === 'MemberExpression' || node?.type === 'OptionalMemberExpression') node = node.object;
    return node?.type === 'Identifier' ? node.name : null;
  };
  const declare = (name, init) => {
    if (bindings.has(name)) blocked.add(name);
    bindings.set(name, init);
  };
  // Name collisions and writes are unresolved rather than guessed across lexical scopes.
  walk(ast, node => {
    if (node.type === 'VariableDeclaration') {
      for (const declaration of node.declarations) {
        if (declaration.id.type === 'Identifier') declare(declaration.id.name, node.kind === 'const' ? declaration.init : null);
      }
    }
    if (/Function/.test(node.type) || node.type === 'ArrowFunctionExpression' || node.type === 'CatchClause') {
      for (const param of [...(node.params ?? []), ...(node.param ? [node.param] : [])]) {
        walk(param, item => {if (item.type === 'Identifier') blocked.add(item.name);});
      }
    }
    if (node.type === 'AssignmentExpression' || node.type === 'UpdateExpression') {
      const name = rootName(node.left ?? node.argument);
      if (name) blocked.add(name);
    }
    if (node.type === 'CallExpression' && node.callee.type === 'MemberExpression' &&
        ['push', 'pop', 'shift', 'unshift', 'splice', 'assign', 'defineProperty'].includes(node.callee.property.name)) {
      const name = rootName(node.callee.object);
      if (name) blocked.add(name);
      for (const arg of node.arguments) if (arg.type === 'Identifier') blocked.add(arg.name);
    }
  });
  let changed = true;
  while (changed) {
    changed = false;
    for (const [name, init] of bindings) {
      if (init?.type === 'Identifier' && (blocked.has(name) || blocked.has(init.name))) {
        for (const alias of [name, init.name]) if (!blocked.has(alias)) {blocked.add(alias); changed = true;}
      }
    }
  }
  const unwrap = (node, seen = new Set()) => {
    if (!node) return null;
    if (['TSAsExpression', 'TSSatisfiesExpression', 'TSNonNullExpression', 'ParenthesizedExpression'].includes(node.type)) return unwrap(node.expression, seen);
    if (node.type !== 'Identifier') return node;
    if (blocked.has(node.name) || seen.has(node.name) || seen.size > 30) return null;
    return unwrap(bindings.get(node.name), new Set([...seen, node.name]));
  };
  const literal = (input, depth = 0) => {
    if (depth > 30) return null;
    const node = unwrap(input);
    if (!node) return null;
    if (node.type === 'StringLiteral' || node.type === 'BooleanLiteral') return node.value;
    if (node.type === 'BinaryExpression' && node.operator === '+') {
      const a = literal(node.left, depth + 1), b = literal(node.right, depth + 1);
      return typeof a === 'string' && typeof b === 'string' ? a + b : null;
    }
    if (node.type === 'TemplateLiteral') {
      let value = node.quasis[0].value.cooked;
      for (let i = 0; i < node.expressions.length; i++) {
        const part = literal(node.expressions[i], depth + 1);
        if (typeof part !== 'string') return null;
        value += part + node.quasis[i + 1].value.cooked;
      }
      return value;
    }
    return null;
  };
  const property = (node, key) => {
    node = unwrap(node);
    if (node?.type !== 'ObjectExpression' || node.properties.some(item => item.type === 'SpreadElement')) return null;
    const matches = node.properties.filter(item => item.type === 'ObjectProperty' && !item.computed && (item.key.name ?? item.key.value) === key);
    return matches.length === 1 ? matches[0].value : null;
  };
  const locate = node => ({line: node.loc.start.line, column: node.loc.start.column});
  const path = (value, parent = '') => value.startsWith('/') ? value : `${parent.replace(/\/$/, '')}/${value}`;
  function routes(input, parent = '', ancestors = new Set()) {
    const node = unwrap(input);
    if (!node || ancestors.has(node) || ancestors.size > 30) {unknown('unresolved-route-configuration', input); return;}
    const next = new Set([...ancestors, node]);
    if (node.type === 'ArrayExpression') {
      for (const element of node.elements) if (element) routes(element, parent, next);
      return;
    }
    if (node.type !== 'ObjectExpression' || node.properties.some(item => item.type === 'SpreadElement')) {
      unknown('unresolved-route-object', node); return;
    }
    const pathNode = property(node, 'path'), indexNode = property(node, 'index');
    const value = literal(pathNode);
    if (pathNode && typeof value !== 'string') {unknown('computed-route-path', pathNode); return;}
    const resolved = typeof value === 'string' ? path(value, parent) : parent;
    if (typeof value === 'string' || literal(indexNode) === true) result.routes.push({path: resolved || '/', mechanism: 'router-configuration', ...locate(node)});
    const nested = property(node, 'children');
    if (nested) routes(nested, resolved, next);
  }
  function rootedRoutes(config, baseNode) {
    const base = baseNode ? literal(baseNode) : '';
    if (typeof base !== 'string' || (base && (!base.startsWith('/') || base.startsWith('//')))) {
      unknown('unresolved-router-base', baseNode); return;
    }
    const start = result.routes.length;
    routes(config);
    if (base && base !== '/') {
      for (const row of result.routes.slice(start)) row.path = base.replace(/\/$/, '') + row.path;
    }
  }
  function jsxRoutes(node, parent = '') {
    const opening = node.openingElement;
    if (opening.name.type !== 'JSXIdentifier' || opening.name.name !== 'Route') return;
    if (opening.attributes.some(item => item.type === 'JSXSpreadAttribute')) {unknown('jsx-route-spread', node); return;}
    const attr = opening.attributes.find(item => item.name?.name === 'path');
    const value = attr?.value?.type === 'JSXExpressionContainer' ? literal(attr.value.expression) : attr?.value?.value;
    if (attr && typeof value !== 'string') {unknown('computed-route-path', node); return;}
    const resolved = typeof value === 'string' ? path(value, parent) : parent;
    if (typeof value === 'string' || opening.attributes.some(item => item.name?.name === 'index')) result.routes.push({path: resolved || '/', mechanism: 'jsx-route', ...locate(node)});
    for (const child of node.children) if (child.type === 'JSXElement') jsxRoutes(child, resolved);
  }
  const jsxNested = new Set();
  walk(ast, node => {
    if (node.type === 'JSXElement' && node.openingElement.name.name === 'Route') {
      for (const child of node.children) if (child.type === 'JSXElement' && child.openingElement.name.name === 'Route') jsxNested.add(child);
    }
  });
  walk(ast, node => {
    if (node.type === 'JSXElement' && !jsxNested.has(node)) jsxRoutes(node);
    if ((node.type === 'ImportDeclaration' || node.type === 'ExportNamedDeclaration' || node.type === 'ExportAllDeclaration') && node.source && node.importKind !== 'type' && node.exportKind !== 'type') {
      result.imports.push({value: node.source.value, mechanism: 'static-import', ...locate(node)});
    }
    if (node.type === 'ImportExpression') {
      const value = literal(node.source);
      if (typeof value === 'string') result.imports.push({value, mechanism: 'dynamic-import', ...locate(node)});
      else unknown('computed-import', node);
    }
    if (!['CallExpression', 'NewExpression'].includes(node.type)) return;
    const callee = node.callee;
    const name = callee.type === 'Identifier' ? callee.name : null;
    const member = callee.type === 'MemberExpression' && !callee.computed ? callee.property.name : null;
    const object = callee.type === 'MemberExpression' && callee.object.type === 'Identifier' ? callee.object.name : null;
    if (['createBrowserRouter', 'createHashRouter', 'useRoutes'].includes(name)) {
      if (name === 'useRoutes') rootedRoutes(node.arguments[0], null);
      else if (node.arguments[1] && (unwrap(node.arguments[1])?.type !== 'ObjectExpression' || unwrap(node.arguments[1]).properties.some(item => item.type === 'SpreadElement'))) unknown('unresolved-router-options', node);
      else rootedRoutes(node.arguments[0], property(node.arguments[1], 'basename'));
    }
    if (['createRouter', 'Router'].includes(name)) {
      const config = property(node.arguments[0], 'routes');
      const history = unwrap(property(node.arguments[0], 'history'));
      if (history && (history.type !== 'CallExpression' || !['createWebHistory', 'createWebHashHistory', 'createMemoryHistory'].includes(history.callee.name))) unknown('unresolved-router-base', history);
      else if (config) rootedRoutes(config, history?.arguments[0]);
      else unknown('unresolved-router-options', node);
    }
    if (callee.type === 'Import') {
      const value = literal(node.arguments[0]);
      if (typeof value === 'string') result.imports.push({value, mechanism: 'dynamic-import', ...locate(node)});
      else unknown('computed-import', node);
    }
    if (name === 'navigate' || (object === 'router' && ['push', 'replace'].includes(member))) {
      const value = literal(node.arguments[0]);
      if (typeof value === 'string' && value.startsWith('/')) result.routes.push({path: value, mechanism: 'navigation-target', ...locate(node)});
      else unknown('computed-navigation', node);
    }
    if (name === 'fetch' || (object === 'axios' && ['get','post','put','patch','delete','head','options'].includes(member))) {
      const value = literal(node.arguments[0]);
      if (typeof value !== 'string') {unknown('computed-request-target', node); return;}
      const options = unwrap(node.arguments[1]);
      const methodNode = property(options, 'method');
      let method = object === 'axios' ? member.toUpperCase() : node.arguments.length < 2 ? 'GET' : null;
      if (name === 'fetch' && options?.type === 'ObjectExpression' && !options.properties.some(item => item.type === 'SpreadElement')) {
        method = methodNode ? literal(methodNode) : 'GET';
      }
      result.requests.push({value, method: typeof method === 'string' ? method.toUpperCase() : null, ...locate(node)});
    }
    if (['localStorage', 'sessionStorage'].includes(object) && ['getItem', 'setItem', 'removeItem'].includes(member)) {
      const key = literal(node.arguments[0]);
      if (typeof key === 'string') result.states.push({store: object, key, operation: member, ...locate(node)});
    }
  });
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    let text = '';
    for await (const chunk of process.stdin) {
      text += chunk;
      if (Buffer.byteLength(text) > 16 * 1024 * 1024) throw new Error('input limit');
    }
    const sources = JSON.parse(text);
    if (!Array.isArray(sources) || sources.length > 500) throw new Error('invalid input');
    const output = sources.map(source => ({id: source.id, ...analyzeSource(source.text)}));
    const encoded = JSON.stringify(output);
    if (Buffer.byteLength(encoded) > 16 * 1024 * 1024) throw new Error('result limit');
    console.log(encoded);
  } catch {
    console.error('AST analysis failed: check input, parser installation and resource limits');
    process.exitCode = 2;
  }
}
