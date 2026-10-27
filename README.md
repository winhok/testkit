<p align="center">
  <img src="assets/logo.svg" width="512" alt="TestKit — Agent skills for practical software testing">
</p>

<p align="center">
  Agent skills for QA engineers and developers: turn requirements into test cases and test runs into traceable results.
</p>

<p align="center">
  English | <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/winhok/testkit/stargazers">
    <img src="https://img.shields.io/github/stars/winhok/testkit?style=flat-square&logo=github" alt="GitHub Stars">
  </a>
  <a href="https://github.com/winhok/testkit/forks">
    <img src="https://img.shields.io/github/forks/winhok/testkit?style=flat-square&logo=github" alt="GitHub Forks">
  </a>
  <a href="https://github.com/winhok/testkit/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/winhok/testkit?style=flat-square" alt="License">
  </a>
</p>

# TestKit

TestKit packages repeatable, reviewable testing workflows as [Agent Skills](https://agentskills.io/) for Claude Code, Codex, and other compatible agents. It connects current requirements to traceable execution evidence across test design, automation, diagnosis, defect verification, and acceptance.

## See TestKit in 101 seconds

An access-control example connects requirement clarification, case review, execution evidence, and acceptance. This is a concept demo, not a live test run.

https://github.com/user-attachments/assets/1f37435c-bc55-43cd-8501-21326120646f

[Open the MP4 file](assets/readme/testkit-demo.en.mp4) · English narration and subtitles.

## Why TestKit

- **An end-to-end workflow:** Move from PRD intake and test analysis through strategy, test points, cases, review, execution, defect retesting, and acceptance.
- **Two complementary API testing paths:** Use Arazzo for deterministic business flows and Schemathesis for examples, coverage, fuzzing, and stateful testing.
- **One evidence contract across Android, iOS, and Web:** Freeze the build, environment, and scope before execution; associate results with raw evidence so retries or stale results cannot silently become a pass.
- **Support for existing projects:** Import OpenAPI, Swagger, YApi, Postman, historical cases, controlled pytest assets, and legacy API reports.
- **Explicit operating boundaries:** Code inspection, write-method tests, knowledge-base changes, and issue submission require the appropriate authorization. Credentials come from environment variables, and persisted results are redacted.
- **Portable and verifiable:** Skills follow the Agent Skills directory convention. The repository includes contract checks, synthetic eval definitions, and a unified test entry point.

## Quick start

Install the full plugin to retain the shared contracts required by TestSpec and test execution.

### Codex

```bash
codex plugin marketplace add winhok/testkit
codex plugin add testkit@testkit-marketplace
```

### Claude Code

```text
/plugin marketplace add winhok/testkit
/plugin install testkit@testkit
/reload-plugins
```

### Other Agent Skills clients

Five self-contained skills, including `api-test-automation`, can be installed individually after previewing them:

```bash
gh skill preview winhok/testkit api-test-automation
gh skill install winhok/testkit api-test-automation
```

TestSpec, PerfSpec, and execution skills depend on shared directories and should be installed as part of the full plugin. See the [installation guide](docs/installation.en.md) for compatibility, updates, Python dependencies, and the `npx skills` option.

### First task: design coupon test cases

After installing the full plugin, open a writable project in your agent and paste:

```text
Use TestKit to design tests for this requirement. Create a coupon-discount
change, analyze the requirements, list test points, generate cases, and review
them. Ask me about missing rules before continuing. Export Excel when the
required Python dependencies are available. Do not execute tests.

R1: Amounts use CNY with two decimal places. For a merchandise subtotal of
at least CNY 100.00, one valid coupon deducts CNY 20.00. Otherwise reject it
and leave the subtotal unchanged.
R2: Reject expired or already-used coupons and leave the subtotal unchanged.
R3: Shipping and stacking discounts are outside this scope.
```

Expected artifacts include a requirements document, analysis, test points,
JSON test cases, and a review under `testspec/changes/coupon-discount/`.
Excel export requires the [Python dependencies](docs/installation.en.md#python-dependencies).
The agent may pause for clarification or a required strategy before generating cases.

| Example input | Expected result |
|---|---|
| CNY 99.99 + valid coupon | Reject; subtotal stays CNY 99.99 |
| CNY 100.00 + valid coupon | Accept; payable amount is CNY 80.00 |
| CNY 100.01 + valid coupon | Accept; payable amount is CNY 80.01 |
| CNY 100.00 + expired coupon | Reject; subtotal stays CNY 100.00 |

This is an illustrative preview, not an executed test report. See the
[bilingual showcase](examples/coupon-discount/README.md) for the full input,
sample cases, and clarification example. No device or target API is needed;
your agent's usual model access is still required.

For a live API example, see the opt-in [DummyJSON authentication demo](examples/api-test-automation/dummyjson-auth/README.md).

> [!NOTE]
> TestKit supplies workflows, scripts, and result contracts. It does not bundle devices, browser services, Appium drivers, business accounts, or a target environment. Execution uses host tools that are available and authorized for the task.

## Capabilities

26 skills cover the following workflows. Detailed capability guides are currently in Simplified Chinese.

| Goal | Skill | Input and output |
|---|---|---|
| [Requirements and test design](docs/testspec.md) | `testspec-*` | PRD, product answers, and historical cases → analysis, strategy, test points, Excel/XMind cases, and review |
| [API automation](docs/api-test-automation.md) | `api-test-automation` | OpenAPI, Swagger, YApi, Postman, or pytest → workflow execution, generative tests, and normalized results |
| [API artifacts](docs/generate-api-artifacts.md) | `generate-api-artifacts` | Reviewed OpenAPI → Postman Collection, Apifox, and JMeter JMX |
| [Performance testing](docs/perfspec.md) | `perfspec-*` | Performance goals → load plan → native JMeter/Locust/k6 assets, execution evidence, and evaluation |
| [Cross-platform app testing](docs/app-test.md) | `app-test` | Android, iOS, or Web target → interaction assertions, evidence, and journey results |
| [Repository-free Web analysis](docs/web-app-reverse.md) | `web-app-reverse` | Website without source access → implementation evidence and TestSpec design input |
| [Log diagnosis](docs/log-analysis.md) | `log-analysis` | Logs and trace IDs → request reconstruction, field provenance, and failure or performance diagnosis |
| [SQL review](docs/sql-safety-review.md) | `sql-safety-review` | OLTP/OLAP SQL → semantic, performance, index, transaction, and lock risks |
| [Android static analysis](docs/android-static-app-reverse.md) | `android-static-app-reverse` | Authorized APK → decompilation, protection signals, API clues, and static leakage clues |
| [Defect verification](docs/defect-verification.md) | `defect-verification` | Defect and fix build → RED, GREEN, REGRESSION verdicts with evidence |
| [Video to issue](docs/video-to-issue.md) | `video-to-issue` | Defect recording → reproduction steps, expected/actual results, and timestamped evidence |
| [Test acceptance](docs/test-acceptance.md) | `test-acceptance` | Frozen scope, results, and evidence → coverage, evidence gaps, and current-build verdict |

Each `skills/<skill-name>/SKILL.md` defines its trigger, inputs, outputs, and operating boundaries. Execution skills share the [execution and evidence contract](skills/_test-run-shared/references/execution-contract.md).

## How the workflow fits together

```text
Requirements → analysis → strategy (when needed) → test points → cases → review
API definition → workflow and schema tests → raw evidence + unified results
Performance goals → load plan → native test assets → execution → evaluation
Test execution → coverage and evidence checks → verdict for the tested build
```

Requirements define expected behavior; code and historical cases provide supporting
context. Before execution, record the build, environment, scope, and checks.
Missing checks, outdated evidence, and unfinished cleanup remain visible in the result.

See the [TestSpec](docs/testspec.md), [API automation](docs/api-test-automation.md),
[PerfSpec](docs/perfspec.md), and [execution contract](skills/_test-run-shared/references/execution-contract.md)
for stage details, compatibility paths, and migration rules (Simplified Chinese).

## Operating boundaries

- Code scanning, write-method or destructive tests, TestLib changes, and external issue submission require explicit authorization.
- API keys, passwords, and tokens are supplied through environment variables; persisted results and public fixtures are redacted and checked for privacy.
- Fuzzing, stateful, and write-method tests run only in a confirmed isolated environment.
- Android static analysis applies only to authorized targets; it does not include bypasses or runtime attacks.
- Historical cases enter TestLib only after alignment with the current PRD and review.

Web testing prefers ego-lite for browser access and session reuse, Midscene for UI automation, agent-browser for supporting exploration and diagnosis, and Computer Use as the fallback. Your selected tool or session takes precedence. Start with [browser setup and tool checks](skills/app-test/references/browser-setup.md), then [session connection and diagnosis](skills/app-test/references/web-session.md).

Use `testspec-update` for requirement changes and `testspec-plan` for execution planning. `testspec-code-calibrate` requires explicit invocation.

## Documentation and support

The installation guide is available in English; the detailed guides below are in Simplified Chinese.

- [Installation and updates](docs/installation.en.md)
- [TestSpec](docs/testspec.md)
- [PerfSpec performance testing](docs/perfspec.md)
- [API automation](docs/api-test-automation.md) and [API artifacts](docs/generate-api-artifacts.md)
- [Android, iOS, and Web testing](docs/app-test.md) and [repository-free Web analysis](docs/web-app-reverse.md)
- [Log diagnosis](docs/log-analysis.md), [SQL review](docs/sql-safety-review.md), and [Android static analysis](docs/android-static-app-reverse.md)
- [Defect verification](docs/defect-verification.md) and [video to issue](docs/video-to-issue.md)
- [Test acceptance](docs/test-acceptance.md) and [execution contract](skills/_test-run-shared/references/execution-contract.md)
- [Development and validation](docs/development.md)

For questions, bugs, and suggestions, use [GitHub Issues](https://github.com/winhok/testkit/issues). The project is maintained by [winhok](https://github.com/winhok).

## Development and contribution

Bug reports, documentation fixes, and skill improvements are welcome. Include reproduction steps and redacted evidence in issues; describe the change and relevant checks in pull requests.

Run the unified checks after installing the repository dependencies:

```bash
python scripts/test_all.py
```

This covers plugin packaging, cross-skill contracts, synthetic eval definitions, and unit tests. Live evaluations against devices, browsers, or public APIs require separate setup and evidence; offline checks do not establish external acceptance. Read the [development guide](docs/development.md) before contributing.

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=winhok/testkit&type=Date)](https://star-history.com/#winhok/testkit&Date)

## License

[MIT](LICENSE)
