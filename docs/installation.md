# 安装 TestKit

本指南已按 2026 年 7 月 26 日的官方文档和本地 CLI 行为更新。推荐顺序是：

1. Claude Code 和 Codex 优先安装完整插件
2. 其他兼容 Agent Skills 的工具按“通用安装”加载独立 skill
3. TestSpec 全流程必须保留 `skills/_testspec-shared/`，不能拆成单个 skill 安装

## Claude Code

TestKit 已包含 Claude Code marketplace。推荐在 Claude Code 中执行：

```text
/plugin marketplace add winhok/testkit
/plugin install testkit@testkit
/reload-plugins
```

也可以使用非交互式 CLI：

```bash
claude plugin marketplace add winhok/testkit
claude plugin install testkit@testkit
```

`testkit@testkit` 中，前一个 `testkit` 是插件名，后一个是 marketplace 名。插件安装会保留完整 `skills/`，因此 TestSpec 的共享契约也会一起安装。

更新时先刷新 marketplace，再更新已安装插件：

```bash
claude plugin marketplace update testkit
claude plugin update testkit@testkit
```

更新完成后重启 Claude Code，或在会话中执行 `/reload-plugins`。

## Codex

TestKit 已包含：

- `.codex-plugin/plugin.json`：插件 manifest
- `.agents/plugins/marketplace.json`：名为 `testkit-marketplace` 的 marketplace

使用当前 Codex CLI 安装完整插件：

```bash
codex plugin marketplace add winhok/testkit
codex plugin add testkit@testkit-marketplace
```

检查安装状态：

```bash
codex plugin marketplace list
codex plugin list
```

刷新 TestKit marketplace 快照：

```bash
codex plugin marketplace upgrade testkit-marketplace
```

刷新后用 `codex plugin list --available --json` 比较已安装版本与可用版本。当前 CLI 没有独立的 `plugin update` 子命令，不要把 marketplace 刷新等同于插件已升级。

在受管理的工作区中，插件是否可见还会受到计划、角色和管理员 Installation policy 的限制。TestKit 是 skill-only plugin，不需要连接外部 app。

## 通用安装：独立 skill

以下五个 skill 是自包含的，可以独立安装：

- `api-test-automation`
- `generate-api-artifacts`
- `log-analysis`
- `sql-safety-review`
- `android-static-app-reverse`

### GitHub CLI（优先）

GitHub CLI 2.90.0 起提供 `gh skill`。该功能目前仍是 public preview，但支持安装前预览、来源追踪、版本固定和更新检查。

先检查内容，再安装到项目：

```bash
gh skill preview winhok/testkit api-test-automation
gh skill install winhok/testkit api-test-automation
```

交互式运行时选择目标 Agent 和安装范围。非交互环境应显式提供目标 Agent；团队或 CI 还应使用完整 commit SHA 固定来源：

```bash
gh skill install winhok/testkit api-test-automation \
  --agent universal \
  --scope project \
  --pin <full-commit-sha>
```

先检查更新，再决定是否应用：

```bash
gh skill update --all --dry-run
gh skill update api-test-automation
```

### `npx skills`（社区兼容入口）

Node.js 18 及以上可以使用 `vercel-labs/skills`：

```bash
npx skills add winhok/testkit --list
npx skills add winhok/testkit --skill api-test-automation
```

默认安装到当前项目；追加 `--global` 才会安装到用户级目录。首次安装不要使用 `--yes`，先核对目标 agent、skill 和安装位置。

## 安装完整 skills 目录

TestSpec skills 不是独立包。它们会读取同级的 `_testspec-shared`，部分阶段还会读取其他 TestSpec skill 的模板。因此：

- 不要对 TestKit 使用 `gh skill install --all`
- 不要对 TestKit 使用 `npx skills add --skill '*'`
- Claude Code 和 Codex 应优先使用完整插件
- 其他工具只能使用通用 Agent Skills 入口时，应复制 `skills/` **目录内的全部内容**，不要只复制 `testspec-*`

目标目录由具体 Agent 的 Agent Skills 实现决定。复制后应满足：

```text
<目标 skills 目录>/
├── _testspec-shared/
├── testspec-new/
├── testspec-update/
├── ...
└── api-test-automation/
```

如果目标目录已经存在同名 skill，先检查来源和本地修改，不要直接覆盖。

## 安装 Python 依赖

仓库脚本使用 Python 3。推荐使用 `uv` 和项目虚拟环境：

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip check
```

不使用 `uv` 时：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

不要把这些依赖安装到系统 Python。`requirements.txt` 当前包含 Excel 生成、YAML/OpenAPI 解析和 Schemathesis 生成式 API 测试所需依赖。

## 验证

在 TestKit 仓库根目录运行：

```bash
python scripts/test_all.py
```

只验证插件打包和 marketplace：

```bash
python scripts/test_all.py --only packaging
```

详细检查组见[开发维护指南](development.md)。

## 参考

- [Claude Code：插件 marketplace](https://code.claude.com/docs/en/discover-plugins)
- [Claude Code：Agent Skills](https://code.claude.com/docs/en/skills)
- [OpenAI：构建 Codex 插件](https://learn.chatgpt.com/docs/build-plugins)
- [OpenAI：Codex 插件与工作区策略](https://help.openai.com/en/articles/20001256/)
- [GitHub CLI：`gh skill install`](https://cli.github.com/manual/gh_skill_install)
- [`vercel-labs/skills`](https://github.com/vercel-labs/skills)
- [uv：虚拟环境](https://docs.astral.sh/uv/pip/environments/)
