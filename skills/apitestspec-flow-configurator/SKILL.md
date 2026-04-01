---
name: apitestspec-flow-configurator
description: 为 API 自动化测试补齐可复用的前置 flow、项目级默认请求配置和环境变量约定。只要用户主要在说登录接口、token 提取、tenant 切换、默认 headers、project.yaml、flows/*.yaml、.env.example、config/.env 的增量补齐，或希望把前置依赖沉淀成可复用配置，都应优先使用这个 skill。当用户说"帮我配一下登录 flow""补一下 token 提取""项目缺 project.yaml"时务必使用。
---

# API Flow Configurator

把登录、租户切换、token 提取、默认 headers 和环境变量配置整理成项目级可复用 flow。

## One-line Purpose

当前阶段只负责把“前置依赖”沉淀成“可复用配置”。

## Use This When

- 用户主要问题是登录、鉴权、token/cookie、tenant、角色切换、预热接口
- 用户要新增或修改 `project.yaml`
- 用户要新增或修改 `flows/*.yaml`
- 用户要生成或补齐 `.env.example`、增量维护 `config/.env`
- 用户已经有 case/spec，但它们缺少前置 flow 才能执行

## Do Not Use This When

- 用户主要输入是接口文档，目标是从文档生成 case。这属于 `apitestspec-composer`
- 用户主要输入是源码，目标是先盘点接口。这属于 `apitestspec-surface-scan`
- 用户已经具备 spec，当前主要目标是直接运行、看结果、查失败原因。这属于 `apitestspec-scenario-runner`
- 用户已经有结果产物，只想看报告。这属于 `apitestspec-result-viewer`

## Hand Off To

- 还没有原生 spec：`apitestspec-composer`
- flow 和环境已齐备，下一步执行：`apitestspec-scenario-runner`
- 如果连接口面都还不清楚，先 `apitestspec-surface-scan`

## Suite Routing Snapshot

详见 [套件路由表](../apitestspec-shared/references/routing.md)。本 skill 对应阶段 3（有 spec，但缺登录流、环境变量或默认 headers）。
## Agent Goal

目标是把“怎么拿认证态、怎么准备前置上下文、怎么把变量传给后续 case”整理成稳定、可复用、可落盘的配置，而不是临时建议，也不是顺手去设计业务 case。

## Decision Matrix

### 输入材料

- 登录或前置接口说明：进入本 skill
- 现有 `project.yaml`、`flows/*.yaml`、`.env.example`、`config/.env`：进入本 skill
- 只有接口文档但没有前置依赖问题：通常不在本 skill

### 允许动作

- 允许写或更新 `project.yaml`
- 允许写或更新 `flows/*.yaml`
- 允许增量维护 `config/.env.example`
- 仅在用户明确要求时，允许增量维护 `config/.env`
- 不允许设计业务测试 case
- 不允许执行测试

### 完成标志

- flow 配置已落盘
- 项目级默认 headers / flow 接入已说明清楚
- 环境变量示例文件已补齐
- 明确哪些变量可供后续 case 复用

## Preferred Tools And Scripts

当输入足够结构化时，优先使用：

```bash
python skills/apitestspec-flow-configurator/scripts/bootstrap_flow.py \
  --output-dir <dir> \
  --project-name <name> \
  --flow-name <flow-name> \
  --method <HTTP-method> \
  --path <url-path> \
  --body '<json-body>' \
  --extract token=$.data.token
```

脚本无法覆盖复杂情况时，再直接编辑 YAML。

## Unified File Conventions

- 环境变量示例文件默认统一为 `config/.env.example`
- 本地环境文件默认统一为 `config/.env`
- `project.yaml` 中引用的变量应与 `config/.env.example` 保持一致
- 不再同时使用“输出目录下 `.env.example`”和 `config/.env.example` 两套口径

## Execution Workflow

1. 提取前置信息。
   - 接口路径
   - 请求方法
   - 请求体字段
   - 需要提取的响应字段与 JSONPath
2. 判断能落哪些文件。
   - `project.yaml`
   - `flows/*.yaml`
   - `config/.env.example`
   - 用户明确要求时，增量更新 `config/.env`
3. 优先整理成可复用变量。
   - token、userId、tenantId、role 等统一命名
4. 最后为执行阶段铺路。
   - 明确默认 headers
   - 明确哪些 flow 已接入 `project.yaml`
   - 明确下一步由 `apitestspec-scenario-runner` 执行

## Auto-Detect Before Asking

- 自动识别是否需要多个角色 flow
- 自动识别哪些 body 字段应该使用 `${ENV.xxx}`
- 自动识别哪些 extract 结果需要供后续 case 复用
- 自动识别是否需要 `BASE_URL`

## When To Stop Guessing

- 不知道 token 或 userId 的 JSONPath 时，不要杜撰
- 不知道登录 body 字段名时，不要默认写死 `username/password`
- `config/.env` 已存在时，不要覆盖已有值
- 用户没有要求写本地环境文件时，不要擅自改 `config/.env`

## Output Rules

### YAML 配置

- step / flow 里的 URL 只写相对路径（如 `/api/v2/login`），不要包含 `${BASE_URL}`。执行引擎会自动将 `project.base_url` 拼接到前面；如果手动写了 `${BASE_URL}`，会造成双重前缀
- `project.yaml` 里的 `base_url` 统一使用 `${ENV.BASE_URL}` 引用环境变量
- flow 中提取出的变量统一写入 `${vars.xxx}` 供后续步骤复用
- `extract` 键名要和后续 case 引用保持一致
- 多个依赖流使用稳定、可读的名字，例如 `user_login`、`admin_login`

### 环境变量文件

- 默认写入 `config/.env.example`
- `config/.env.example` 必须包含 `BASE_URL`
- YAML 中凡是出现 `${ENV.XXX}`，都应在 `config/.env.example` 给出示例值
- `config/.env.example` 已存在时，只增量补齐缺失变量
- 保留原有注释和顺序，不要粗暴重写整个文件

### 本地环境文件

- 只有用户明确要求时才处理 `config/.env`
- `config/.env` 不存在时，可从 `config/.env.example` 衍生初始版本
- `config/.env` 已存在时，只补缺失变量，不覆盖已有值
- 明确提醒用户替换示例值，避免提交敏感信息

## Output Contract

回答时必须说明：

- 改了哪些文件
- 新增了哪些环境变量
- 哪些提取值可在后续 case 中复用
- 默认 headers、base URL、flow 名称是否已接入 `project.yaml`
- 如果只生成了 `config/.env.example`，要明确说明尚未自动改 `config/.env`
- 当前没有做什么：不生成业务 case、不执行测试、不查看报告
- 如果信息不足，明确指出缺了哪些字段

## Resources

- Spec 格式参考：[../apitestspec-shared/references/spec-format.md](../apitestspec-shared/references/spec-format.md)
- 完整示例项目：[../apitestspec-shared/references/example-project.md](../apitestspec-shared/references/example-project.md)
