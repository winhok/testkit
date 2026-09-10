# 执行与证据契约 v1

适用于完整 TestKit 插件。工具位于 `scripts/test_run.py`，只管理本地记录；执行操作由当前宿主可用的工具和现有 API runner 完成。保留 TestSpec context v2、用例 schema v2、API result v1，各自版本独立。

## 任务与能力

简单局部检查可使用 mode=local 和 local-check 来源，不必创建完整 TestSpec。正式验收 mode=acceptance 需要当前 requirements、用例和策略快照；从确认的验收范围列出所有检查，包括无法执行的检查。不能从成功结果反推计划全集。TestSpec 产物先通过现有 context chain/review 验证器；publish 不是运行前置条件。

复用 strategy 中的环境、oracle 和能力需求，执行前刷新实际工具/目标可访问性、账号角色与操作授权。每项 capability 独立记录 availability=unknown/available/limited/unavailable，authorization=unknown/granted/denied，actions（read/write 数组）、target_id、scope、basis、checked_at。工具存在不等于目标可访问，也不等于已授权。受限能力只用于其允许的动作；无数据库权限可采用需求允许的外部 oracle。缺失能力只阻塞依赖检查。

build 必须是可核实的部署标识、构建号或包摘要，不要求源码或 commit；不知道则先记录局部观察，不编造正式验收版本。环境与权限是独立维度，public 不是生产写入许可。

## 目录与 CLI

所有 evidence/source 路径相对于显式 --root，必须位于该目录内。使用合成或脱敏副本；不保存密码、Token、Cookie、业务正文、私有源码。运行目录使用新的 test-runs/<run-id>；工具拒绝覆盖已有文件。

```sh
python <skills>/_test-run-shared/scripts/test_run.py freeze --root <project> --run-dir <project>/test-runs/<run-id> --input <scope-draft.json>
# 执行后登记，每次重试一个新 attempt ID
python <skills>/_test-run-shared/scripts/test_run.py record --root <project> --run-dir <run-dir> --input <attempt-draft.json>
python <skills>/_test-run-shared/scripts/test_run.py evaluate --root <project> --run-dir <run-dir> --current-targets <targets.json> --output <new-report.json>
```

evaluate 不执行测试。退出码 0=当前范围通过，1=合法但未通过，2=记录无效。report-only 使用已有验收 JSON 渲染，不重跑、不重新登记或改写历史状态。current-targets 是此次复核取得的 targets 数组；保存其外部出处。无当前身份验证时不能沿用旧 build 宣称新验收。

## Scope

scope-draft 的完整示例见 examples/synthetic-web/scope-draft.json（仓库根目录）。freeze 自动补充 sources 的 SHA-256 和 frozen_at。
必需字段：
- run_id、mode(local/acceptance)、sources[{id,kind,path}]。
- sources.kind=requirements/cases/strategy/local-check/runner-definition/dataset。
- targets[{id,platform(api/web/android/ios),build,environment}]。
- capabilities[{id,target_id,availability,authorization,actions,scope,basis,checked_at}]。
- checks[{id,case_id,source_id,requirement_refs,oracle,target_id,required,effect,cleanup,depends_on,capability_ids,binding}]。
- 正式验收还需 source_revision，且 source 中包含 requirements 和 cases。
- binding={runner,selector}；API binding 额外关联 definition_source_id。observation selector 是 JSON pointer；Arazzo selector 是 workflow_id，数据驱动必须附 dataset_index；pytest/Schemathesis selector=suite。

一个 check 对应一个 oracle、目标与环境/角色组合。用例可有多个 checks；mandatory 全部满足才证明该用例。稳定 case ID 加内容摘要绑定，不能只比较 source_revision。optional 排除必须在冻结前有范围依据，报告始终列出。

## Attempt 与原始结果

attempt-draft：
```json
{
  "id":"attempt-1","check_id":"check-1",
  "target":{"id":"web","platform":"web","build":"synthetic-build-1","environment":"test"},
  "started_at":"2026-01-01T01:00:00Z","finished_at":"2026-01-01T01:00:01Z",
  "status":"passed","cleanup_status":"not-required",
  "evidence":[{"path":"evidence/observation.json","collector":"browser-tool","collected_at":"2026-01-01T01:00:01Z"}]
}
```

时间必须是真实采集时间，晚于 freeze；示例时间不可直接冒充执行。record 补 scope_sha256 和证据摘要。target 必须精确匹配冻结目标，execution 工具同时保存能核对目标的证据。第一份 evidence 为 binding 指向的 JSON，后续可以是脱敏截图、录屏等 supporting artifacts。

observation JSON 的 selector 指向对象：
```json
{"status":"passed","actual":"订单状态显示已确认","basis":"浏览器断言结果和截图定位","method":"tool"}
```
method=tool/human；人工记录明确核验者和依据，不能伪装成 runner 原生断言。不能单凭生成此 JSON 证明发生了执行。

runner 原始状态保持不变。Arazzo 按 workflow/dataset 唯一绑定，pytest 现有 JUnit 名称无法可靠逐条对应 nodeid，因此第一版只支持完整 invocation/suite 映射，selected_nodeids 必须完全一致。Schemathesis envelope 只支持 suite 级契约结论，不能映射成任意业务断言通过。若需精确业务断言，使用 Arazzo 或真实 observation。定义和数据也必须冻结，执行前验证文件未变；工具能力授权不由这些记录授予。

## Journey / Fixture / 恢复

跨端旅程以 check.depends_on 建立有向无环图。由任务执行者按依赖调度现有工具，不由本 CLI 执行任意命令。明确共享业务实体、账号角色、必要变量传递、数据隔离、初始化和清理；secret 仅存在进程/工具会话，不进入 JSON。跨端先写步骤计划，再执行。等待异步状态必须有最大等待和可观察完成条件，不能用固定 sleep 冒充完成。

中断后读取 scope 和所有 attempts，核对目标、会话、数据状态及已有副作用，继续未完成步骤；不能自动重放已产生写入的动作。新 attempt 保留历史。failed 后 passed 标记 inconclusive，需要新运行明确复核不稳定因素。cleanup required 时失败或未知不能验收通过。仅清理本次创建且可识别的会话、进程或测试数据。

## 判定

验收从固定 required 检查集合计算，输出所有 checks 与 attempt IDs。漏测/blocked 阻塞；failed 失败；error、证据不足、跳过、混合重试或清理不明为 inconclusive；源内容或被测目标变化为 stale。记录合法、执行记录存在、覆盖完整、验收通过是不同字段。所有尝试和原始文件可复核；SHA-256 能发现变化但不是外部事实认证或防恶意重写的签名。

## 迁移

API v1 旧结果可保持原样继续使用。要加入新的历史记录体系：
```sh
python <skills>/_test-run-shared/scripts/test_run.py migrate --input old-result.json --check
python <skills>/_test-run-shared/scripts/test_run.py migrate --input old-result.json --output new-legacy-record.json
```
支持 Arazzo、Schemathesis、pytest、组合 automation envelope。保留原始状态/内容/摘要，标记缺失的执行前范围、目标身份和断言映射；迁移记录不是 test-attempt，不能进入当前验收。不可反推 freeze 时间，重新执行才能形成完整的新协议记录。重复迁移和覆盖输出均拒绝，原件保留。TestSpec 旧 context 仍使用 migrate_change_context.py，两个迁移层互不混用。
