"""资源检索服务：抽取检索条件，并以混合语义/关键词/视觉信号检索摄影师、作品与套餐。"""

import json
import math
import re
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.services.ai_domain_synonyms import (
    MAKEUP_TERMS,
    detect_style_terms,
    matches_term as matches_domain_term,
    normalize_terms,
)
from backend.app.services.ai_embedding_service import (
    cosine_similarity,
    pgvector_candidate_scores,
    query_embedding,
)
from backend.app.services.ai_resource_context_service import (
    CONTEXT_SCHEMA_VERSION,
)
from backend.app.services.ai_resource_index_service import load_or_rebuild_resource_documents
from backend.app.services.ai_multimodal_embedding_service import (
    image_candidate_scores,
    visual_query_embedding,
)


GENERIC_QUERY_TERMS = {
    "一下",
    "上架",
    "什么",
    "作品",
    "哪些",
    "如何",
    "套餐",
    "帮我",
    "想拍",
    "想要",
    "平台",
    "怎么",
    "怎么样",
    "找",
    "推荐",
    "搜索",
    "摄影",
    "摄影师",
    "方案",
    "有没有",
    "本网站",
    "查",
    "查找",
    "关于",
    "相关",
    "看看",
    "类似",
    "给我",
    "网站",
    "能否",
    "请帮",
    "请问",
    "资源",
    "选择",
    "预约",
    "适合",
    "风格",
    "站内",
}

# 对话控制词：只表达指代和对上一轮结果的反馈，不是资源特征。
# 这些词曾被当成正向检索关键词（“不太满意”“个我不太”），
# 把真实备选挤出相关性门槛，最终导致 candidate_counts 为 0。
# 注意不要收录“换成”：它会把“换成都的”削成“都的”，反而丢掉城市。
CONVERSATION_CONTROL_TERMS = (
    "这个",
    "这条",
    "这位",
    "这家",
    "那个",
    "那位",
    "刚才",
    "刚刚",
    "上一个",
    "上个",
    "上面",
    "下一个",
    "另一个",
    "另外",
    "再来",
    "再给",
    "重新",
    "还有",
    "别的",
    "其他",
    "其它",
    "不太满意",
    "不满意",
    "满意",
    "不喜欢",
    "喜欢",
    "不合适",
    "合适",
    "不行",
    "不太行",
    "不够",
    "换一个",
    "换一批",
    "换一换",
    "换个",
    "一个",
    "一位",
    "一名",
    "算了",
    "可以吗",
    "行吗",
)

GENERIC_QUERY_TERMS.update(CONVERSATION_CONTROL_TERMS)

GENERIC_QUERY_FRAGMENTS = tuple(sorted(GENERIC_QUERY_TERMS, key=len, reverse=True))

RESOURCE_SEARCH_TERMS = (
    "推荐",
    "找",
    "搜索",
    "有没有",
    "相关",
    "类似",
    "作品",
    "摄影师",
    "套餐",
    "方案",
    "资源",
)

REFERENCE_KEYS = ("photographers", "portfolio_items", "packages")

# 资源类型词表：ai_orchestrator_service 的规则分类器直接复用本表，不要再维护第二份。
RESOURCE_TYPE_TERMS = {
    "photographers": (
        "摄影师",
        "摄影老师",
        "拍摄老师",
        "跟拍师",
        "摄影团队",
    ),
    "portfolio_items": (
        "作品",
        "样片",
        "案例",
        "客片",
        "成片",
        "照片",
        "图片",
        "图集",
        "片子",
    ),
    "packages": (
        "套餐",
        "方案",
        "服务包",
        "报价",
        "价格",
        "价位",
        "多少钱",
        "费用",
        "收费",
    ),
    "projects": (
        "企划",
        "拍摄企划",
        "拍摄需求",
        "拍摄计划",
        "任务",
        "拍摄任务",
        "应邀任务",
        "企划大厅",
    ),
}

RESOURCE_TYPE_LABELS = {
    "photographers": "摄影师",
    "portfolio_items": "作品",
    "packages": "套餐",
    "projects": "企划",
}

# 预算抽取语境：出现其中任一词时，原文里的数字才可能是金额。
BUDGET_CONTEXT_TERMS = (
    "预算",
    "价格",
    "价位",
    "报价",
    "费用",
    "收费",
    "多少钱",
    "以内",
    "以下",
    "不超过",
    "不能超过",
    "左右",
    "上下",
)

# 紧跟在数字后面的单位：出现这些说明是日期、时长、张数等，不是金额。
NON_MONEY_UNIT_SUFFIXES = (
    "月",
    "日",
    "号",
    "点",
    "分",
    "秒",
    "张",
    "人",
    "位",
    "名",
    "天",
    "周",
    "年",
    "岁",
    "组",
    "套",
    "小时",
    "公里",
    "km",
    "%",
)

MONEY_UNIT_SUFFIXES = ("元", "块", "¥", "￥", "rmb", "RMB", "内", "以内", "以下", "封顶")


class RetrievalCriteria(BaseModel):
    """资源检索条件模型，承载文本、关键词、城市、预算、风格等过滤条件。"""
    model_config = ConfigDict(extra="forbid")

    text: str
    terms: list[str] = Field(default_factory=list)
    location: str | None = None
    budget_max: float | None = None
    owner_user_id: int | None = None
    owner_display_name: str | None = None
    resource_types: list[str] | None = None
    style_terms: list[str] | None = None
    requires_makeup: bool = False
    package_includes: list[str] | None = None
    limit: int = 3
    # 多轮检索审计：本轮由上游意图显式确认的字段、从上一轮继承的字段，
    # 以及本轮必须排除的资源 ID。
    explicit_fields: list[str] = Field(default_factory=list)
    inherited_fields: list[str] = Field(default_factory=list)
    exclude_resource_ids: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """将条件序列化为可 JSON 输出的字典。"""
        payload = self.model_dump(mode="json")
        payload["city"] = self.location
        payload["resource_types"] = self.resource_types or []
        payload["style_terms"] = self.style_terms or []
        payload["package_includes"] = self.package_includes or []
        return payload


# 允许上游（意图槽位 / 上一轮 search_context）直接指定的结构化条件字段。
# 只放开这些字段：package_includes 之类由规则从原文猜出来的值会变成过强的硬过滤。
OVERRIDABLE_CRITERIA_FIELDS = (
    "location",
    "budget_max",
    "style_terms",
    "requires_makeup",
    "owner_user_id",
    "owner_display_name",
)

_EMPTY_CRITERIA_VALUES = (None, "", [], {}, False)


def should_retrieve(content: str | None) -> bool:
    """所有非空用户消息都触发数据库检索，不再依赖关键词白名单。"""
    text = (content or "").strip()
    return bool(text)


def strip_conversation_control_terms(content: str | None) -> str:
    """移除“这个 / 刚才 / 不太满意 / 换一个”等对话控制词，只留下资源特征。"""
    normalized = content or ""
    for fragment in GENERIC_QUERY_FRAGMENTS:
        normalized = normalized.replace(fragment, " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _apply_criteria_overrides(
    criteria: RetrievalCriteria,
    overrides: dict[str, Any] | None,
    *,
    audit_field: str,
    override_existing: bool,
) -> None:
    """把上游给定的结构化条件写入 criteria。

    override_existing=True 用于本轮意图已确认的条件：它比检索器从原文的再次抽取更可信。
    override_existing=False 用于上一轮继承的条件：只回填本轮没有的字段。
    """
    if not overrides:
        return
    audit = getattr(criteria, audit_field)
    for field in OVERRIDABLE_CRITERIA_FIELDS:
        value = overrides.get(field)
        if value in _EMPTY_CRITERIA_VALUES:
            continue
        if field == "style_terms":
            value = normalize_terms(value)
            if not value:
                continue
        if not override_existing and getattr(criteria, field) not in _EMPTY_CRITERIA_VALUES:
            continue
        if getattr(criteria, field) == value:
            continue
        setattr(criteria, field, value)
        if field not in audit:
            audit.append(field)


def _semantic_query_text(criteria: RetrievalCriteria, content: str | None) -> str:
    """用清理过控制词的原文加上结构化条件做语义检索，避免“不太满意”参与召回。"""
    parts: list[str] = [strip_conversation_control_terms(content), criteria.location or ""]
    parts.extend(criteria.style_terms or [])
    parts.extend(criteria.package_includes or [])
    if criteria.budget_max is not None:
        parts.append(f"预算{criteria.budget_max:g}元内")
    text = " ".join(part for part in parts if part).strip()
    return text or (content or "")


def retrieve_references(
    db: Session,
    content: str | None,
    limit: int = 3,
    resource_types: list[str] | tuple[str, ...] | None = None,
    vision_analysis: dict[str, Any] | None = None,
    image_attachments: list[dict[str, Any]] | None = None,
    criteria_overrides: dict[str, Any] | None = None,
    inherited_criteria: dict[str, Any] | None = None,
    exclude_resource_ids: list[str] | tuple[str, ...] | None = None,
    soft_style_resource_types: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any] | None:
    """执行资源检索主流程，返回命中引用、条件与诊断信息。"""
    if not should_retrieve(content):
        return None

    started_at = perf_counter()
    documents = load_or_rebuild_resource_documents(db)
    conversion_scores = _owner_conversion_scores(db)
    for values in documents.values():
        for document in values:
            document["conversion_score"] = conversion_scores.get(
                int(document.get("owner_user_id") or 0),
                settings.AI_CONVERSION_PRIOR_RATE,
            )
    criteria = _extract_criteria(content or "", documents)
    # 顺序即优先级：本轮意图确认的条件 > 检索器从原文的抽取 > 上一轮继承的条件。
    _apply_criteria_overrides(
        criteria,
        criteria_overrides,
        audit_field="explicit_fields",
        override_existing=True,
    )
    _apply_criteria_overrides(
        criteria,
        inherited_criteria,
        audit_field="inherited_fields",
        override_existing=False,
    )
    criteria.exclude_resource_ids = [
        str(resource_id) for resource_id in exclude_resource_ids or [] if str(resource_id or "").strip()
    ]
    criteria.limit = _effective_limit(content or "", limit)
    resource_keys = _normalize_resource_keys(resource_types) or _select_resource_keys(content or "", criteria)
    criteria.resource_types = list(resource_keys)
    embedding_error = None
    try:
        query_vector, embedding_info = query_embedding(_semantic_query_text(criteria, content))
    except Exception as exc:
        query_vector = None
        embedding_info = {"provider": "fallback", "model": None, "dimensions": 0}
        embedding_error = type(exc).__name__
    visual_vector = None
    visual_info: dict[str, Any] = {"provider": "disabled", "model": None, "dimensions": 0}
    visual_error = None
    if image_attachments or (
        vision_analysis and settings.AI_IMAGE_EMBEDDING_PROVIDER.lower() == "mock"
    ):
        try:
            visual_vector, visual_info = visual_query_embedding(image_attachments, vision_analysis)
        except Exception as exc:
            visual_error = type(exc).__name__
    visual_document_scores, visual_owner_scores = image_candidate_scores(
        db,
        query_vector=visual_vector,
        limit=max(100, criteria.limit * 20),
    )
    native_scores = pgvector_candidate_scores(
        db,
        query_vector=query_vector,
        resource_types=[
            {
                "photographers": "photographer",
                "portfolio_items": "portfolio_item",
                "packages": "package",
            }[key]
            for key in resource_keys
        ],
        limit=max(50, criteria.limit * 10),
    )
    if native_scores:
        for values in documents.values():
            for document in values:
                document["pgvector_score"] = native_scores.get(document.get("document_id"), 0.0)
    if visual_document_scores or visual_owner_scores:
        for values in documents.values():
            for document in values:
                direct_score = visual_document_scores.get(document.get("document_id"), 0.0)
                owner_score = visual_owner_scores.get(document.get("owner_user_id"), 0.0)
                if document.get("resource_type") == "package":
                    document["package_shadow_visual_score"] = direct_score
                # Portfolio fusion must use the actual work image. Owner fallback is
                # useful for photographer/package discovery, but would pollute the
                # independent image-retrieval list with unrelated works by the same owner.
                document["visual_score"] = (
                    direct_score
                    if document.get("resource_type") == "portfolio_item"
                    else direct_score or (owner_score * 0.90)
                )
    raw_references = {
        key: _rank_documents(
            documents[key], criteria, criteria.limit, query_vector,
            image_query=bool(visual_vector),
            soft_style_filter=key in set(soft_style_resource_types or []),
        )
        for key in REFERENCE_KEYS
    }
    # Portfolio search uses two independent ranked lists when an image query is
    # available. This avoids comparing raw SigLIP cosine scores with text
    # embedding scores and lets textual refinements influence the fusion safely.
    portfolio_rrf = None
    if "portfolio_items" in resource_keys and visual_vector:
        portfolio_rrf = _rank_portfolio_rrf(
            documents["portfolio_items"], criteria, criteria.limit,
            query_vector, content=content or "",
        )
        raw_references["portfolio_items"] = portfolio_rrf["items"]
    package_rrf_shadow = None
    if "packages" in resource_keys and visual_vector:
        package_rrf_shadow = _rank_portfolio_rrf(
            documents["packages"], criteria, criteria.limit,
            query_vector, content=content or "",
            visual_score_key="package_shadow_visual_score",
            resource_label="package",
        )
        package_image_candidates = (package_rrf_shadow.get("candidate_counts") or {}).get("image", 0)
        if settings.AI_PACKAGE_IMAGE_SEARCH_ENABLED and package_image_candidates:
            raw_references["packages"] = package_rrf_shadow["items"]
    references = _filter_references(raw_references, resource_keys)
    diagnostics = {
        "document_counts": {
            key: len(documents.get(key) or [])
            for key in REFERENCE_KEYS
        },
        "candidate_counts": {
            key: len(raw_references.get(key) or [])
            for key in REFERENCE_KEYS
        },
        "result_counts": {
            key: len(references.get(key) or [])
            for key in REFERENCE_KEYS
        },
        "latency_ms": round((perf_counter() - started_at) * 1000),
        "retrieval_mode": "multimodal" if visual_vector else ("hybrid" if query_vector else "keyword"),
        "excluded_resource_ids": list(criteria.exclude_resource_ids),
        "explicit_fields": list(criteria.explicit_fields),
        "inherited_fields": list(criteria.inherited_fields),
        "semantic_backend": "pgvector" if native_scores else ("python_cosine" if query_vector else "disabled"),
        "embedding": {
            **embedding_info,
            "error": embedding_error,
        },
        "multimodal": {
            **visual_info,
            "enabled": bool(visual_vector),
            "error": visual_error,
            "image_weight": settings.AI_MULTIMODAL_IMAGE_WEIGHT,
            "ranking_mode": "image_primary" if visual_vector else None,
            "effective_visual_weight": (
                settings.AI_IMAGE_SEARCH_VISUAL_WEIGHT if visual_vector else 0.0
            ),
            "matched_portfolio_documents": len(visual_document_scores),
            "matched_owners": len(visual_owner_scores),
            "fusion": "weighted_rrf" if portfolio_rrf else None,
            "fusion_weights": portfolio_rrf.get("weights") if portfolio_rrf else None,
            "fusion_candidate_counts": portfolio_rrf.get("candidate_counts") if portfolio_rrf else None,
            # Pure SigLIP order for debugging retrieval quality before text/RRF reranking.
            "siglip_top_10": portfolio_rrf.get("siglip_top_10") if portfolio_rrf else [],
            "package_shadow": {
                "enabled": bool(package_rrf_shadow),
                "candidate_counts": package_rrf_shadow.get("candidate_counts") if package_rrf_shadow else None,
                "weights": package_rrf_shadow.get("weights") if package_rrf_shadow else None,
                "siglip_top_10": package_rrf_shadow.get("siglip_top_10") if package_rrf_shadow else [],
                "ranked_ids": [
                    str(item.get("id")) for item in (package_rrf_shadow or {}).get("items", [])
                ],
                "legacy_ranked_ids": [
                    str(item.get("id")) for item in raw_references.get("packages", [])
                ] if package_rrf_shadow else [],
            },
            "package_multimodal": {
                "enabled": bool(package_rrf_shadow),
                "online_enabled": bool(
                    settings.AI_PACKAGE_IMAGE_SEARCH_ENABLED
                    and package_rrf_shadow
                    and (package_rrf_shadow.get("candidate_counts") or {}).get("image", 0)
                ),
                "image_candidates": (package_rrf_shadow or {}).get("candidate_counts", {}).get("image", 0),
                "text_candidates": (package_rrf_shadow or {}).get("candidate_counts", {}).get("text", 0),
                "union_candidates": (package_rrf_shadow or {}).get("candidate_counts", {}).get("union", 0),
                "fused_results": len((package_rrf_shadow or {}).get("items", [])),
                "matched_samples": len((package_rrf_shadow or {}).get("siglip_top_10", [])),
            },
        },
        "score_weights": {
            "semantic": settings.AI_HYBRID_SEMANTIC_WEIGHT,
            "keyword": settings.AI_HYBRID_KEYWORD_WEIGHT,
            "business": settings.AI_HYBRID_BUSINESS_WEIGHT,
            "quality": settings.AI_HYBRID_QUALITY_WEIGHT,
            "freshness": settings.AI_HYBRID_FRESHNESS_WEIGHT,
        },
        "image_search_weights": {
            "visual": settings.AI_IMAGE_SEARCH_VISUAL_WEIGHT,
            "text": settings.AI_IMAGE_SEARCH_TEXT_WEIGHT,
            "keyword": settings.AI_IMAGE_SEARCH_KEYWORD_WEIGHT,
            "business": settings.AI_IMAGE_SEARCH_BUSINESS_WEIGHT,
            "quality": settings.AI_IMAGE_SEARCH_QUALITY_WEIGHT,
            "freshness": settings.AI_IMAGE_SEARCH_FRESHNESS_WEIGHT,
        },
        "conversion_feedback": {
            "owners_scored": len(conversion_scores),
            "prior_rate": settings.AI_CONVERSION_PRIOR_RATE,
            "prior_weight": settings.AI_CONVERSION_PRIOR_WEIGHT,
        },
    }

    return {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "criteria": criteria.as_dict(),
        "references": references,
        "diagnostics": diagnostics,
    }


def has_reference_matches(retrieval: dict[str, Any] | None) -> bool:
    """判断检索结果中是否包含有效引用。"""
    references = (retrieval or {}).get("references") or {}
    return any(
        references.get(key)
        for key in REFERENCE_KEYS
    )


def is_resource_search(content: str | None) -> bool:
    """判断文本是否包含资源搜索关键词。"""
    text = (content or "").strip()
    return any(term in text for term in RESOURCE_SEARCH_TERMS)


def describe_criteria(
    criteria: dict[str, Any] | None,
    *,
    include_resource_types: bool = True,
) -> str:
    """把结构化条件描述成一句人话，例如“重庆、婚礼、套餐”。

    只用结构化字段，不拼接 criteria.terms：那里面是原文切出来的 n-gram，
    无结果时会复述出“个我不太”这种错误的“完全匹配关键词”。
    """
    payload = criteria or {}
    parts: list[str] = []
    if payload.get("city"):
        parts.append(str(payload["city"]))
    parts.extend(str(term) for term in payload.get("style_terms") or [] if term)
    if payload.get("budget_max") is not None:
        parts.append(f"预算{float(payload['budget_max']):g}元内")
    if payload.get("requires_makeup"):
        parts.append("含妆造")
    if include_resource_types:
        parts.extend(
            RESOURCE_TYPE_LABELS[key]
            for key in payload.get("resource_types") or []
            if key in RESOURCE_TYPE_LABELS
        )
    unique: list[str] = []
    for part in parts:
        if part and part not in unique:
            unique.append(part)
    return "、".join(unique[:4])


def describe_resource_types(criteria: dict[str, Any] | None) -> str:
    """把请求的资源类型描述成中文标签，例如“作品”“摄影师、套餐”。"""
    labels = [
        RESOURCE_TYPE_LABELS[key]
        for key in (criteria or {}).get("resource_types") or []
        if key in RESOURCE_TYPE_LABELS
    ]
    unique: list[str] = []
    for label in labels:
        if label not in unique:
            unique.append(label)
    return "、".join(unique[:3])


def build_empty_retrieval_prompt(
    retrieval: dict[str, Any] | None,
    *,
    refinement: dict[str, Any] | None = None,
) -> str:
    """无结果时给最终 LLM 的结构化诊断，让它结合真实会话解释，而不是套用固定话术。"""
    criteria = (retrieval or {}).get("criteria") or {}
    diagnostics = (retrieval or {}).get("diagnostics") or {}
    diagnosis = {
        "matched_resources": 0,
        "conditions": {
            "city": criteria.get("city"),
            "style_terms": criteria.get("style_terms") or [],
            "budget_max": criteria.get("budget_max"),
            "requires_makeup": bool(criteria.get("requires_makeup")),
            "resource_types": criteria.get("resource_types") or [],
        },
        "explicit_fields": diagnostics.get("explicit_fields") or [],
        "inherited_fields": diagnostics.get("inherited_fields") or [],
        "excluded_resource_ids": diagnostics.get("excluded_resource_ids") or [],
        "is_refinement": bool(refinement),
        "candidate_counts": diagnostics.get("candidate_counts") or {},
    }
    rules = [
        "本轮平台检索没有任何命中资源，下面是结构化诊断。",
        "你必须承认这一点：不要编造任何资源名称、价格、ID 或档期，也不要推荐 references 之外的资源。",
        "结合完整对话历史说明为什么这次没有结果，并指出可以放宽哪一项条件（城市、预算、风格或时间）。",
        "最多只追问 1 个最关键的条件，禁止输出固定的信息收集清单。",
    ]
    if diagnosis["excluded_resource_ids"]:
        rules.append(
            "用户对上一轮推荐不满意，excluded_resource_ids 里的资源已按要求排除；"
            "请明确说明已经排除了上次推荐的那一个，不要重复推荐，也不要说自己无法换一个。"
        )
    if diagnosis["inherited_fields"]:
        rules.append("conditions 中的条件部分继承自上一轮搜索，请按这些条件解释，不要重新询问用户已经说过的信息。")
    return "".join(rules) + "\n" + json.dumps(diagnosis, ensure_ascii=False)


def build_retrieval_context(retrieval: dict[str, Any] | None) -> str | None:
    """将检索结果构建为交给最终 LLM 的受约束上下文文本。"""
    if not retrieval:
        return None

    payload = {
        "context_schema_version": retrieval.get("context_schema_version", CONTEXT_SCHEMA_VERSION),
        "criteria": retrieval["criteria"],
        "references": retrieval["references"],
    }
    refinement_rules = ""
    if (retrieval.get("criteria") or {}).get("exclude_resource_ids"):
        refinement_rules = (
            "用户对之前推荐过的资源不满意，criteria.exclude_resource_ids 里的资源已经从 references 中排除。"
            "不要再提这些资源，也不要说自己无法换一个，直接介绍本次的新备选，并说明它和上一个的差异。"
        )
    if (retrieval.get("criteria") or {}).get("inherited_fields"):
        refinement_rules += (
            "criteria 中的城市、风格、预算是从上一轮延续下来的条件，回答时按这些条件解释匹配理由。"
        )
    return (
        "平台数据库检索结果如下。你必须遵守："
        "先判断用户当前只要哪一种资源：摄影师、作品或套餐。"
        "用户要摄影师就只从 references.photographers 推荐；用户要作品就只从 references.portfolio_items 推荐；"
        "用户要套餐或方案就只从 references.packages 推荐。"
        "references 里非本次请求类型的列表会被置空；回答和下方可点击链接都只能对应非空的同一类资源。"
        "除非用户明确同时要求多种资源，否则不要在同一次回答里混合输出摄影师、作品和套餐。"
        "如果用户要求的资源类型对应列表不为空，就直接推荐该列表里的真实资源，第一句话用肯定表达，不要否认自己的推荐能力。"
        "如果用户要求的资源类型对应列表为空，不要改推其他类型资源。"
        "如果 criteria.owner_display_name 不为空，回答只能围绕该摄影师名下的资源，不要推荐其他摄影师或其他摄影师的套餐。"
        "如果 criteria.limit 为 1，正文和下方可点击资源都只能推荐 1 个，不要补充第二个或其它备选。"
        "如果 references.packages 只有 1 条，正文也只能推荐这 1 个套餐，不要补充其它套餐。"
        "可以使用 references 中的 user_bio、description、price_label、price_tags、equipment、package_summaries、portfolio_summaries、matched_works 解释匹配理由。"
        "每个具体推荐都必须明确写出 references 中的真实资源名称，并且只能推荐带有 _rag 排名信息的返回项。"
        "_rag 只用于排序与审计，不要向用户展示内部打分、embedding 模型或权重。"
        "推荐内容只能来自这些列表，不能编造其他资源。"
        "如果三个列表都为空，说“暂时没找到完全匹配的上架资源”，并最多追问 1 到 2 个关键条件。"
        "禁止输出固定的六项信息收集清单。\n"
        f"{refinement_rules}"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _select_resource_keys(content: str, criteria: RetrievalCriteria | None = None) -> tuple[str, ...]:
    """根据文本与条件选择本次检索的资源类型。"""
    text = content.strip()
    matched = tuple(
        key
        for key in REFERENCE_KEYS
        if any(term in text for term in RESOURCE_TYPE_TERMS[key])
    )
    if "packages" in matched and not _explicitly_requests_multiple_resource_types(text):
        return ("packages",)
    if "portfolio_items" in matched and "photographers" in matched and not _explicitly_requests_multiple_resource_types(text):
        return ("portfolio_items",)
    if criteria and criteria.owner_user_id and "packages" in matched:
        return ("packages",)
    if matched:
        return matched

    # 用户只表达“推荐/找一下”但没有点明资源时，默认给摄影师。
    return ("photographers",)


def _normalize_resource_keys(resource_types: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """过滤传入的资源类型，只保留支持的键。"""
    if not resource_types:
        return ()
    selected = tuple(key for key in resource_types if key in REFERENCE_KEYS)
    return selected


def _filter_references(
    references: dict[str, list[dict[str, Any]]],
    resource_keys: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    """按资源类型过滤引用，未选中的类型置空。"""
    selected = set(resource_keys)
    return {
        key: references.get(key, []) if key in selected else []
        for key in REFERENCE_KEYS
    }


def _extract_criteria(
    content: str,
    documents: dict[str, list[dict[str, Any]]],
) -> RetrievalCriteria:
    """从用户文本与资源文档中抽取完整检索条件。"""
    terms = _extract_terms(content, documents)
    owner_user_id, owner_display_name = _extract_owner(content, documents)
    return RetrievalCriteria(
        text=content,
        terms=terms,
        location=_extract_location(content, documents),
        budget_max=_extract_budget(content),
        owner_user_id=owner_user_id,
        owner_display_name=owner_display_name,
        style_terms=_extract_style_terms(content, documents),
        requires_makeup=_requires_makeup(content),
        package_includes=_extract_package_includes(content, documents),
    )


def _extract_budget(content: str) -> float | None:
    """只在有金额语境时把数字当预算。

    以前取原文里最大的数字，于是“8月15日下午2点”会被读成预算 15 元、
    “精修30张”会被读成预算 30 元，把真实候选全部过滤掉。
    """
    k_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK](?![a-zA-Z])", content)
    if k_match:
        return float(k_match.group(1)) * 1000

    has_budget_context = any(term in content for term in BUDGET_CONTEXT_TERMS)
    amounts: list[float] = []
    for match in re.finditer(r"(?<!\d)(\d{2,6}(?:\.\d+)?)(?!\d)", content):
        suffix = content[match.end() : match.end() + 4].lstrip()
        if suffix.startswith(NON_MONEY_UNIT_SUFFIXES):
            continue
        if suffix.startswith(MONEY_UNIT_SUFFIXES) or has_budget_context:
            amounts.append(float(match.group(1)))
    return max(amounts) if amounts else None


def _extract_location(content: str, documents: dict[str, list[dict[str, Any]]]) -> str | None:
    """从文本中匹配已知资源城市。"""
    locations = []
    for resource_documents in documents.values():
        for document in resource_documents:
            if document.get("city"):
                locations.append(document["city"])

    for location in sorted(set(locations), key=len, reverse=True):
        if location and location in content:
            return location
        short = _short_location(location)
        if short and short in content:
            return short
    return None


def _extract_terms(content: str, documents: dict[str, list[dict[str, Any]]]) -> list[str]:
    """抽取文本命中的已知词条与查询 n-gram。"""
    known_terms: set[str] = set()
    for resource_documents in documents.values():
        for document in resource_documents:
            known_terms.update(_clean_terms(document.get("tags") or []))
            known_terms.update(_clean_terms(document.get("price_tags") or []))
            known_terms.update(_clean_terms([document.get("title", ""), document.get("summary", "")]))

    matched = [term for term in known_terms if term and term in content]
    matched.extend(_extract_query_terms(content))
    return sorted(set(matched), key=lambda item: (-len(item), item))[:12]


def _extract_style_terms(content: str, documents: dict[str, list[dict[str, Any]]]) -> list[str]:
    """抽取文本命中的风格词条并做同义词归一化。"""
    known_terms: set[str] = set()
    for resource_documents in documents.values():
        for document in resource_documents:
            known_terms.update(_clean_terms(document.get("tags") or []))
            payload = document.get("payload") or {}
            known_terms.update(_clean_terms(payload.get("styles") or []))
            known_terms.update(_clean_terms(payload.get("photographer_styles") or []))

    matched = sorted(
        {
            term
            for term in known_terms
            if term and term in content and term not in GENERIC_QUERY_TERMS and term not in MAKEUP_TERMS
        },
        key=lambda item: (-len(item), item),
    )
    # 领域同义词：用户说“婚庆”“人像”时数据库里可能写成“婚礼跟拍”“写真”，
    # 精确子串匹配抽不到条件，归一化后再交给同义词感知的过滤。
    return normalize_terms([*matched, *detect_style_terms(content)])[:8]


def _requires_makeup(content: str) -> bool:
    """判断文本是否要求含妆造。"""
    return any(term in content for term in MAKEUP_TERMS)


def _extract_package_includes(content: str, documents: dict[str, list[dict[str, Any]]]) -> list[str]:
    """抽取文本命中的套餐包含内容。"""
    known_terms: set[str] = {
        *MAKEUP_TERMS,
        "精修",
        "底片",
        "服装",
        "棚拍",
        "外景",
        "自然光",
    }
    for document in documents.get("packages", []):
        payload = document.get("payload") or {}
        known_terms.update(_clean_terms(payload.get("includes") or []))
        known_terms.update(_clean_terms(payload.get("service_tags") or []))

    matched = {
            term
            for term in known_terms
            if term and term in content and term not in GENERIC_QUERY_TERMS
    }
    if any(term in matched for term in MAKEUP_TERMS):
        matched.difference_update(MAKEUP_TERMS)
        matched.add("妆造")

    return sorted(
        matched,
        key=lambda item: (-len(item), item),
    )[:8]


def _extract_owner(
    content: str,
    documents: dict[str, list[dict[str, Any]]],
) -> tuple[int | None, str | None]:
    """识别文本中提到的摄影师归属（用户 ID 与显示名）。"""
    candidates = []
    for document in documents.get("photographers", []):
        payload = document.get("payload") or {}
        display_name = (payload.get("user_display_name") or "").strip()
        if display_name and display_name in content:
            candidates.append((len(display_name), document.get("owner_user_id"), display_name))

    if not candidates:
        return None, None
    _, owner_user_id, display_name = sorted(candidates, reverse=True)[0]
    return owner_user_id, display_name


def _extract_query_terms(content: str) -> list[str]:
    """从文本切分 n-gram 查询词条，过滤通用词。"""
    normalized = re.sub(r"\d+(?:\.\d+)?\s*[kK]?", " ", content)
    for fragment in GENERIC_QUERY_FRAGMENTS:
        normalized = normalized.replace(fragment, " ")
    chunks = re.findall(r"[A-Za-z][A-Za-z0-9_-]+|[\u4e00-\u9fff]+", normalized)
    terms: set[str] = set()

    for chunk in chunks:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]+", chunk):
            _add_query_term(terms, chunk)
            continue

        max_size = min(4, len(chunk))
        for size in range(max_size, 1, -1):
            for index in range(0, len(chunk) - size + 1):
                _add_query_term(terms, chunk[index:index + size])

    return sorted(terms, key=lambda item: (-len(item), item))


def _add_query_term(terms: set[str], term: str) -> None:
    """将词条加入集合，过滤过短或通用的碎片。"""
    normalized = term.strip()
    if len(normalized) < 2:
        return
    if normalized in GENERIC_QUERY_TERMS:
        return
    if any(fragment in normalized for fragment in GENERIC_QUERY_FRAGMENTS):
        return
    terms.add(normalized)


def _portfolio_rrf_weights(content: str) -> tuple[float, float, str]:
    """Choose rank weights from the user's refinement language.

    Image-only similarity favors SigLIP. Attribute-changing phrases such as
    "darker" or "outdoors" favor the text route while retaining the reference
    image as an appearance prior.
    """
    text = (content or "").lower()
    image_weight = max(0.0, float(settings.AI_PORTFOLIO_RRF_IMAGE_WEIGHT))
    text_weight = max(0.0, float(settings.AI_PORTFOLIO_RRF_TEXT_WEIGHT))
    modifier_terms = (
        "更暗", "暗一点", "再暗", "亮一点", "更亮", "室外", "户外", "外景",
        "室内", "棚拍", "换成", "改成", "不要", "去掉", "增加", "减少",
        "冷一点", "暖一点", "更冷", "更暖", "低饱和", "高饱和",
    )
    similarity_terms = ("相似", "类似", "同款", "一样", "照着", "参考图")
    if any(term in text for term in modifier_terms):
        return image_weight * 0.85, text_weight * 1.50, "text_refinement"
    if any(term in text for term in similarity_terms):
        return image_weight * 1.25, text_weight * 0.85, "visual_similarity"
    return image_weight, text_weight, "balanced"


def _portfolio_negative_terms(content: str) -> list[str]:
    """Extract a small, explicit deny-list from refinement language."""
    matches = re.findall(
        r"(?:不要|去掉|排除|别要|不想要)\s*([\u4e00-\u9fffA-Za-z0-9_-]{2,8})",
        content or "",
    )
    return [term for term in matches if term not in GENERIC_QUERY_TERMS][:5]


def _rank_portfolio_rrf(
    documents: list[dict[str, Any]],
    criteria: RetrievalCriteria,
    limit: int,
    query_vector: list[float] | None,
    *,
    content: str,
    visual_score_key: str = "visual_score",
    resource_label: str = "portfolio_item",
) -> dict[str, Any]:
    """Fuse independent SigLIP and text retrieval lists with weighted RRF."""
    candidate_limit = max(
        20,
        min(500, limit * max(1, int(settings.AI_PORTFOLIO_RRF_CANDIDATE_MULTIPLIER))),
    )
    eligible = [document for document in documents if _matches_filters(document, criteria)]
    negative_terms = _portfolio_negative_terms(content)
    if negative_terms:
        eligible = [
            document for document in eligible
            if not any(_matches_term(_document_haystack(document), term) for term in negative_terms)
        ]
    strict_style_filter = "style_terms" in criteria.explicit_fields
    if strict_style_filter and criteria.style_terms and any(
        _matches_style_terms(document, criteria.style_terms) for document in eligible
    ):
        eligible = [
            document for document in eligible
            if _matches_style_terms(document, criteria.style_terms)
        ]

    image_ranked = sorted(
        (
            (max(0.0, float(document.get(visual_score_key) or 0.0)), document)
            for document in eligible
            if float(document.get(visual_score_key) or 0.0) > 0
        ),
        key=lambda item: (-item[0], str(item[1].get("id", ""))),
    )[:candidate_limit]

    text_ranked: list[tuple[float, dict[str, Any], float, float]] = []
    for document in eligible:
        keyword_score = _keyword_score(document, criteria)
        semantic_score = document.get("pgvector_score")
        if semantic_score is None:
            semantic_score = max(0.0, cosine_similarity(query_vector, document.get("embedding")))
        structured_match = _matches_structured_criteria(document, criteria)
        if not _is_relevant_candidate(
            criteria,
            keyword_score=keyword_score,
            semantic_score=semantic_score,
            structured_match=structured_match,
        ):
            continue
        text_score = 0.70 * semantic_score + 0.30 * keyword_score
        text_ranked.append((text_score, document, semantic_score, keyword_score))
    text_ranked.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
    text_ranked = text_ranked[:candidate_limit]

    image_weight, text_weight, weight_reason = _portfolio_rrf_weights(content)
    rrf_k = max(1, int(settings.AI_PORTFOLIO_RRF_K))
    fused: dict[int, dict[str, Any]] = {}

    for rank, (visual_score, document) in enumerate(image_ranked, start=1):
        entry = fused.setdefault(document["document_id"], {"document": document, "rrf": 0.0})
        entry.update({"image_rank": rank, "visual_score": visual_score})
        entry["rrf"] += image_weight / (rrf_k + rank)

    for rank, (text_score, document, semantic_score, keyword_score) in enumerate(text_ranked, start=1):
        entry = fused.setdefault(document["document_id"], {"document": document, "rrf": 0.0})
        entry.update({
            "text_rank": rank,
            "text_score": text_score,
            "semantic_score": semantic_score,
            "keyword_score": keyword_score,
        })
        entry["rrf"] += text_weight / (rrf_k + rank)

    siglip_top_10 = []
    for image_rank, (visual_score, document) in enumerate(image_ranked[:10], start=1):
        entry = fused[document["document_id"]]
        siglip_top_10.append({
            f"{resource_label}_id": document.get("id") or (document.get("payload") or {}).get("id"),
            "visual_score": round(float(visual_score), 6),
            "image_rank": image_rank,
            "text_rank": entry.get("text_rank"),
            "rrf_score": round(float(entry.get("rrf") or 0.0), 8),
        })

    ranked = sorted(
        fused.values(),
        key=lambda entry: (
            -entry["rrf"],
            -_quality_score(entry["document"]),
            -_freshness_score(entry["document"]),
            str(entry["document"].get("id", "")),
        ),
    )
    items: list[dict[str, Any]] = []
    for rank, entry in enumerate(ranked[:limit], start=1):
        document = entry["document"]
        payload = {
            **(document.get("payload") or {}),
            "_rag": {
                "schema_version": f"{resource_label}_rrf_v1",
                "rank": rank,
                "fusion_mode": "weighted_rrf",
                "rrf_score": round(entry["rrf"], 8),
                "rrf_k": rrf_k,
                "image_rank": entry.get("image_rank"),
                "text_rank": entry.get("text_rank"),
                "visual_score": round(float(entry.get("visual_score") or 0.0), 6),
                "semantic_score": round(float(entry.get("semantic_score") or 0.0), 6),
                "keyword_score": round(float(entry.get("keyword_score") or 0.0), 6),
                "weight_reason": weight_reason,
            },
        }
        items.append(payload)
    return {
        "items": items,
        "weights": {
            "image": round(image_weight, 4),
            "text": round(text_weight, 4),
            "reason": weight_reason,
            "rrf_k": rrf_k,
            "negative_terms": negative_terms,
        },
        "candidate_counts": {
            "image": len(image_ranked),
            "text": len(text_ranked),
            "union": len(fused),
        },
        "siglip_top_10": siglip_top_10,
    }


def _rank_documents(
    documents: list[dict[str, Any]],
    criteria: RetrievalCriteria,
    limit: int,
    query_vector: list[float] | None = None,
    *,
    image_query: bool = False,
    soft_style_filter: bool = False,
) -> list[dict[str, Any]]:
    """对候选文档做混合打分排序，返回带 _rag 信息的 top 结果。"""
    scored = []
    strict_style_filter = (
        not soft_style_filter
        and (not image_query or "style_terms" in criteria.explicit_fields)
    )
    exact_style_available = strict_style_filter and bool(criteria.style_terms) and any(
        _matches_filters(document, criteria)
        and _matches_style_terms(document, criteria.style_terms or [])
        for document in documents
    )
    for document in documents:
        if not _matches_filters(document, criteria):
            continue
        if exact_style_available and not _matches_style_terms(document, criteria.style_terms or []):
            continue

        price = _to_float(document.get("price"))
        keyword_score = _keyword_score(document, criteria)
        text_semantic_score = document.get("pgvector_score")
        if text_semantic_score is None:
            text_semantic_score = max(0.0, cosine_similarity(query_vector, document.get("embedding")))
        visual_score = max(0.0, float(document.get("visual_score") or 0.0))
        if visual_score:
            image_weight = max(0.0, min(1.0, settings.AI_MULTIMODAL_IMAGE_WEIGHT))
            semantic_score = (1 - image_weight) * text_semantic_score + image_weight * visual_score
        else:
            semantic_score = text_semantic_score
        business_score = _business_score(document, criteria)
        quality_score = _quality_score(document)
        freshness_score = _freshness_score(document)
        if not _is_relevant_candidate(
            criteria,
            keyword_score=keyword_score,
            semantic_score=semantic_score,
            structured_match=_matches_structured_criteria(document, criteria),
        ):
            continue
        if image_query:
            final_score = (
                settings.AI_IMAGE_SEARCH_VISUAL_WEIGHT * visual_score
                + settings.AI_IMAGE_SEARCH_TEXT_WEIGHT * text_semantic_score
                + settings.AI_IMAGE_SEARCH_KEYWORD_WEIGHT * keyword_score
                + settings.AI_IMAGE_SEARCH_BUSINESS_WEIGHT * business_score
                + settings.AI_IMAGE_SEARCH_QUALITY_WEIGHT * quality_score
                + settings.AI_IMAGE_SEARCH_FRESHNESS_WEIGHT * freshness_score
            )
            fusion_mode = "image_primary"
        else:
            final_score = (
                settings.AI_HYBRID_SEMANTIC_WEIGHT * semantic_score
                + settings.AI_HYBRID_KEYWORD_WEIGHT * keyword_score
                + settings.AI_HYBRID_BUSINESS_WEIGHT * business_score
                + settings.AI_HYBRID_QUALITY_WEIGHT * quality_score
                + settings.AI_HYBRID_FRESHNESS_WEIGHT * freshness_score
            )
            fusion_mode = "text_image" if visual_score else "text"
        payload = {
            **(document.get("payload") or {}),
            "_rag": {
                "schema_version": "hybrid_rag_v1",
                "final_score": round(final_score, 6),
                "semantic_score": round(semantic_score, 6),
                "text_semantic_score": round(text_semantic_score, 6),
                "visual_score": round(visual_score, 6),
                "fusion_mode": fusion_mode,
                "keyword_score": round(keyword_score, 6),
                "business_score": round(business_score, 6),
                "quality_score": round(quality_score, 6),
                "freshness_score": round(freshness_score, 6),
                "embedding_model": document.get("embedding_model"),
            },
        }
        scored.append((final_score, price or 0, str(document.get("id", "")), payload))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    results = []
    for rank, (_, _, _, payload) in enumerate(scored[:limit], start=1):
        payload["_rag"]["rank"] = rank
        results.append(payload)
    return results


def _effective_limit(content: str, default: int) -> int:
    """计算实际生效的返回数量上限。"""
    if _requests_single_result(content):
        return 1
    try:
        normalized = int(default)
    except (TypeError, ValueError):
        return 3
    return max(1, min(normalized, 10))


def _requests_single_result(content: str) -> bool:
    """判断文本是否要求只返回一个结果。"""
    # 资源量词不一定是“个/位/名”。搜索作品、样片和案例时，用户常说
    # “一份作品”“一张照片”“一组样片”等；这些表达必须在检索文本被
    # 视觉标签重写之前完成确定性识别。
    if re.search(
        r"(?:推荐|找|给我|只推荐|只要|我只要|选|挑)\s*[【\[\(（]?\s*"
        r"(?:一|1)\s*(?:份|张|组|套|条)\s*(?:作品|样片|案例|照片|图片|资源|方案|套餐)?",
        content,
    ):
        return True
    if re.search(r"(?<!第)(?:一|1)\s*(?:个|位|名)\s*(?:摄影师|摄影老师|拍摄老师|跟拍师)", content):
        return True
    if re.search(r"(?:推荐|找|给我|只推荐|只要|我只要|选|挑)\s*[【\[\(（]?\s*(?:一|1)\s*(?:个|位|名)?", content):
        return True
    return any(
        phrase in content
        for phrase in (
            "推荐一个",
            "推荐一位",
            "推荐一名",
            "推荐1个",
            "推荐1位",
            "推荐1名",
            "只推荐一个",
            "只推荐一位",
            "只推荐一名",
            "只要一个",
            "只要一位",
            "只要一名",
            "我只要一个",
            "我只要一位",
            "我只要一名",
            "一个方案",
            "一个套餐",
            "一个不",
            "选一个",
            "挑一个",
        )
    )


def _explicitly_requests_multiple_resource_types(content: str) -> bool:
    """判断文本是否明确要求同时检索多种资源类型。"""
    return any(
        phrase in content
        for phrase in (
            "摄影师和套餐",
            "摄影师及套餐",
            "摄影师以及套餐",
            "摄影师还有套餐",
            "摄影师和方案",
            "摄影师及方案",
            "摄影师以及方案",
            "摄影师还有方案",
            "作品和套餐",
            "作品以及套餐",
            "作品和摄影师",
            "作品以及摄影师",
        )
    )


def _matches_filters(document: dict[str, Any], criteria: RetrievalCriteria) -> bool:
    """检查文档是否满足排除、归属、城市、预算等硬过滤条件。"""
    if criteria.exclude_resource_ids and str(document.get("id")) in set(criteria.exclude_resource_ids):
        return False

    if criteria.owner_user_id and document.get("resource_type") in {"photographer", "package", "portfolio_item"}:
        if document.get("owner_user_id") != criteria.owner_user_id:
            return False

    if criteria.location and not _matches_location(document, criteria.location):
        return False

    if criteria.budget_max is not None and not _matches_budget(document, criteria.budget_max):
        return False

    if document.get("resource_type") == "package":
        if criteria.requires_makeup and not _package_has_makeup(document):
            return False
        if criteria.package_includes and not _matches_terms(document, criteria.package_includes):
            return False

    return True


def _keyword_score(document: dict[str, Any], criteria: RetrievalCriteria) -> float:
    """计算文档关键词命中比例得分。"""
    terms = _clean_terms([*(criteria.terms or []), *(criteria.style_terms or [])])
    if not terms:
        return 0.5
    haystack = _document_haystack(document)
    matched = sum(1 for term in terms if _matches_term(haystack, term))
    return matched / len(terms)


def _business_score(document: dict[str, Any], criteria: RetrievalCriteria) -> float:
    """按结构化条件命中情况计算商业相关度得分。"""
    signals = []
    if criteria.location:
        signals.append(1.0 if _matches_location(document, criteria.location) else 0.0)
    if criteria.budget_max is not None:
        signals.append(1.0 if _matches_budget(document, criteria.budget_max) else 0.0)
    if criteria.style_terms:
        signals.append(1.0 if _matches_style_terms(document, criteria.style_terms) else 0.0)
    if criteria.requires_makeup and document.get("resource_type") == "package":
        signals.append(1.0 if _package_has_makeup(document) else 0.0)
    signals.append(max(0.0, min(1.0, float(document.get("conversion_score") or 0.0))))
    return sum(signals) / len(signals) if signals else 0.5


def _owner_conversion_scores(db: Session) -> dict[int, float]:
    """统计各摄影师订单转化率，作为商业分先验。"""
    from backend.app.models.order import Order, OrderStatus

    counts: dict[int, list[int]] = {}
    converted_statuses = {
        OrderStatus.CONFIRMED,
        OrderStatus.IN_PROGRESS,
        OrderStatus.DELIVERED,
        OrderStatus.RECEIVED,
        OrderStatus.REVIEWED,
        OrderStatus.COMPLETED,
    }
    for owner_user_id, status_value in db.query(Order.photographer_id, Order.status).all():
        bucket = counts.setdefault(int(owner_user_id), [0, 0])
        bucket[1] += 1
        if status_value in converted_statuses:
            bucket[0] += 1
    prior_weight = max(0, int(settings.AI_CONVERSION_PRIOR_WEIGHT))
    prior_rate = max(0.0, min(1.0, float(settings.AI_CONVERSION_PRIOR_RATE)))
    return {
        owner_user_id: (converted + prior_rate * prior_weight) / (total + prior_weight)
        for owner_user_id, (converted, total) in counts.items()
    }


def _quality_score(document: dict[str, Any]) -> float:
    """按资料完整度计算文档质量得分。"""
    payload = document.get("payload") or {}
    values = [
        document.get("title"),
        document.get("summary"),
        document.get("tags"),
        document.get("city"),
        payload.get("user_bio") or payload.get("photographer_bio") or payload.get("description"),
        payload.get("portfolio_summaries") or payload.get("samples") or payload.get("thumbnail_url"),
    ]
    return sum(1 for value in values if value) / len(values)


def _freshness_score(document: dict[str, Any]) -> float:
    """按更新时间衰减计算新鲜度得分。"""
    value = document.get("updated_at")
    if not value:
        return 0.5
    try:
        from datetime import datetime, timezone
        updated_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds() / 86400)
        return math.exp(-age_days / 180)
    except (TypeError, ValueError):
        return 0.5


def _is_relevant_candidate(
    criteria: RetrievalCriteria,
    *,
    keyword_score: float,
    semantic_score: float,
    structured_match: bool = False,
) -> bool:
    """判断候选文档是否达到相关性门槛。"""
    # 城市、风格、预算这些结构化条件全部命中的资源不再走关键词/语义阈值：
    # criteria.terms 里是原文切出来的 n-gram，噪声会把真实备选挤到阈值之下。
    if structured_match:
        return True
    has_semantic_terms = bool(criteria.terms or criteria.style_terms)
    if not has_semantic_terms:
        return True
    return (
        keyword_score > 0
        or semantic_score >= settings.AI_HYBRID_MIN_SEMANTIC_SCORE
    )


def _matches_structured_criteria(document: dict[str, Any], criteria: RetrievalCriteria) -> bool:
    """文档是否满足本轮全部已知的结构化条件（城市、风格、预算、妆造）。"""
    signals: list[bool] = []
    if criteria.location:
        signals.append(_matches_location(document, criteria.location))
    if criteria.style_terms:
        signals.append(_matches_style_terms(document, criteria.style_terms))
    if criteria.budget_max is not None:
        signals.append(_matches_budget(document, criteria.budget_max))
    if criteria.requires_makeup and document.get("resource_type") == "package":
        signals.append(_package_has_makeup(document))
    return bool(signals) and all(signals)


def _matches_location(document: dict[str, Any], location: str) -> bool:
    """判断文档城市是否与目标城市匹配。"""
    city = document.get("city")
    if not city:
        return False
    return location in city or city in location or _short_location(city) == _short_location(location)


def _matches_budget(document: dict[str, Any], budget_max: float) -> bool:
    """判断文档价格是否在预算上限内。"""
    resource_type = document.get("resource_type")
    payload = document.get("payload") or {}

    if resource_type == "package":
        price = _to_float(document.get("price"))
        return price is not None and price <= budget_max

    if resource_type == "photographer":
        price_range = payload.get("price_range") or {}
        min_price = _to_float(price_range.get("min"))
        return min_price is not None and min_price <= budget_max

    related_prices = payload.get("related_package_prices") or []
    return any(
        (price := _to_float(item.get("price"))) is not None and price <= budget_max
        for item in related_prices
    )


def _matches_terms(document: dict[str, Any], terms: list[str]) -> bool:
    """判断文档是否包含全部指定词条。"""
    haystack = _document_haystack(document)
    return all(_matches_term(haystack, term) for term in terms)


def _matches_style_terms(document: dict[str, Any], terms: list[str]) -> bool:
    """判断文档是否匹配全部风格词条。"""
    payload = document.get("payload") or {}
    resource_type = document.get("resource_type")
    if resource_type == "package":
        values = [
            payload.get("styles") or [],
            payload.get("service_tags") or [],
            document.get("title", ""),
            document.get("summary", ""),
        ]
    elif resource_type == "portfolio_item":
        values = [
            payload.get("tags") or [],
            payload.get("photographer_styles") or [],
            document.get("title", ""),
            document.get("summary", ""),
        ]
    else:
        values = [
            payload.get("styles") or [],
            document.get("tags") or [],
            document.get("title", ""),
            document.get("summary", ""),
            payload.get("user_bio", ""),
        ]
    haystack = " ".join(str(value) for value in values if value)
    return all(_matches_term(haystack, term) for term in terms)


def _matches_term(haystack: str, term: str) -> bool:
    """同义词感知匹配：“婚礼”能命中“婚庆/婚宴/婚礼跟拍”，“妆造”能命中“化妆/带妆”。"""
    return matches_domain_term(haystack, term)


def _package_has_makeup(document: dict[str, Any]) -> bool:
    """判断套餐是否包含妆造服务。"""
    payload = document.get("payload") or {}
    if payload.get("makeup_included") is True:
        return True
    haystack = _document_haystack(document)
    if any(term in haystack for term in ("不含化妆", "不含妆", "不带妆", "无妆")):
        return False
    return any(term in haystack for term in MAKEUP_TERMS)


def _document_haystack(document: dict[str, Any]) -> str:
    """拼接文档的全文检索文本。"""
    payload = document.get("payload") or {}
    values = [
        document.get("title", ""),
        document.get("summary", ""),
        document.get("search_text", ""),
        document.get("city", ""),
        document.get("price_label", ""),
        *(document.get("tags") or []),
        *(document.get("price_tags") or []),
        payload,
    ]
    return " ".join(str(value) for value in values if value)


def _clean_terms(values: list[Any]) -> list[str]:
    """清洗词条列表，去掉空白项。"""
    return [str(value).strip() for value in values if str(value).strip()]


def _short_location(location: str | None) -> str:
    """去掉省市县后缀，返回城市简称。"""
    if not location:
        return ""
    return re.sub(r"(省|市|区|县)$", "", location.strip())


def _to_float(value: Any) -> float | None:
    """安全地把值转为浮点数，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
