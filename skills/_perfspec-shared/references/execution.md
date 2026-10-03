# 性能执行与 TestKit 验收交接

PerfSpec 使用现有 `_test-run-shared/scripts/test_run.py` 管理记录。该 CLI 不执行压测、不验证 SLA 算术、不认证外部构建或原始结果真实性。当前不接受 jmeter/locust/k6 原生 binding；采用可审查 observation，保留所有原始证据。不能自动把任何原生 summary 映射成 passed。

## 执行前

数据准备、smoke 和正式 profile 是独立运行，分别冻结各自执行输入。正式 freeze 在数据准备与 smoke 完成、最终数据校验之后；原生结果和 execution.json 只能在对应执行期间/之后采集，不是 freeze 的来源。

若需要 seed：先核对资产和已有写入/清理授权，按下述范围规则建立独立 mode=local 的准备运行，冻结 seed/cleanup 定义、参数和数据分配规则，再执行。`preparation.json` 记录 preparation_run_id、输入摘要、真实时间、每步状态、本次实体登记证据（脱敏）、requested_count/created_count/usable_count、分片校验、未完成动作、cleanup_status 和原始证据。凭据与业务正文不落盘。
部分失败保存已写入实体和未知状态，先恢复/清理；不因数量不足就从头重放 seed。smoke 消耗数据后重新校验/补充，正式快照反映最终状态；准备记录作为 supporting evidence，不冒充正式负载结果。

1. 核对可访问的实际构建、URL、环境、操作角色及已授权负载/时长/写入范围。public 可访问不是压测许可。
2. 将当前 plan、脚本、数据、生成器、配置和相关需求/用例作为 sources 冻结，kind 使用既有 requirements/cases/strategy/local-check/runner-definition/dataset。敏感数据使用可复核脱敏副本、生成定义或非秘密数据，不将真实凭据放入冻结目录。
3. 构造 scope-draft，required 从完整已确认范围取得。每场景至少绑定业务正确性、测量有效性、负载达成和已配置的 SLA 检查；cleanup required 独立记录。每个 check 引用来源、case_id、REQ、target 和独立 oracle。
   PerfSpec 在 scope-draft 中增加 profile_id，标明这次运行的 profile；它是保留在 scope.json 中的 PerfSpec 元数据，现有 freeze CLI 不代为校验 profile。smoke 和正式 scope 不能互换。
4. binding 使用 `{"runner":"observation","selector":"/checks/PERF_001"}`；selector 指向之后 performance-result.json 中的单项对象。正式 acceptance 使用真实 TestSpec case/REQ ID；局部运行可以使用 local-check。
5. target platform 仍为 api/web，不新增 perfspec 平台。capability actions 仍为 read/write，scope/basis 额外写清最大负载、时长和副作用；工具存在不证明授权。

```sh
python <skills>/_test-run-shared/scripts/test_run.py freeze \
  --root <project> --run-dir <project>/test-runs/<new-run-id> \
  --input <scope-draft.json>
```

CLI 拒绝已有运行目录；输出生成后再把执行文件写到该新目录。执行前检查输入仍匹配 scope，采集执行后摘要，不事后反推 freeze。
正式验收的用例全集中 excluded 项须有范围原因，blocked 项不能消失；publish 不作为前置。现有 CLI 的覆盖结论按冻结 checks 计算，不能单凭其通过声称未列入范围的用例已执行。

## execution.json

真实执行采集并保存：schema_version、spec_id、run_id、profile_id、runner{name,version}、workers、target{id,platform,url,build,environment,identity_basis}、started_at、finished_at、status（completed/failed/aborted/error/blocked）、exit_code（无进程则 null）、effective_config 与其摘要、input_hashes_before/after、inputs_unchanged、phase_windows、raw_artifacts、generator_monitoring、stop_reason、cleanup_status、cleanup_evidence。
execution 另记录执行前 scope.json 的 scope_sha256；规范化结果引用同一 scope 文件与摘要，并与 scope 的 run_id/profile_id、plan 来源摘要、必测 checks 对齐。不能在执行后从剩余通过项反推 scope。
input_hashes_before/after 按 scope.sources 的 path→sha256 全集采集；runner 入口和 plan.data.dataset_paths 不能漏入 scope。用于当前通过时再核对实际文件内容及计划来源摘要；两份执行摘要彼此相等不能证明未漂移。发生漂移保留历史记录，当前结论标 stale，修订输入需新运行。
时间带时区，窗口覆盖真实执行；unknown 明确保留，不复制文档示例。有效配置覆盖 CLI、环境的非秘密部分、脚本选项和分布式参数；记录秘密名称不记录值。所有 evidence 都位于 root 内且经脱敏。
smoke 和正式运行使用独立 run/profile。耗数初始化或 smoke 改变正式输入时更新资产快照、重新 freeze；dataset 外部写入状态要有自己的验证证据。

## 执行后

由 `perfspec-evaluate` 复核后生成 performance-result.json。checks 对象示例：

```json
{
  "checks": {
    "PERF_001": {
      "id": "PERF_001",
      "status": "inconclusive",
      "actual": "目标 20 iterations/s，实际 8；P95 230 ms",
      "basis": "正式测量窗口负载未达到；引用 raw 结果与执行配置，不能据低延迟证明目标容量",
      "method": "tool"
    }
  }
}
```

method=tool 仅在实际工具采集/计算支撑时使用；人工评估明确 method=human、核验者和依据。这里的示例不是执行事实，也不能直接登记。
每个 attempt 的第一份 evidence 指向 performance-result.json，后续包括原生 JTL/JSON/CSV、execution.json、监控、构建身份、数据准备和清理依据。checks 是按 check ID 索引的对象，键与对象 id 一致，禁止数组。attempt.check_id 与固定 oracle 对齐，status 与 observation 一致，时间取真实采集值。

```sh
python <skills>/_test-run-shared/scripts/test_run.py record \
  --root <project> --run-dir <run-dir> --input <attempt-draft.json>
python <skills>/_test-run-shared/scripts/test_run.py evaluate \
  --root <project> --run-dir <run-dir> --current-targets <targets.json> \
  --output <new-acceptance-report.json>
```

复核 source hashes、实际输入、target identity 和每个 oracle 是宿主责任；observation binding 不会自动执行原生 runner provenance 检查。范围不全、metadata 不足或只有历史 summary 时，仅保留局部分析/inconclusive，不用手填 metadata 晋升正式通过。
失败后重试必须新 attempt；资产、profile 或目标改变必须新运行，保留原记录。evaluate 不重跑压测，最终验收仍由 test-acceptance 管理。
