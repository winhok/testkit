"""Canonical project.yaml template used by bootstrap scripts."""
from __future__ import annotations


def build_project_spec(project_name: str) -> dict:
    return {
        "project": {
            "name": project_name,
            "base_url": "${ENV.BASE_URL}",
            "vars": {},
            "defaults": {"headers": {"Content-Type": "application/json"}},
            "report": {
                "allure_results_dir": "allure-results",
                "structured_results_file": "reports/results.json",
                "cases_dir": "cases",
                "flows_dir": "flows",
            },
        }
    }
