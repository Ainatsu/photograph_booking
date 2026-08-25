"""评估多模态 RAG 排序的确定性表现并输出 JSON 报告。"""

import argparse
import json
from pathlib import Path

from backend.app.services.ai_multimodal_evaluation_service import (
    evaluate_multimodal_cases,
    load_multimodal_cases,
)


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "evals" / "multimodal_rag_golden.jsonl"


def main() -> int:
    """命令行入口：跑多模态金标准评估，低于阈值时以非零码退出。"""
    parser = argparse.ArgumentParser(description="Evaluate deterministic multimodal RAG ranking")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    args = parser.parse_args()
    report = evaluate_multimodal_cases(load_multimodal_cases(args.dataset))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["accuracy"] >= args.min_accuracy else 1


if __name__ == "__main__":
    raise SystemExit(main())
