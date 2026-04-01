"""Pytest test file for API spec execution. Works with conftest.py fixtures."""
from engine import execute_case


def test_case(project_spec, case_spec, http_client, env_vars, flow_registry):
    result = execute_case(
        project_spec, case_spec,
        client=http_client, env=env_vars, flows=flow_registry,
    )
    assert result.status == "passed", (
        f"[{result.case_id}] {result.case_name} failed at step '{result.failed_step}': {result.reason}"
    )
