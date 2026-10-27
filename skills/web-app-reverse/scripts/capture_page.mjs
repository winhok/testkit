/** Capture selected page structure, inline resources and retained scoped script sources. */
export async function capturePage(page, allowedOrigins, {includeScriptSources = true} = {}) {
  const url = new URL(await page.url());
  if (!Array.isArray(allowedOrigins) || !allowedOrigins.includes(url.origin)) throw new Error('capture-target-unconfirmed');
  const capture = await page.evaluate(({allowedOrigins}) => {
    if (!allowedOrigins.includes(location.origin)) throw new Error('capture-target-changed');
    const resources = [], maximum = 2 * 1024 * 1024;
    const origin = location.origin;
    const bytes = text => new TextEncoder().encode(text).length;
    // Construct structural HTML rather than dumping live values or page text.
    const skeleton = document.createElement('main');
    let truncated = false, retainedBytes = 0;
    const add = resource => {
      if (resources.length >= 499) {truncated = true; return;}
      if (resource.text != null) {
        const size = bytes(resource.text);
        if (size > maximum || retainedBytes + size > 8 * 1024 * 1024) {
          delete resource.text;
          resource.reason = size > maximum ? 'body-size-limit' : 'body-budget';
          truncated = true;
        } else retainedBytes += size;
      }
      resources.push(resource);
    };
    for (const element of Array.from(document.querySelectorAll('form,input,button,select,textarea')).slice(0, 500)) {
      const copy = document.createElement(element.tagName.toLowerCase());
      for (const attr of ['type', 'required', 'minlength', 'maxlength', 'min', 'max', 'step', 'multiple', 'disabled']) {
        if (element.hasAttribute(attr)) {
          const value = element.getAttribute(attr);
          if (value.length > 256) {truncated = true; continue;}
          copy.setAttribute(attr, value);
        }
      }
      skeleton.append(copy);
    }
    if (document.querySelectorAll('form,input,button,select,textarea').length > 500) truncated = true;
    for (const script of document.scripts) {
      if (script.src) {
        const target = new URL(script.src, document.baseURI);
        if (allowedOrigins.includes(target.origin)) add({url: target.href, mimeType: 'text/javascript', reason: 'external-reference-only'});
      } else if (!script.type || ['module','text/javascript','application/javascript'].includes(script.type)) {
        add({url: new URL(`/__inline__/${resources.length}.js`, origin).href, mimeType: 'text/javascript', text: script.textContent});
      }
    }
    for (const style of document.querySelectorAll('style')) {
      add({url: new URL(`/__inline__/${resources.length}.css`, origin).href, mimeType: 'text/css', text: style.textContent});
    }
    for (const link of document.querySelectorAll('link[rel="stylesheet"]')) {
      const target = new URL(link.href, document.baseURI);
      if (allowedOrigins.includes(target.origin)) add({url: target.href, mimeType: 'text/css', reason: 'external-reference-only'});
    }
    resources.push({url: location.href, mimeType: 'text/html', text: skeleton.outerHTML});
    return {schema_version: 1, kind: 'web-page-capture', resources,
      coverage: {document: 'structural-projection', external_bodies: 'not-collected', truncated}};
  }, {allowedOrigins});
  if (includeScriptSources) {
    const retained = await captureScriptSources(page, allowedOrigins, {expectedUrl: url.href});
    const urls = new Set(retained.resources.map(resource => resource.url));
    capture.resources = [...capture.resources.filter(resource => !urls.has(resource.url)), ...retained.resources];
    capture.coverage.scripts = retained.coverage;
    if (capture.resources.length > 500) {
      capture.resources = capture.resources.slice(0, 500);
      capture.coverage.truncated = true;
    }
  }
  if (new URL(await page.url()).href !== url.href) throw new Error('capture-target-changed');
  return capture;
}

export async function captureScriptSources(page, allowedOrigins, {expectedUrl} = {}) {
  const initial = new URL(await page.url());
  if (expectedUrl && initial.href !== expectedUrl) throw new Error('capture-target-changed');
  if (!allowedOrigins.includes(initial.origin)) throw new Error('capture-target-unconfirmed');
  const resources = [], gaps = [];
  let total = 0, enabled = false;
  try {
    await page.cdp('Debugger.enable');
    enabled = true;
    const events = await page.events();
    const scripts = events.filter(event => event.method === 'Debugger.scriptParsed');
    for (const event of scripts) {
      const {url, scriptId} = event.params;
      let origin;
      try {origin = new URL(url).origin;} catch {continue;}
      if (!allowedOrigins.includes(origin)) continue;
      if (resources.length >= 100 || total >= 8 * 1024 * 1024) {gaps.push('script-budget'); break;}
      if (new URL(await page.url()).href !== initial.href) throw new Error('capture-target-changed');
      try {
        const {scriptSource} = await page.cdp('Debugger.getScriptSource', {scriptId}, {timeout: 5000});
        if (typeof scriptSource !== 'string') throw new Error('missing-script-source');
        const size = new TextEncoder().encode(scriptSource).length;
        if (size > 2 * 1024 * 1024 || total + size > 8 * 1024 * 1024) {gaps.push('script-size-limit'); continue;}
        total += size;
        resources.push({url, mimeType: 'text/javascript', text: scriptSource, collection: 'debugger-source'});
      } catch {gaps.push('script-source-unavailable');}
    }
    if (new URL(await page.url()).href !== initial.href) throw new Error('capture-target-changed');
    return {resources, coverage: {retained: resources.length, gaps, external_bodies: 'retained-debugger-sources'}};
  } finally {
    if (enabled) await page.cdp('Debugger.disable');
  }
}
