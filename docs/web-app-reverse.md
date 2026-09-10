# 逆向梳理无源码 Web 应用

`web-app-reverse` 面向拿不到代码仓库的测试场景，从网站已交付的 HTML、JavaScript/CSS、公开 source map、HAR、浏览器状态和运行记录中建立可追溯的实现地图，为 TestSpec 分析、测试点和用例设计提供证据。

## 适合什么任务

- 无源码或无仓库时梳理网站页面、路由和功能边界。
- 分析 bundle、chunk、worker、source map 和动态加载关系。
- 盘点接口、实时通道、状态、角色、功能开关、校验和错误分支。
- 发现隐藏测试面、覆盖缺口和需要产品确认的实现线索。

已有源码时应使用 `testspec-code-calibrate`；按确认用例执行验收时使用 [`app-test`](app-test.md)。本能力不用于主动安全探测。

## 输入与产出

输入可以是站点入口、用户导出的静态资源目录、HAR、Network/trace 记录或浏览器状态。开始前需要明确目标 origin、环境、角色、允许的只读导航和禁止的业务动作。

默认输出 `inspection-report.md`，包含：

- 已扫描、跳过、缺失和仅被引用资源的覆盖账本。
- 页面/路由、资源、接口、状态、角色与错误分支六层地图。
- 带来源定位和证据等级的发现。
- 候选测试点、风险优先级、未知项和最小验证建议。

需要结构化结果时输出 `inspection-map.json`。已有完整导出目录可以先生成中间 inventory：

```bash
python skills/web-app-reverse/scripts/inspect_assets.py \
  --root exports \
  --discover-local \
  --site-origin https://test.example.invalid \
  --output asset-inventory.json
```

## 证据边界

- 资源中存在路径、组件或分支，不等于线上功能可用。
- 分母未知时不报告覆盖百分比。
- 逆向阶段不提交表单、不写业务数据、不重放写请求、不做故障注入。
- 同路径不同 origin 不合并；source map 与 bundle 版本无法关联时明确标记未知。
- 发现作为 TestSpec 的 reference 输入，不伪装成代码校准产物，也不覆盖产品需求。

完整执行契约见 [`web-app-reverse`](../skills/web-app-reverse/SKILL.md)。发现进入用例设计的方式见 [TestSpec 指南](testspec.md#使用无仓库-web-实现证据)。
