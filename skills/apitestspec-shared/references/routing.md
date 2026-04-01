# API TestSpec 套件路由表

按"最早缺失产物优先"路由：

| 阶段 | 条件 | 使用 skill |
|------|------|-----------|
| 1 | 没有文档，只有源码 | `apitestspec-surface-scan` |
| 2 | 有接口文档，但没有原生 spec | `apitestspec-composer` |
| 3 | 有 spec，但缺登录流、环境变量或默认 headers | `apitestspec-flow-configurator` |
| 4 | 有 spec 且执行条件已具备，要运行 | `apitestspec-scenario-runner` |
| 5 | 已有结果产物，只想看报告 | `apitestspec-result-viewer` |

如果用户一次提多个阶段（例如"帮我根据文档生成 case 并跑一下"），按当前最早缺失阶段处理，完成后明确说明下一步交给谁。
