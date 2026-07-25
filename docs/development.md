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
| `contracts` | TestSpec 跨 skill 输入、产物和状态契约 |
| `evals` | synthetic eval 声明、fixture 和上下文链 |
| `unit` | adapters、runner、迁移器、生成器和知识库工具 |

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
- 非 `example.invalid` URL
- 编辑器聊天记录路径
- 真实 PRD、用例、凭据或业务标识

仓库校验器会检查这些规则。模型行为 eval 仍需要支持 `evals/evals.json` 的运行器。

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
