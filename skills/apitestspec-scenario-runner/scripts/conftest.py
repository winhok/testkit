"""Pytest conftest for API spec runner. Drop into your test project root."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from engine import HttpClient
from loaders import discover_case_files, discover_flows, load_case_file, load_project_spec


def _load_env(project_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    dotenv = project_dir / "config" / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--project", default=None, help="Path to project.yaml")
    parser.addoption("--tag", action="append", default=[], help="Filter by tag")


@pytest.fixture(scope="session")
def project_spec(request: pytest.FixtureRequest):
    p = request.config.getoption("--project")
    if not p:
        pytest.skip("--project not specified")
    return load_project_spec(Path(p).resolve())


@pytest.fixture(scope="session")
def env_vars(project_spec, request):
    p = Path(request.config.getoption("--project")).resolve()
    return _load_env(p.parent)


@pytest.fixture(scope="session")
def http_client(project_spec, env_vars):
    url = env_vars.get("BASE_URL", project_spec.base_url)
    return HttpClient(url)


@pytest.fixture(scope="session")
def flow_registry(project_spec, request):
    p = Path(request.config.getoption("--project")).resolve()
    return discover_flows(p, project_spec)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case_spec" not in metafunc.fixturenames:
        return
    p = metafunc.config.getoption("--project")
    if not p:
        return
    project_path = Path(p).resolve()
    project = load_project_spec(project_path)
    tags = metafunc.config.getoption("--tag") or []
    items = []
    for cf in discover_case_files(project_path, project):
        doc = load_case_file(cf)
        for c in doc.cases:
            if tags and not any(t in c.tags for t in tags):
                continue
            items.append(pytest.param(c, id=c.id))
    metafunc.parametrize("case_spec", items)
