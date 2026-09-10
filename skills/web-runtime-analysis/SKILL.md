---
name: web-runtime-analysis
license: MIT
description: 面向没有源码仓库权限的测试人员，分析网站 DOM、交付的 JS/CSS、公开 source map、请求和浏览器状态，发现功能、接口、交互分支与候选测试点。用户要分析网站实现线索、梳理接口或提前判断测哪里时使用；按既定用例执行验收走 app-test。
---

# Web 运行时侦察

目标是给测试设计提供可追溯的实现地图。输入网站或用户提供的浏览器产物，不要求源码、数据库或服务器权限。

读取 [inspection.md](references/inspection.md)。需要登记运行证据时读取 [共享执行契约](../_test-run-shared/references/execution-contract.md)，普通静态侦察无需创建验收 scope。

1. 明确站点/页面、账号角色、环境和允许交互范围。列出现有浏览器、Network、bundle、source map 等能力，未知能力不当作不存在。
2. 从入口页面及实际资源依赖建立页面、路由、DOM/表单、脚本/CSS清单；按当前风险选择深挖模块，记录未加载、不可访问和采样范围。
3. 分析 JS 的路由、接口字符串、请求封装、表单校验、条件分支、错误处理、存储和实时消息；用运行时观察验证有价值的候选。
4. 每条发现标记 static-candidate/runtime-observed/interaction-confirmed，以及文件摘要/URL、locator、时间、角色和限制。
5. 输出 inspection-report.md：功能地图、接口目录、交互/状态分支、候选测试点、风险、未知项与最小验证建议。JSON 可按 inspection.md 的 finding 结构提供。

已有本地导出的 HTML/JS/CSS 可先运行 `python scripts/inspect_assets.py --root <exports> --asset index.html --asset main.js --output <new-report.json>`。脚本只提供静态候选清单，不访问网络、不自动下载引用，不替代运行时观察。

静态代码出现路径不证明接口有效；请求发出不证明业务成功；压缩变量名和框架特征不构成根因。没有执行的分支不能声明已覆盖。发现作为 TestSpec 的 reference 输入，产品规则冲突交由产品确认，不自行改 canonical requirements。
