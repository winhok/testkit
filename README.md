<p align="center">
  <img src="assets/logo.svg" width="512" alt="TestKit — Agent skills for practical software testing">
</p>

<p align="center">
  21 agent skills for practical software testing: from requirements and test design to API and cross-platform execution, diagnosis, defect verification, and evidence-backed acceptance.
</p>

<p align="center">
  English | <a href="README.zh-CN.md">简体中文</a>
</p>

# TestKit

TestKit packages repeatable, reviewable testing workflows as [Agent Skills](https://agentskills.io/) for Claude Code, Codex, and other compatible agents. It connects current requirements to traceable execution evidence across test design, automation, diagnosis, defect verification, and acceptance.

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

TestSpec and execution skills depend on shared directories and should be installed as part of the full plugin. See the [installation guide](docs/installation.md) for compatibility, updates, Python dependencies, and the `npx skills` option.

Once installed, describe your task in natural language:

```text
Design test cases from this PRD and export them to Excel.
Import this YApi project and run API tests after login.
Run these login cases on Android, iOS, and Web.
Find the cause of this request timeout in the logs.
Turn this defect recording into a bug draft with timestamped evidence.
Check which items in the frozen scope lack evidence for acceptance.
```

> [!NOTE]
> TestKit supplies workflows, scripts, and result contracts. It does not bundle devices, browser services, Appium drivers, business accounts, or a target environment. Execution uses host tools that are available and authorized for the task.

## Capabilities

| Goal | Skill | Input and output |
|---|---|---|
| [Requirements and test design](docs/testspec.md) | `testspec-*` | PRD, product answers, and historical cases → analysis, strategy, test points, Excel/XMind cases, and review |
| [API automation](docs/api-test-automation.md) | `api-test-automation` | OpenAPI, Swagger, YApi, Postman, or pytest → workflow execution, generative tests, and normalized results |
| [API artifacts](docs/generate-api-artifacts.md) | `generate-api-artifacts` | Reviewed OpenAPI → Postman Collection, Apifox, and JMeter JMX |
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

### Requirements to reviewed cases

TestSpec starts with the current PRD, product answers, and acceptance rules. Code and historical cases are calibration evidence; they do not override product intent.

```text
testspec-new / testspec-update
  → testspec-analysis
  → testspec-plan (when required)
  → testspec-points
  → testspec-generate
  → testspec-review
  → testspec-publish

Historical cases: testspec-import → PRD alignment → main flow
Code evidence: testspec-code-calibrate → product confirmation → main flow
No-repository Web evidence: web-app-reverse → testspec-new (as needed) → main flow
No-repository app evidence: android-static-app-reverse → testspec-new (as needed) → main flow
Knowledge base: testspec-audit → lifecycle proposal → user confirmation
```

`testspec-code-calibrate` requires explicit authorization and a clear source identity and scope before code inspection. TestSpec uses context schema v2; see the [TestSpec guide](docs/testspec.md) for migration of older changes.

### API definition to test results

```text
OpenAPI / Swagger / YApi / Postman
  → normalized OpenAPI
  ├─ Arazzo: login, variable extraction, business assertions, data, cleanup
  └─ Schemathesis: examples, coverage, fuzzing, stateful tests
  → raw evidence + normalized results
```

Existing pytest tests are a controlled compatibility path: execution is limited to full node IDs in a source manifest and checks the bound source and configuration. They complement Arazzo and Schemathesis for complex Python or legacy cases.

### Execution to acceptance

Freeze source material, target build, environment, and checks before execution. Record attempts and raw evidence, then use `test-acceptance` to assess coverage and the verdict for that build. Missing checks, stale evidence, mixed retries, and unresolved cleanup remain visible.

## Operating boundaries

- Code scanning, write-method or destructive tests, TestLib changes, and external issue submission require explicit authorization.
- API keys, passwords, and tokens are supplied through environment variables; persisted results and public fixtures are redacted and checked for privacy.
- Fuzzing, stateful, and write-method tests run only in a confirmed isolated environment.
- Android static analysis applies only to authorized targets; it does not include bypasses or runtime attacks.
- Historical cases enter TestLib only after alignment with the current PRD and review.

## Documentation and support

- [Installation and updates](docs/installation.md)
- [TestSpec](docs/testspec.md)
- [API automation](docs/api-test-automation.md) and [API artifacts](docs/generate-api-artifacts.md)
- [Android, iOS, and Web testing](docs/app-test.md) and [repository-free Web analysis](docs/web-app-reverse.md)
- [Log diagnosis](docs/log-analysis.md), [SQL review](docs/sql-safety-review.md), and [Android static analysis](docs/android-static-app-reverse.md)
- [Defect verification](docs/defect-verification.md) and [video to issue](docs/video-to-issue.md)
- [Test acceptance](docs/test-acceptance.md) and [execution contract](skills/_test-run-shared/references/execution-contract.md)
- [Development and validation](docs/development.md)

For questions, bugs, and suggestions, use [GitHub Issues](https://github.com/winhok/testkit/issues). The project is maintained by [winhok](https://github.com/winhok).

## Development and contribution

Run the unified checks after installing the repository dependencies:

```bash
python scripts/test_all.py
```

This covers plugin packaging, cross-skill contracts, synthetic eval definitions, and unit tests. Live evaluations against devices, browsers, or public APIs require separate setup and evidence; offline checks do not establish external acceptance. Read the [development guide](docs/development.md) before contributing.

## License

MIT
