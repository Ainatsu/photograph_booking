"""AI 意图识别评估服务：加载金标准用例并批量评估意图识别效果。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from backend.app.services.ai_orchestrator_service import recognize_intent


EVALUATION_SCHEMA_VERSION = "agent_eval_v1"


def load_golden_cases(path: str | Path) -> list[dict[str, Any]]:
    """从 JSONL 文件加载金标准评估用例。"""
    cases = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            case = json.loads(stripped)
            case.setdefault("id", f"line-{line_number}")
            cases.append(case)
    return cases


def evaluate_intent_cases(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """批量评估意图识别用例并汇总准确率。"""
    results = [evaluate_intent_case(case) for case in cases]
    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "results": results,
    }


def evaluate_intent_case(case: dict[str, Any]) -> dict[str, Any]:
    """评估单个意图识别用例，返回与期望的差异明细。"""
    actual = recognize_intent(
        case.get("input") or "",
        case.get("attachments") or [],
    ).as_dict()
    expected = case.get("expected") or {}
    mismatches = []

    for field in ("intent", "route", "requires_confirmation"):
        if field in expected and actual.get(field) != expected[field]:
            mismatches.append({
                "field": field,
                "expected": expected[field],
                "actual": actual.get(field),
            })

    expected_slots = expected.get("slots") or {}
    actual_slots = actual.get("slots") or {}
    for key, expected_value in expected_slots.items():
        actual_value = actual_slots.get(key)
        if isinstance(expected_value, list) and isinstance(actual_value, list):
            matched = all(item in actual_value for item in expected_value)
        elif isinstance(actual_value, list):
            matched = expected_value in actual_value
        else:
            matched = actual_value == expected_value
        if not matched:
            mismatches.append({
                "field": f"slots.{key}",
                "expected": expected_value,
                "actual": actual_value,
            })

    for key in expected.get("forbidden_slots") or []:
        if actual_slots.get(key) not in (None, "", []):
            mismatches.append({
                "field": f"slots.{key}",
                "expected": "absent",
                "actual": actual_slots.get(key),
            })

    if "missing_slots" in expected:
        expected_missing = set(expected["missing_slots"])
        actual_missing = set(actual.get("missing_slots") or [])
        if expected_missing != actual_missing:
            mismatches.append({
                "field": "missing_slots",
                "expected": sorted(expected_missing),
                "actual": sorted(actual_missing),
            })

    return {
        "id": case.get("id"),
        "input": case.get("input"),
        "passed": not mismatches,
        "mismatches": mismatches,
        "actual": actual,
    }
