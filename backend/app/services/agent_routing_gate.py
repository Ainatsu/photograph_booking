"""统一 Agent 决策层的灰度开关（阶段C §4-C.1、§4-C.2、§8）。

阶段B 只有一个全局 `AGENT_ROUTING_MODE`，要么全量要么不开，没法"先灰度一小部分流量"。
这里把它拆成两个模式加一个比例：

- `AGENT_ROUTING_MODE`：命中灰度时生效的**目标模式**（shadow / tool_loop）；
- `AGENT_ROUTING_BASELINE_MODE`：没命中时的模式，通常是 legacy；
- `AGENT_ROUTING_ROLLOUT_PERCENT`：命中比例，默认 100（等价于阶段B 的全量开关）。

分桶用 sha256 稳定哈希（与 `joint_recommendation_gate` 同一套做法）：同一个用户或会话
在整个灰度期内始终落在同一侧，指标才有可比性；重启进程、多实例部署也不会来回跳。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from backend.app.core.config import settings


ROUTING_ROLLOUT_SCHEMA_VERSION = "agent_routing_rollout_v1"

ROUTING_MODES = ("legacy", "shadow", "tool_loop")
ROLLOUT_UNITS = ("user", "conversation", "global")

RolloutUnit = Literal["user", "conversation", "global"]


@dataclass(frozen=True)
class RoutingRollout:
    """本轮请求的灰度判定结果。

    `mode` 是真正生效的模式，`reason` 说明为什么落在这一侧——灰度期排查"这个用户为什么
    没走新链路"时，只看这一个字段就够，不用回去猜配置。
    """

    mode: str
    target_mode: str
    baseline_mode: str
    unit: str
    percent: int
    in_rollout: bool
    reason: str
    identity: str | None = None
    bucket: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """将灰度判定结果序列化为字典。"""
        return {
            "schema_version": ROUTING_ROLLOUT_SCHEMA_VERSION,
            "mode": self.mode,
            "target_mode": self.target_mode,
            "baseline_mode": self.baseline_mode,
            "unit": self.unit,
            "percent": self.percent,
            "in_rollout": self.in_rollout,
            "reason": self.reason,
            "bucket": self.bucket,
        }


def normalize_routing_mode(value: str | None, *, default: str = "legacy") -> str:
    """归一化路由模式，非法值回退到默认值。"""
    mode = (value or "").strip().lower()
    return mode if mode in ROUTING_MODES else default


def normalize_rollout_unit(value: str | None) -> str:
    """归一化灰度分桶单位，非法值回退为 user。"""
    unit = (value or "").strip().lower()
    return unit if unit in ROLLOUT_UNITS else "user"


def normalize_rollout_percent(value: Any) -> int:
    """归一化灰度比例，非法值返回 0。"""
    try:
        percent = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, percent))


def rollout_bucket(identity: str) -> int:
    """把身份稳定映射到 [0, 100)。"""
    digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) % 100


def _id_set(raw: str | None) -> set[str]:
    """把逗号分隔的配置串解析为 ID 集合。"""
    return {item.strip() for item in (raw or "").split(",") if item.strip()}


def resolve_routing_rollout(
    *,
    user_id: int | str | None = None,
    conversation_id: int | str | None = None,
) -> RoutingRollout:
    """决定这一轮用哪个 routing mode。

    优先级：黑名单 → 白名单 → 目标模式是否与基线相同 → 比例分桶。
    黑名单排在最前，是为了让"这个账号先别进新链路"这类临时止血立刻生效（§8）。
    """
    target_mode = normalize_routing_mode(settings.AGENT_ROUTING_MODE)
    baseline_mode = normalize_routing_mode(settings.AGENT_ROUTING_BASELINE_MODE)
    unit = normalize_rollout_unit(settings.AGENT_ROUTING_ROLLOUT_UNIT)
    percent = normalize_rollout_percent(settings.AGENT_ROUTING_ROLLOUT_PERCENT)

    def outcome(*, in_rollout: bool, reason: str, bucket: int | None, identity: str | None) -> RoutingRollout:
        return RoutingRollout(
            mode=target_mode if in_rollout else baseline_mode,
            target_mode=target_mode,
            baseline_mode=baseline_mode,
            unit=unit,
            percent=percent,
            in_rollout=in_rollout,
            reason=reason,
            identity=identity,
            bucket=bucket,
        )

    user_key = str(user_id) if user_id not in (None, "") else None
    if user_key and user_key in _id_set(settings.AGENT_ROUTING_ROLLOUT_DENYLIST):
        return outcome(in_rollout=False, reason="denylist", bucket=None, identity=user_key)
    if user_key and user_key in _id_set(settings.AGENT_ROUTING_ROLLOUT_ALLOWLIST):
        return outcome(in_rollout=True, reason="allowlist", bucket=None, identity=user_key)

    # 目标模式和基线一样时不必分桶：两侧结果相同，还能少一次哈希。
    if target_mode == baseline_mode:
        return outcome(in_rollout=True, reason="target_is_baseline", bucket=None, identity=None)
    if percent >= 100:
        return outcome(in_rollout=True, reason="percent_full", bucket=None, identity=None)
    if percent <= 0:
        return outcome(in_rollout=False, reason="percent_zero", bucket=None, identity=None)

    if unit == "global":
        # 比例在 global 单位下没有分桶对象：要么全开要么全关，交由上面两个分支处理。
        return outcome(in_rollout=False, reason="percent_zero", bucket=None, identity=None)

    raw_identity = conversation_id if unit == "conversation" else user_id
    identity = f"{unit}:{raw_identity}" if raw_identity not in (None, "") else f"{unit}:anonymous"
    bucket = rollout_bucket(identity)
    in_rollout = bucket < percent
    return outcome(
        in_rollout=in_rollout,
        reason="bucket_in" if in_rollout else "bucket_out",
        bucket=bucket,
        identity=identity,
    )


def resolve_routing_mode(
    *,
    user_id: int | str | None = None,
    conversation_id: int | str | None = None,
) -> str:
    """返回本轮实际生效的路由模式。"""
    return resolve_routing_rollout(user_id=user_id, conversation_id=conversation_id).mode
