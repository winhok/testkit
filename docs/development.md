# 验证和维护 TestKit

本指南面向 TestKit 维护者。它说明如何运行稳定检查、管理公开评测（eval）、维护 TestLib，并在发布前检查插件包装。

## 安装开发依赖

建议使用仓库虚拟环境：

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip check
```

## 运行稳定检查

运行插件包装、契约、eval 定义和单元测试：

```bash
python scripts/test_all.py
```

按检查组运行：

```bash
python scripts/test_all.py --only packaging
python scripts/test_all.py --only contracts
python scripts/test_all.py --only evals
python scripts/test_all.py --only unit
```

检查组职责如下：

| 检查组 | 验证内容 |
|---|---|
| `packaging` | Codex、Claude Code 插件 manifest 和目录包装 |
| `contracts` | TestSpec context v2、question graph、plan、迁移、跨 skill 输入与状态契约 |
| `evals` | 全仓 synthetic eval、触发边界、版本基线工具和 TestSpec 上下文链 |
| `unit` | adapters、runner、迁移器、生成器和知识库工具 |

执行与验收定向检查：`python skills/_test-run-shared/tests/test_test_run.py`。覆盖冻结范围、漏测、过期、证据变更、权限、依赖、重试、清理、API 适配与旧报告迁移。新增行为 eval 定义不等于已运行模型评测；三端真实环境验收另行记录工具、目标及证据。

旧脚本回归：`python tests/test_legacy_script_regressions.py`，已纳入 unit 组，使用合成数据和工具 mock，覆盖输入保护、公司导出格式、迁移、TestLib、网络与静态分析边界。

## 运行 API live eval

API live eval 使用 DummyJSON 公开练习账号：

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass

python scripts/test_all.py --only live-api-test-automation
```

该检查需要网络。Schemathesis 如果发现公共服务的协议缺陷，可以返回测试失败；配置、认证或传输错误使用不同状态。

## 保护 eval 隐私

公开 TestSpec eval 只提交标记为 `synthetic` 的内联 fixture。本地业务材料放入已忽略的以下目录：

- `testspec/`
- `skills/**/evals/private/`

公开 eval 不得包含：

- 用户主目录绝对路径
- 邮箱、IP 地址或通用唯一标识符（UUID）
- 非 `example.invalid`（含其子域名）URL；公开格式标识 URL 除外
- 编辑器聊天记录路径
- 真实 PRD、用例、凭据或业务标识

仓库校验器会检查这些规则。模型行为 eval 仍需要支持 `evals/evals.json` 的运行器。

## 维护触发边界与版本基线

五个新增 Skills 的行为集包含 23 个离线合成场景（app-test 4、web-runtime-analysis 3、defect-verification 5、video-to-issue 4、test-acceptance 7），每个场景均附输入文件与稳定 assertion ID。程序断言检查显式要求的 eval-result.json 和输入内容完整性；定性断言检查结论依据、操作边界与未验证事实。全部是文件驱动场景，不替代真实浏览器、真机和外部 Issue 连接器测试。

```bash
python scripts/check_new_skill_evals.py
python scripts/check_new_skill_evals.py --probe-helpers
```

第一条验证 fixture hash、断言语法、空答案拒绝和输入修改检测；不执行模型评测。第二条已纳入标准 evals 检查组，另测试生产辅助脚本对已提供记录的判定，任何结果违背预期即返回非零。不要把该探针的结果计作模型通过率。

模型评测时，每个 case 使用全新隔离目录，保留完整 Skills/shared 依赖；只给模型 prompt 与 files，不提供 expected_output、assertions 或审查答案。模型输出落盘后才运行程序断言，由独立评审依据 qualitative rubric 判断定性项。用户要求的额外 eval-result.json 是评测输出约定，不修改正式产物协议。不得把本任务的参考推演或 fixture 检查结果冒充 baseline/candidate/without-skill 实测结果。使用此新数据集对三个组重新运行，不与旧的空 fixture 集混算。

根目录 `evals/skill-routing.json` 为每个公开 skill 保存至少一个 should-trigger 样本和一个 near-miss 排除样本。相邻能力必须成对覆盖；`testspec-plan` 必须分别排除明确的 analysis、points 和 generate 请求。新增、删除或改名 skill 时必须同步该文件。

Question graph 与旧 change 迁移的定向测试：

```bash
python skills/_testspec-shared/tests/test_question_graph.py
```

模型 eval runner 应对旧版、候选版和不加载 skill 的控制组使用完全相同的 prompt、fixture 与 assertion ID，并把 eval 定义内容哈希写入 `eval_set_sha256`。比较结果：

```bash
python scripts/compare_eval_runs.py \
  --baseline eval-results/previous.json \
  --candidate eval-results/candidate.json \
  --without-skill eval-results/without-skill.json \
  --output eval-results/comparison.json
```

任一旧版已通过断言在候选版失败、控制组通过整条用例，或候选版不优于控制组，比较命令都会失败。这样可区分真实 skill 增益与任何模型都能通过的弱断言。运行结果属于本地证据，除非完全合成且明确需要，否则不提交。

仓库级静态检查：

```bash
python scripts/validate_skill_repository.py
```

它检查公开 skill 的 frontmatter、MIT license、入口行数、reference 路由、合成 eval 和全量触发边界，并拒绝跟踪 Python cache 或把 `skills/` 根目录变成 Python package。

## 维护 TestLib

`testspec-publish` 是 TestLib 的正常写入入口。维护脚本不能替代 publish 流程。

只读检查 TestLib 健康度：

```bash
python skills/_testspec-shared/scripts/validate_testlib.py \
  --testlib testspec/testlib
```

联合审计重复、错放和 provenance 风险：

```bash
python skills/testspec-audit/scripts/audit_testlib.py \
  --testlib testspec/testlib
```

重建 TestLib 索引：

```bash
python skills/_testspec-shared/scripts/rebuild_testlib_index.py \
  --testlib testspec/testlib
```

审计默认只读。合并、废弃或迁移用例前，需要确认具体 case ID。

## 检查目录和链接

新增、删除或重命名 skill 后，需要同步检查：

- `.codex-plugin/plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- 根目录 `README.md`
- `scripts/test_all.py`

运行以下命令检查空白错误和旧名称残留：

```bash
git diff --check
rg "old_skill_name" README.md skills scripts .*-plugin
```

## 发布前检查

发布前完成以下检查：

1. 运行 `python scripts/test_all.py`
2. 运行受影响 skill 的定向测试
3. 检查 `git diff --check`
4. 确认没有提交 `__pycache__`、真实凭据或私有 eval
5. 确认 manifest、README 和 skill 名称一致
6. 对需要网络的 live eval 单独记录结果
