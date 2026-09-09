# Pytest 存量资产兼容

仅在用户已有 pytest 资产，或测试需要专有签名、文件/流处理、消息队列、数据库后置验证等 Arazzo 不适合表达的 Python 逻辑时读取本文件。新建的 OpenAPI 广覆盖仍优先使用 Schemathesis，确定性业务链仍优先使用 Arazzo。

## 安全边界

`collect` 不是静态扫描。pytest collection 会导入测试模块、`conftest.py` 和显式插件，因此 collection 与 execution 都属于 Python 代码执行。必须满足：

- 用户明确给出 pytest 项目根目录和 selector；不得默认扫描整个仓库。
- selector 只能是项目目录内路径或原生完整 nodeid，不接受任意 pytest 参数。
- 默认禁用通过安装包 entry point 自动发现的第三方插件，并忽略环境中的 `PYTEST_ADDOPTS`、`PYTEST_PLUGINS`；所需外部插件通过 collection 的 `--plugin` 明确登记。项目范围内被指纹覆盖的 `conftest.py` 仍会按 pytest 原生语义加载，也可能声明项目插件，因此 collection 仍是代码执行。
- 运行只接受 manifest 中的完整 nodeid；不存在、重复或最终零选择都失败关闭。
- collection 后测试文件、相关 `conftest.py` 或 pytest 配置发生变化时，manifest 立即视为 stale。
- secret 通过环境提供，并用 `--secret-env ENV_NAME` 登记脱敏；不得把值写进 selector、manifest 或回复。
- pytest 测试自身的联网、写操作和环境风险仍受用户授权边界约束；manifest 只控制来源和选择范围，不等于目标环境授权。

## Collection manifest

```bash
python scripts/pytest_compat.py collect ./service \
  --selector tests/api \
  --output ./api-tests/pytest-source-manifest.json
```

需要项目插件时重复传入模块名：

```bash
python scripts/pytest_compat.py collect ./service \
  --selector tests/api/test_users.py \
  --plugin pytest_asyncio.plugin \
  --output ./api-tests/pytest-source-manifest.json
```

manifest 记录 pytest 版本与配置相对路径、collection selector、显式插件及可解析版本、环境隔离策略、原生完整 nodeid、来源文件、相关 `conftest.py` 和 pytest 配置的 SHA-256，以及聚合 `source_fingerprint`。运行时插件版本变化会使 manifest 失效。

manifest 不保存项目绝对路径、环境变量值或 pytest stdout。collection error、退出码 5 和零条目都不生成成功 manifest。已有输出未经 `--force` 不覆盖。

## 精确执行

执行单个参数化 nodeid：

```bash
python scripts/pytest_compat.py run ./service \
  --manifest ./api-tests/pytest-source-manifest.json \
  --nodeid 'tests/api/test_users.py::test_get_user[active]' \
  --junit ./api-tests/reports/pytest-junit.xml \
  --output ./api-tests/reports/pytest-run-result.json
```

明确执行 manifest 的全部条目：

```bash
python scripts/pytest_compat.py run ./service \
  --manifest ./api-tests/pytest-source-manifest.json \
  --all-collected \
  --junit ./api-tests/reports/pytest-junit.xml \
  --output ./api-tests/reports/pytest-run-result.json
```

执行前重新计算 source fingerprint，并核对当前 pytest 版本。JUnit 在写入正式路径前完成 secret 脱敏；规范化 JSON 记录选择的 nodeid、pytest 版本、原始 exit code、汇总、逐 testcase 结果和有长度上限的脱敏输出。报告目标互不相同，已有文件未经 `--force` 不覆盖。

退出语义：

- `0`：pytest exit code 0，至少执行一个 testcase；
- `1`：pytest exit code 1，表示确定性测试发现；
- `2`：collection、配置、stale、未知 nodeid、pytest 版本、JUnit、timeout 或其他 runner 错误。

不得仅根据 JUnit tests/failures 数量覆盖原始 exit code。pytest exit code 5 即使生成空 JUnit，也属于配置错误。

## 归一化外部结果

已有 CI 单独执行 pytest 时，可把 exit code 和 JUnit 合并为同一结果契约：

```bash
python scripts/pytest_compat.py normalize \
  --junit ./raw-junit.xml \
  --exit-code 1 \
  --secret-env API_TOKEN \
  --sanitized-junit ./pytest-junit.xml \
  --output ./pytest-run-result.json
```

`normalize` 不执行测试，也不推断测试选择范围。输入 JUnit 损坏、根元素不支持或 exit code 0 但零 testcase 时失败，不写成功结果。
