# 性能结果与基线比较 v1

`performance-result.json` 是由宿主根据真实结果制作的规范化报告，不是现有 API result v1，也不是 runner 原生执行证明。保留原始文件与字段定义；无计划的历史分析使用 report-only。

## 字段

- schema_version=1、spec_id、run_id、plan_sha256、runner{name,version}、target、mode=local|acceptance|report-only。
- local/acceptance 另含 profile_id（本次执行的单一 profile）、scope={path,sha256}（执行前冻结检查范围）、load_observation={model,unit,stages:[{duration_seconds,target,actual}],source}。阶段 actual 表示按该模型采集的达成负载；阶段顺序、时长、目标对应所选 profile，不能将 smoke 负载当作正式负载。
- execution={path,sha256}：相对 root 指向已有 execution.json，并校验文件摘要。状态、退出码、时间、配置、输入摘要及身份依据统一保存在 [execution.json 契约](execution.md#executionjson) 中；不在结果里重复内嵌这些详情。缺失执行来源时为 null。
- raw_evidence：非空 [{path,sha256}]，相对 root 指向已有原始文件；report-only 也必须保留。
- window：开始/结束、阶段、样本排除规则；无法分窗时明确 unknown。
- scenarios：从冻结计划全集列出 id、required、exclusion_reason、observed、metrics、threshold_results 和证据引用。
- metrics：稳定 selector、metric、unit、statistic、value（缺失 null）、sample_count、window、source、calculation、失败样本处理。吞吐分开 requests/iterations/completed-business-journeys。
- checks：按 check ID 索引的 JSON 对象（禁止数组）；每个值含 id、status、actual、basis、method=tool|human，键必须等于 id。用 `/checks/<check-id>` 进行 observation 绑定。status 使用现有 observation 的 passed/failed/blocked/skipped/inconclusive/error；报告级 stale 不直接作为 observation 状态。
- execution_validity=valid|invalid|unknown；load_status=met|not-met|unknown|not-applicable；functional_status、sla_status=passed|failed|unknown|not-applicable；cleanup_status=passed|failed|unknown|not-required。
- verdict=passed|failed|blocked|inconclusive|stale；reasons、limitations、comparison、diagnosis。

## 缺失值与完整示例

local/acceptance 的 spec_id、run_id、plan_sha256、runner、target 和 execution 引用必须来自真实输入。report-only 中没有来源的 spec_id/run_id/plan_sha256、runner.name/runner.version、target、execution、window 使用 JSON null；保留 raw evidence 引用与 limitations，不补造 unknown 字符串、摘要或时间。无冻结范围时 scenarios 只表示 observed 标签，required=null，并说明完整覆盖 unknown；checks 可为空对象，不得用于正式 record。
无冻结来源的外部/合成摘要都可使用 report-only。摘要的 execution_valid=true 只保留为来源声明，独立 execution_validity 仍为 unknown；未冻结阈值只做描述性数值比较，sla_status=unknown。明确没有配置 SLA 时 sla_status=not-applicable，verdict 不得因空阈值集合变 passed。没有计划的描述性报告使用 verdict=inconclusive（已明确来源过期时 stale），原报告事实可单独引用。摘要含明确目标与实际负载时可保留描述性的 load_status=met/not-met 并声明测量有效性 unknown；缺少比较口径时 unknown，纯描述且没有负载目标才 not-applicable。report-only 允许顶层 metrics 数组保存无场景归属的观察，selector/sample_count/window/失败样本口径无来源时 null；不得虚构场景或完整覆盖。
完整 local 合成示例见 [example-artifacts.md](example-artifacts.md)；历史分析缺失字段示例见同页。示例不是生产执行事实。

## 计算与状态

先判断证据是否足以支持测量，再计算原生业务断言和冻结阈值。原生 nonzero 可能是阈值失败，也可能是执行器错误；不能只看退出码。

1. 当前来源、计划/资产/数据或被测目标与冻结记录不符：stale。历史报告保留历史事实，不将其晋升为当前通过。
   当前 passed 还须核对 scope.sources 的实际文件摘要，执行 input_hashes_before/after 均须等于该冻结来源映射；计划、runner 入口和全部 dataset_paths 必须在其中。历史文件不会被检查器改写；输入漂移后保留原报告，另行标记 stale 或使用历史 report-only 分析，不能继续作为当前通过证据。
2. 未执行且必需 capability/授权/数据缺失：blocked，仍列所有场景。
3. 有可信且有效样本支持任一必需业务或 SLA 失败：failed；其他缺口继续列出。无效测量不能包装成可信 SLA passed/failed，原生失败事实独立保存。
4. 已执行但窗口未知、压测机饱和影响未排除、样本不足、必需指标缺失、标签歧义、提前中止、负载未达到或清理失败/unknown：inconclusive。负载未达需区分 generator 不足与已观察的服务退化；后者有有效 SLA 失败可为 failed。
5. passed 需 required 全覆盖、有效测量、达到该 profile 负载、业务和所有已配置 SLA 通过、清理完成。closed 不需要凭空附加开放到达率；load not-applicable 仅用于明确的纯历史描述，不允许正式性能验收借此跳过负载证明。
6. 探索容量没有通过标准时可以给出已观察容量区间与限制，sla_status=not-applicable，不能据此判 SLA passed。中止后不推断未测负载的容量。

unknown、空样本、null、未映射和遗漏不能按 0 或 passed 处理；不对各 worker/场景 P95 求平均。仅使用兼容原始样本、直方图或工具原生聚合；声明算法和精度。
local/acceptance 场景的 required 必须与冻结计划相同，threshold_results 按计划阈值 ID 完整列出且不得重复；未测阈值也保留条目并标 unknown，不能通过删除阈值或修改 required 缩小通过条件。
一次结果对应 execution.profile_id 和冻结 scope.profile_id 指定的同一 profile。场景列表仍保留计划全集；本次未包含的场景 observed=false，阈值 unknown；passed 只表示所选 profile 的必测场景通过，不代表其他 profile 或全计划通过。结果 checks 必须包含冻结 scope 中所有 required ID，额外 check 也须存在于 scope。
passed 的必测指标须有有限数值和整数样本数，样本数达到场景 sample_policy 与 profile measurement 的较高下限（至少 1）；阈值 actual 不得 null，必须对应相同 selector/metric/statistic/unit 的指标值，limit/operator 保持计划定义。结果测量窗口须位于 execution 的对应 phase 内，并达到所选 profile 的最短测量时长；指标窗口与该 phase 相同。这些产物检查不重算原生百分位或 SLA。
不同工具 elapsed/http_req_duration/Locust response_time 的边界并不天然一致；连接/TLS、重定向、流式读取、失败请求和旅程计时必须明确定义。

## 比较

comparison={status: comparable|not-comparable|unknown|not-requested, differences, metrics, verdict, basis}。
比较前核对场景步骤/配比、profile 模型/阶段/负载、数据类别、环境拓扑/资源、压测机、工具版本/参数、计时边界/窗口/算法。build 可是本次比较变量，其余差异需控制或说明影响；不同工具无一致性证明时不声称可比。
使用计划预定绝对阈值与相对回退规则。基线为 0 时不计算无意义百分比；噪声和样本不足给 unknown，不能将一次波动确定为回退。

## 诊断

diagnosis：time_windows、facts（含证据来源）、hypotheses（confidence 与可证伪动作）、clock_uncertainty、missing_signals。日志和监控只证明采集事实，相关性不能单独证明根因。建议下一轮负载或优化由后续任务决定，不修改原计划或原始 verdict。
