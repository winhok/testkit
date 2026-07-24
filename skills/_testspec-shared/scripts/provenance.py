#!/usr/bin/env python3
"""Shared TestSpec provenance classification."""
from __future__ import annotations

from typing import Any


ALLOWED_PAIRS = {
    ("testspec-native", "provisional"),
    ("testspec-native", "verified"),
    ("legacy-import", "unverified"),
}


def classify_provenance(origin: Any, trust: Any) -> str:
    """Return a stable provenance state for an artifact or case."""
    if not isinstance(origin, dict) or not isinstance(trust, dict):
        return "unknown"
    pair = (origin.get("kind"), trust.get("status"))
    if pair not in ALLOWED_PAIRS:
        return "invalid"
    return f"{pair[0]}/{pair[1]}"
