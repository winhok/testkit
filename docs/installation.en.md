# Install TestKit

English | [简体中文](installation.md)

Use the full plugin for Claude Code and Codex. TestSpec, PerfSpec, and execution
skills depend on shared directories and are not standalone packages.
This guide documents the repository's installation paths; CLI availability and
managed-workspace policies depend on your host.

## Codex

Run in your terminal:

```bash
codex plugin marketplace add winhok/testkit
codex plugin add testkit@testkit-marketplace
codex plugin marketplace list
codex plugin list
```

The plugin name is `testkit`; its Codex marketplace is `testkit-marketplace`.
Managed workspaces may restrict plugin installation or visibility. TestKit is
a skill-only plugin and does not require an external app connection.

To refresh the marketplace snapshot:

```bash
codex plugin marketplace upgrade testkit-marketplace
codex plugin list --available --json
```

Compare installed and available versions. Refreshing a marketplace snapshot
does not by itself prove that an installed plugin has been upgraded. Consult
your installed CLI's help for supported plugin replacement or update actions.

## Claude Code

Run inside Claude Code:

```text
/plugin marketplace add winhok/testkit
/plugin install testkit@testkit
/reload-plugins
```

Both the plugin and Claude Code marketplace are named `testkit`.
For updates, run in your terminal:

```bash
claude plugin marketplace update testkit
claude plugin update testkit@testkit
```

Then restart Claude Code or run `/reload-plugins`.

## Standalone skills

These five skills are self-contained:

- `api-test-automation`
- `generate-api-artifacts`
- `log-analysis`
- `sql-safety-review`
- `android-static-app-reverse`

With a GitHub CLI installation that supports `gh skill`, preview before installing:

```bash
gh skill preview winhok/testkit api-test-automation
gh skill install winhok/testkit api-test-automation
```

Select the agent and project scope interactively. For automation, specify them
explicitly and pin a full commit SHA:

```bash
gh skill install winhok/testkit api-test-automation \
  --agent universal \
  --scope project \
  --pin <full-commit-sha>
```

Check for updates before applying them:

```bash
gh skill update --all --dry-run
gh skill update api-test-automation
```

Alternatively, with Node.js 18 or later:

```bash
npx skills add winhok/testkit --list
npx skills add winhok/testkit --skill api-test-automation
```

Review the agent, skill, and destination before accepting installation. Use
project scope unless you intentionally want a user-wide installation.

## Preserve shared dependencies

Do not use `gh skill install --all` or `npx skills add --skill '*'` as a substitute
for the full TestKit plugin. For other clients, copy all contents of `skills/`
into the client's skills directory, retaining sibling directories including:

```text
<client skills directory>/
├── _testspec-shared/
├── _test-run-shared/
├── _perfspec-shared/
├── testspec-new/
├── perfspec-analysis/
├── test-acceptance/
└── ... other skills
```

Check existing skills and local edits before copying over them. Device tools,
browser services, JMeter, Locust, k6, accounts, and target environments are
provided separately by the host when needed.

## Python dependencies

Plugin installation provides skills; Python script dependencies require separate
setup. From a local TestKit checkout, use a project virtual environment:

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip check
```

Or use Python's built-in virtual environment support with a compatible Python:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Avoid installing these dependencies into system Python. They support Excel
export, YAML/OpenAPI parsing, generative API testing, and pytest compatibility.

## Verify and try a task

From the repository root, check plugin packaging:

```bash
python scripts/test_all.py --only packaging
```

For all offline checks:

```bash
python scripts/test_all.py
```

These checks do not establish real-device or live-service acceptance.
For a first design task, try the [coupon showcase](../examples/coupon-discount/README.md).
For test groups and maintenance details, see the [development guide](development.md)
(Simplified Chinese).
