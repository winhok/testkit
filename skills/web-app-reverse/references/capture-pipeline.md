# 无仓库 Web 分析流水线

按输入选择一路：已有浏览器会话 → 当前页面采集；已有 HAR → 离线导出；只有 HTML/JS/CSS 目录 → 本地规范化。三路生成同一份私有 manifest，再解析 AST、关联记录并生成六层测试地图。工具均为 TestKit 独立实现，无 REA 运行依赖。

## 准备与依赖

在 TestKit 根目录运行，Node.js 20+：

```bash
npm ci --prefix skills/web-app-reverse --ignore-scripts
```

仅安装锁定的 Babel parser 及其依赖；[Babel parser 官方 API](https://babeljs.io/docs/babel-parser)用于解析 JS/JSX/TypeScript。运行源码只读解析，不 import 或 eval 被测脚本。

把本次输入和产物放在已忽略的 `web-inspections/<run>/`，或另选本地私有目录。manifest 为精确资源解析保留原 URL，脚本正文也可能含敏感值；文件默认权限为目录 0700/文件 0600，Windows 使用当前账号的目录 ACL。报告使用 origin_label 和去查询参数的路径；共享前复核路径、状态 key 等业务标识。

## 已有浏览器会话

先按 app-test 的会话流程选择当前页面。ego-lite 的本轮 `ego-browser nodejs` 脚本导入 `scripts/capture_page.mjs` 的绝对 file URL：

```javascript
const {capturePage} = await import('file:///absolute/TestKit/skills/web-app-reverse/scripts/capture_page.mjs');
const capture = await capturePage(page, ['https://example.invalid']);
const fs = await import('node:fs/promises');
await fs.writeFile('/absolute/private/capture.json', JSON.stringify(capture), {flag:'wx', mode:0o600});
```

沿用已绑定的 task/page，不创建另一个登录环境。采集器读取表单结构（省略值和正文）、内联脚本/CSS，并通过该 Page 的 CDP Debugger 取得已保留的同范围脚本正文；结束后释放 Debugger；采集期间 URL 变化即停止，重新观察当前页面后再采集。它会消费本轮 page.events，采集期间避免在同一 Page 并行使用另一个事件消费者。范围外脚本跳过；最多保留 100 个 Debugger 脚本、合计 8 MiB，单个资源 2 MiB，内联脚本和样式正文另设合计 8 MiB 预算，超限记录为缺失正文。CSS 外链保留为引用，可用用户导出的 HAR 补充正文。

`capturePage(page, origins, {includeScriptSources:false})` 仅采集 DOM 投影、内联资源与外链引用。其他宿主根据其当前文档采集同样字段，或直接使用其 HAR 导出。

页面采集输入：`{schema_version:1, kind:"web-page-capture", resources:[{url,mimeType,text?,encoding?}], coverage:{...}}`。缺失 text 保留为 unavailable；base64 正文写 `encoding:"base64"`。

## HAR 或采集 JSON 导出

```bash
python skills/web-app-reverse/scripts/export_capture.py \
  --input web-inspections/run/session.har \
  --site-origin https://example.invalid \
  --output-dir web-inspections/run/export
```

--input 也接受上一节 capture.json。默认只接收选定 origin，第三方资源须以 `--allow-origin https://assets.example.invalid` 显式纳入。输入最多 32 MiB/500 条记录，资源正文单个 2 MiB；HAR 保留 method/status/原 entry 定位，省略认证头和请求/业务响应内容。静态脚本及 HTML/CSS/source map 正文存入独立资源文件。

输出目录必须不存在。导出保留采集文本的 UTF-8 字节（base64 正文按捕获编码还原）、SHA-256、字节数、来源定位和 collection 类型；已有目录保留。缺失正文、非成功响应或超限项目保留具体 reason，不删除覆盖缺口。

## 已有静态目录

```bash
python skills/web-app-reverse/scripts/export_local.py \
  --root exports --site-origin https://example.invalid \
  --base-path / --output-dir web-inspections/run/export
```

--base-path 指定导出目录在站点中的实际目录前缀，例如目录里的 main.js 对应 /assets/main.js 时用 `/assets/`。按用户提供的布局建立映射，不猜原站点路径。读取最多 200 个本地文件并检查根目录边界；保持旧 `inspect_assets.py` 作为轻量正则盘点入口。

## AST 与六层地图

```bash
python skills/web-app-reverse/scripts/build_test_map.py \
  --export-dir web-inspections/run/export \
  --site-origin https://example.invalid \
  --output web-inspections/run/inspection-map.json
```

先校验文件摘要、字节数和目录边界，再用 Babel AST 解析路由配置、JSX Route、React basename/Vue history base、静态 const 字面量、导航目标、fetch/axios、静态/动态 import、Storage 访问。遇到重名、参数遮蔽、动态表达式、展开属性、可变路由对象或解析失败，保留 unknown。相对 fetch 需显式 `--document-url https://example.invalid/app/`；相对 import 则按脚本 URL 解析。仅按已发现 sourceMappingURL 关联捕获到的 map，原始 sourcesContent 的深度分析留给后续按需分析。

地图字段沿用 inspection.md：scope、coverage、maps、findings、unknowns。maps.behaviors 保存带来源的资源/路由/接口/状态关系；每个来源包含 source_id、SHA-256、行列。每次 source occurrence 独立保留，重复 URL 或版本进入 ambiguous，不静默选一个。

接口按 origin、原始 path 摘要、method 与 HAR 历史记录关联，避免脱敏后的相同显示路径被合并。historical-match 表示接口签名相符；页面动作与请求的因果关系仍由对应运行 trace 确认。同文件出现的路由和接口通过来源图关联，不能直接拼成已验证业务流程。

每条 test_candidate 携带触发线索、前置条件、角色、测试数据、动作、oracle、授权范围和自动化建议。由 agent 根据来源和页面观察补齐具体控件/业务规则，生成 inspection-report.md，交 TestSpec；确认后的 UI 用例由 Midscene 执行。静态线索、历史请求和本次操作结果分别记录。

## 设计来源

方法参考 REA 的资源导出、路由 inventory、模块图和静态/运行关联设计（审阅版本 `269630f4e1c93e45e5d133fde370736133865a3c`），[参考文档](https://github.com/morluto/rea/blob/269630f4e1c93e45e5d133fde370736133865a3c/docs/website-script-export.md)。本流水线按 TestKit 的数据契约独立编写；没有复制 REA 实现或引入其安装、MCP、原生分析引擎。
