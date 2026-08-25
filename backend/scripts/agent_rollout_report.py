"""阶段C 灰度报告 CLI（§4-C.2、§4-C.3、§4-C.5）。

用法：
    python -m backend.scripts.agent_rollout_report --days 7
    python -m backend.scripts.agent_rollout_report --dataset backend/evals/agent_phase_c_tool_selection.jsonl

不调用任何 LLM：只读已落库的 AgentTrace 与消息元数据。给出阈值参数时会用退出码
表达"这批灰度指标是否达标"，可以直接挂进 CI 或发布前检查。
"""

import argparse
import json

from backend.app.core.database import SessionLocal

# 模型没有统一的注册入口（见 backend/migrations/env.py 的同款写法）：
# 脚本里只 import AgentTrace 会让 SQLAlchemy 在配置 mapper 时找不到 Payment 之类的
# 关联类，所以这里显式把整张模型图导进来。
from backend.app.models import (  # noqa: F401
    ai_conversation,
    ai_production,
    ai_resource,
    analytics,
    chat_read_state,
    comment,
    favorite,
    follow,
    identity_verification,
    like,
    message,
    notification,
    order,
    order_delivery,
    order_dispute,
    order_event,
    order_reschedule,
    payment,
    photographer,
    photographer_application,
    project,
    recommendation,
    user,
)
from backend.app.services.ai_evaluation_service import load_golden_cases
from backend.app.services.ai_offline_eval_service import (
    evaluate_rules_tool_selection,
    replay_agent_traces,
)


def _check_thresholds(report: dict, args: argparse.Namespace) -> list[str]:
    """返回未达标的项；空列表表示全部通过。"""
    metrics = report.get("metrics") or {}
    violations: list[str] = []
    if metrics.get("tool_calls") and metrics["tool_success_rate"] < args.min_tool_success:
        violations.append(
            f"tool_success_rate={metrics['tool_success_rate']} < {args.min_tool_success}"
        )
    if metrics.get("tool_calls") and metrics["no_result_rate"] > args.max_no_result:
        violations.append(f"no_result_rate={metrics['no_result_rate']} > {args.max_no_result}")
    if metrics.get("tool_proposals") and metrics["wrong_tool_rate"] > args.max_wrong_tool:
        violations.append(f"wrong_tool_rate={metrics['wrong_tool_rate']} > {args.max_wrong_tool}")
    if (
        metrics.get("recommendation_turns")
        and metrics["repeat_recommendation_rate"] > args.max_repeat_recommendation
    ):
        violations.append(
            f"repeat_recommendation_rate={metrics['repeat_recommendation_rate']}"
            f" > {args.max_repeat_recommendation}"
        )
    # 写操作拦截率必须是 1.0：低于 1 说明有写工具没走既有确认流程（§5.2）。
    if metrics.get("write_proposals") and metrics["write_block_rate"] < args.min_write_block:
        violations.append(f"write_block_rate={metrics['write_block_rate']} < {args.min_write_block}")
    return violations


def main() -> int:
    """命令行入口：回放 Agent 灰度 trace 生成报告，未达标时以非零码退出。"""
    parser = argparse.ArgumentParser(description="Agent rollout metrics and offline evaluation")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=None, help="只回放最近 N 条 trace")
    parser.add_argument(
        "--with-text",
        action="store_true",
        help="分歧样本里带上截断后的用户原文（默认不输出）",
    )
    parser.add_argument("--dataset", default=None, help="额外跑一次规则选工具的固定集评估")
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    parser.add_argument("--min-tool-success", type=float, default=0.90)
    parser.add_argument("--max-no-result", type=float, default=0.20)
    parser.add_argument("--max-wrong-tool", type=float, default=0.05)
    parser.add_argument("--max-repeat-recommendation", type=float, default=0.05)
    parser.add_argument("--min-write-block", type=float, default=1.0)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = replay_agent_traces(
            db,
            days=args.days,
            limit=args.limit,
            include_text=args.with_text,
        )
    finally:
        db.close()

    exit_code = 0
    violations = _check_thresholds(report, args)
    if violations:
        report["violations"] = violations
        exit_code = 1

    if args.dataset:
        dataset_report = evaluate_rules_tool_selection(load_golden_cases(args.dataset))
        report["rules_tool_selection"] = dataset_report
        if dataset_report["total"] and dataset_report["accuracy"] < args.min_accuracy:
            report.setdefault("violations", []).append(
                f"rules_tool_selection.accuracy={dataset_report['accuracy']} < {args.min_accuracy}"
            )
            exit_code = 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
