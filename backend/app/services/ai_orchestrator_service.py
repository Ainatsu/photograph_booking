"""规则式意图识别与槽位抽取：将用户消息分类为企划、套餐、预约、检索等意图。"""

import re
from typing import Any

from backend.app.services.ai_agent_contracts import AgentIntent
from backend.app.services.ai_domain_synonyms import detect_style_terms
from backend.app.services.ai_retrieval_service import RESOURCE_TYPE_TERMS, is_resource_search

STYLE_TERMS = (
    "毕业照",
    "日系",
    "复古",
    "胶片",
    "自然光",
    "清新",
    "婚纱",
    "人像",
    "校园",
    "写真",
    "纪实",
    "室内",
    "教室",
    "外景",
    "棚拍",
    "妆造",
    "化妆",
)

CITY_SUFFIX_RE = re.compile(r"([\u4e00-\u9fff]{2,8})(?:市|本地|当地)")

CHINESE_DIGITS = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "两": 2,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}

CHINESE_MONTH_MAP = {
    "十二": 12, "十一": 11, "十": 10, "九": 9, "八": 8,
    "七": 7, "六": 6, "五": 5, "四": 4, "三": 3, "二": 2, "一": 1,
    "元": 1,
}


def _parse_chinese_number(text: str) -> int | None:
    """解析中文数字表达式，如 五百→500, 三千五→3500, 一万二→12000"""
    total = 0
    current_val = 0
    last_unit = 1
    has_content = False

    for ch in text:
        if ch in CHINESE_DIGITS:
            current_val = CHINESE_DIGITS[ch]
            has_content = True
        elif ch in CHINESE_UNITS:
            unit_val = CHINESE_UNITS[ch]
            if current_val == 0:
                current_val = 1
            has_content = True
            if unit_val >= 10000:
                total = (total + current_val) * unit_val
                current_val = 0
            else:
                total += current_val * unit_val
                current_val = 0
            last_unit = unit_val

    if current_val > 0:
        if last_unit >= 100:
            total += current_val * (last_unit // 10)
        else:
            total += current_val

    return total if has_content and total > 0 else None


def recognize_intent_by_rules(content: str | None, attachments: list[dict] | None = None) -> AgentIntent:
    """按规则将用户消息识别为 AgentIntent 意图。"""
    text = (content or "").strip()
    has_image = any((item or {}).get("type") == "image" for item in attachments or [])
    slots = _extract_slots(text)

    if _is_follow_intent(text):
        return AgentIntent(
            intent="follow_photographer",
            sub_intents=["prepare_follow"],
            slots=slots,
            requires_confirmation=True,
            route="follow",
            confidence=0.9,
        )

    if _is_project_consultation(text):
        return AgentIntent(
            intent="chat",
            sub_intents=["general_chat"],
            slots=slots,
            route="chat",
            confidence=0.82,
        )

    if _is_project_discovery_intent(text):
        return AgentIntent(
            intent="resource_search",
            sub_intents=["search_project"],
            slots={**slots, "resource_types": ["projects"]},
            route="project_discovery",
            confidence=0.9,
        )

    if _is_project_application_intent(text):
        return AgentIntent(
            intent="project_application",
            sub_intents=["prepare_project_application"],
            slots=slots,
            route="project_application",
            confidence=0.9,
        )

    if _is_project_intent(text):
        missing_slots = _project_missing_slots(slots)
        return AgentIntent(
            intent="project_flow",
            sub_intents=["create_project"],
            slots=slots,
            missing_slots=missing_slots,
            requires_confirmation=True,
            route="project",
            confidence=0.82,
        )

    if _looks_like_project_detail_form(text, slots):
        missing_slots = _project_missing_slots(slots)
        return AgentIntent(
            intent="project_flow",
            sub_intents=["create_project"],
            slots=slots,
            missing_slots=missing_slots,
            requires_confirmation=True,
            route="project",
            confidence=0.8,
        )

    if _is_package_publish_intent(text):
        missing_slots = _package_missing_slots(slots)
        return AgentIntent(
            intent="package_publish_flow",
            sub_intents=["publish_package"],
            slots=slots,
            missing_slots=missing_slots,
            requires_confirmation=True,
            route="package",
            confidence=0.82,
        )

    if _is_booking_intent(text):
        # A booking message may mention a photographer in its notes; that does
        # not turn the active booking workflow into photographer discovery.
        slots["resource_types"] = ["packages"]
        missing_slots = []
        if not slots.get("date"):
            missing_slots.append("date")
        if not slots.get("time"):
            missing_slots.append("time")
        sub_intents = ["search_package", "create_booking"]
        if has_image:
            sub_intents.insert(0, "vision_analysis")
        return AgentIntent(
            intent="booking_flow",
            sub_intents=sub_intents,
            slots=slots,
            missing_slots=missing_slots,
            requires_confirmation=True,
            route="booking",
            confidence=0.85,
        )

    if has_image and _is_image_driven_retrieval_intent(text):
        resource_types = _image_resource_types_from_text(text)
        slots.setdefault("resource_types", resource_types)
        return AgentIntent(
            intent="resource_search",
            sub_intents=["vision_analysis", _search_sub_intent(resource_types)],
            slots=slots,
            route="vision_retrieval",
            confidence=0.9,
        )

    if has_image:
        return AgentIntent(
            intent="image_analysis",
            sub_intents=["vision_analysis"],
            slots=slots,
            route="vision",
            confidence=0.86,
        )

    if _is_resource_retrieval_intent(text):
        slots.setdefault("resource_types", _resource_types_from_text(text))
        return AgentIntent(
            intent="resource_search",
            sub_intents=[_search_sub_intent(slots["resource_types"])],
            slots=slots,
            route="retrieval",
            confidence=0.88,
        )

    return AgentIntent(
        intent="chat",
        sub_intents=["general_chat"],
        slots=slots,
        route="chat",
        confidence=0.68,
    )


# 向后兼容包装
recognize_intent = recognize_intent_by_rules


def should_run_retrieval(intent: AgentIntent) -> bool:
    """判断该意图是否需要触发资源检索。"""
    if intent.intent == "resource_search":
        return True
    if intent.intent == "booking_flow" and "search_package" in intent.sub_intents:
        return True
    return False


def _extract_slots(text: str) -> dict[str, Any]:
    """从用户文本中抽取全部结构化槽位。"""
    slots: dict[str, Any] = {}
    resource_types = _resource_types_from_text(text)
    if resource_types:
        slots["resource_types"] = resource_types

    styles = _extract_styles(text)
    if styles:
        slots["style"] = styles[0] if len(styles) == 1 else styles

    budget = _extract_budget(text)
    if budget is not None:
        slots["budget_max"] = budget

    budget_range = _extract_budget_range(text)
    if budget_range:
        if "budget_min" not in slots and budget_range[0] is not None:
            slots["budget_min"] = budget_range[0]
        if "budget_max" not in slots and budget_range[1] is not None:
            slots["budget_max"] = budget_range[1]

    city = _extract_city(text)
    if city:
        slots["city"] = city

    location_text = _extract_location_text(text, city)
    if location_text:
        slots["location_text"] = location_text

    photographer_name = _extract_photographer_name(text)
    if photographer_name:
        slots["photographer_name"] = photographer_name

    package_name = _extract_package_name(text)
    if package_name:
        slots["package_name"] = package_name

    duration_minutes = _extract_duration_minutes(text)
    if duration_minutes is not None:
        slots["duration_minutes"] = duration_minutes

    image_count = _extract_image_count(text)
    if image_count is not None:
        slots["image_count"] = image_count

    package_includes = _extract_package_includes(text, image_count)
    if package_includes:
        slots["package_includes"] = package_includes

    package_description = _extract_labeled_project_text(
        text,
        labels=("方案简介", "套餐简介", "服务简介", "简介", "方案描述", "套餐描述", "服务描述", "描述", "介绍"),
    )
    if package_description:
        slots["package_description"] = package_description

    if _requires_makeup(text):
        slots["requires_makeup"] = True

    if _requests_single_result(text):
        slots["limit"] = 1

    date = _extract_date(text)
    if date:
        slots["date"] = date
    time = _extract_time(text)
    if time:
        slots["time"] = time

    people_count = _extract_people_count(text)
    if people_count is not None:
        slots["people_count"] = people_count

    project_title = _extract_labeled_project_text(
        text,
        labels=("企划标题", "拍摄标题", "标题", "企划名称"),
    )
    if not project_title:
        project_title = _extract_implicit_project_title(text)
    if project_title:
        slots["title"] = project_title

    project_description = _extract_labeled_project_text(
        text,
        labels=("需求描述", "拍摄需求", "具体需求", "需求说明", "需求"),
    )
    if project_description:
        slots["description"] = project_description

    deliverables = _extract_labeled_project_text(
        text,
        labels=("交付要求", "交付内容", "成片要求", "出片要求", "交付物"),
    )
    if deliverables:
        slots["deliverables"] = deliverables

    return slots


def _is_negated(text: str, action: str) -> bool:
    """检查文本中是否包含对某个动作的否定表达。"""
    patterns = [
        rf"不\s*{re.escape(action)}",
        rf"先不\s*{re.escape(action)}",
        rf"别\s*{re.escape(action)}",
        rf"不要\s*{re.escape(action)}",
        rf"先不要\s*{re.escape(action)}",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_follow_intent(text: str) -> bool:
    """判断是否为关注摄影师意图。"""
    if not text:
        return False
    # 否定表达：不关注、先不关注 → 不是关注意图
    if _is_negated(text, "关注"):
        return False
    return any(term in text for term in ("关注", "收藏这个摄影师", "收藏这位摄影师", "follow"))


def _is_project_intent(text: str) -> bool:
    """判断是否为发布企划意图。"""
    if not text:
        return False
    if _is_project_consultation(text):
        return False
    # 否定表达：不发企划、先不发企划了 → 不是企划意图
    if re.search(r"(?:不|别)\s*发\s*企划", text) or re.search(r"先不\s*发\s*企划", text):
        return False
    if "咨询" in text and "企划" in text and "发布" not in text:
        return False
    if re.search(r"(?:发|发布).{0,30}企划", text):
        return True
    if (
        any(term in text for term in ("发布", "帮我发", "帮我发布"))
        and "需求" in text
        and any(term in text for term in ("写真", "毕业照", "跟拍", "拍摄", "摄影"))
        and not any(term in text for term in ("方案", "套餐"))
    ):
        return True
    return any(
        term in text
        for term in ("发布企划", "发企划", "发一个企划", "拍摄企划", "征集摄影师", "发布拍摄")
    )


def _is_project_consultation(text: str) -> bool:
    if not text or not any(term in text for term in ("企划", "拍摄需求", "拍摄计划", "拍摄任务")):
        return False
    return any(term in text for term in (
        "如何", "怎么", "怎样", "什么是", "怎么用", "如何用",
        "能否", "可以吗", "教程", "流程", "规则", "要求", "咨询", "了解",
        "建议", "意见", "怎么写", "如何写", "怎么准备", "如何准备",
        "是否合适", "合不合适", "值不值得", "帮我看看",
    ))


def _has_project_reference_index(text: str) -> bool:
    return bool(re.search(r"第\s*[一二两三四五六七八九十\d]+\s*(?:个|位|名)?|[1-9]\d*\s*(?:个|位|名|号)", text))


def _is_project_discovery_intent(text: str) -> bool:
    if not text:
        return False
    has_project_target = any(term in text for term in (
        "企划", "拍摄需求", "拍摄计划", "任务", "应邀", "企划大厅",
    ))
    has_indexed_application = _has_project_reference_index(text) and any(
        term in text for term in ("申请", "报名", "应邀", "参加", "提交", "接这个")
    )
    if not has_project_target and not has_indexed_application:
        return False
    return any(term in text for term in (
        "推荐", "找", "寻找", "看看", "浏览", "有什么", "有没有",
        "可接", "能接", "接单", "接活", "大厅",
    )) or has_indexed_application


def _is_project_application_intent(text: str) -> bool:
    """判断是否明确要申请当前企划，而不是咨询或寻找企划。"""
    if not text or _is_project_consultation(text) or _has_project_reference_index(text):
        return False
    if not any(term in text for term in ("企划", "拍摄需求", "拍摄计划", "项目", "应邀")):
        return False
    if any(term in text for term in ("推荐", "寻找", "搜索", "有没有", "有什么可", "看看")):
        return False
    if any(term in text for term in ("填写应邀", "提交应邀", "确认应邀")):
        return True
    return bool(re.search(r"(?:申请|报名|提交|填写|确认|应邀|参加).{0,16}(?:企划|项目)", text))


def _extract_implicit_project_title(text: str) -> str | None:
    """从文本中隐式提取企划标题。"""
    patterns = (
        r"(?:帮我|请|想)?(?:发布|发)(?:一个|个)?\s*([^，,。；;\n]{2,40}?)企划(?=[，,。；;\n]|$)",
        r"(?:帮我|请|想)?(?:发布|发)(?:一个|个)?\s*([^，,。；;\n]{2,40}?)(?=[，,。；;\n].*需求)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.S)
        if not match:
            continue
        value = re.sub(r"^(?:关于|拍摄|摄影)", "", match.group(1)).strip()
        if not value or value in {"企划", "拍摄", "摄影"}:
            continue
        if not any(term in value for term in ("写真", "毕业照", "跟拍", "拍摄", "摄影", "婚礼", "活动", "人像", "亲子")):
            continue
        return value if value.endswith("企划") else f"{value}企划"
    return None


def _looks_like_project_detail_form(text: str, slots: dict[str, Any]) -> bool:
    """判断文本是否像企划详情表单的填写内容。"""
    if not text or _is_package_publish_intent(text):
        return False

    field_labels = (
        "城市", "地点", "位置", "预算", "时间", "日期", "人数",
        "需求", "需求描述", "拍摄需求", "具体需求", "需求说明",
        "交付要求", "交付内容", "成片要求", "出片要求", "交付物",
    )
    label_count = sum(1 for label in field_labels if _has_labeled_field(text, label))
    filled_count = sum(
        1
        for key in ("city", "location_text", "budget_max", "date", "people_count", "description", "deliverables")
        if slots.get(key) not in (None, "", [])
    )
    has_project_specific_field = any(
        _has_labeled_field(text, label)
        for label in ("需求", "需求描述", "拍摄需求", "具体需求", "需求说明", "交付要求", "交付内容")
    )
    has_basic_project_info = sum(
        1
        for key in ("city", "budget_max", "date", "people_count")
        if slots.get(key) not in (None, "", [])
    ) >= 2
    return has_project_specific_field and has_basic_project_info and (label_count >= 4 or filled_count >= 5)


def _has_labeled_field(text: str, label: str) -> bool:
    """判断文本中是否出现指定字段标签。"""
    return bool(re.search(rf"(?:^|[\s，,。；;]){re.escape(label)}\s*(?:是|为|在|：|:|，|,)?", text))


def _is_package_publish_intent(text: str) -> bool:
    """判断是否为发布方案/套餐意图。"""
    if "企划" in text:
        return False
    if re.search(r"(?:发布|上架|创建|新增|发).{0,30}(?:方案|套餐)", text):
        return True
    return any(
        term in text
        for term in ("发布方案", "发布套餐", "上架方案", "上架套餐", "新增方案", "新增套餐", "创建方案", "创建套餐")
    )


def _is_booking_intent(text: str) -> bool:
    """检测是否为预约意图"""
    if not text:
        return False
    # 否定表达：先不要预约、不预约 → 不是预约意图
    if _is_negated(text, "预约"):
        return False
    # "咨询怎么预约" 是咨询问题，不是预约操作
    if "咨询" in text and "预约" in text:
        return False
    if any(term in text for term in (
        "预约", "预定", "预订", "下单", "订这个套餐", "定这个套餐",
        "创建预约", "帮我约", "帮我安排", "安排拍摄", "预约拍摄",
    )):
        return True

    # 模式匹配
    if re.search(r"(?:想|要|打算|帮我)\s*(?:约|预约|预定|预订|定)", text):
        return True
    if re.search(r"(?:把|帮).{0,10}(?:这个|那个).{0,10}(?:预约|预定|预订|定下来)", text):
        return True
    if re.search(r"就\s*(?:这个|它|这个套餐|这个方案)\s*(?:吧|了)?\s*(?:,|，)?\s*(?:约|预约|定)", text):
        return True

    return False


def _is_resource_retrieval_intent(text: str) -> bool:
    """判断是否为资源检索意图。"""
    if is_resource_search(text):
        return True
    return any(term in text for terms in RESOURCE_TYPE_TERMS.values() for term in terms)


def _is_image_driven_retrieval_intent(text: str) -> bool:
    """判断是否为图片驱动的检索意图。"""
    if not text:
        return False

    has_search_action = any(
        term in text
        for term in ("找", "推荐", "搜索", "查找", "有没有", "类似", "相似", "同款", "匹配")
    )
    if not has_search_action:
        return False

    has_resource_target = any(
        term in text
        for terms in RESOURCE_TYPE_TERMS.values()
        for term in terms
        if term not in {"照片", "图片"}
    )
    has_visual_reference = any(
        term in text
        for term in ("这张图", "这张图片", "这张照片", "参考图", "风格", "类似")
    )
    return has_resource_target or has_visual_reference


def _resource_types_from_text(text: str) -> list[str]:
    """从文本中提取请求的资源类型。"""
    matched = [
        key
        for key, terms in RESOURCE_TYPE_TERMS.items()
        if any(term in text for term in terms)
    ]
    if "packages" in matched and not _explicitly_requests_multiple_resource_types(text):
        return ["packages"]
    if "portfolio_items" in matched and "photographers" in matched and not _explicitly_requests_multiple_resource_types(text):
        return ["portfolio_items"]
    if matched:
        return matched
    if is_resource_search(text):
        return ["photographers"]
    return []


def _image_resource_types_from_text(text: str) -> list[str]:
    """从带图文本中提取请求的资源类型。"""
    matched = []
    for key, terms in RESOURCE_TYPE_TERMS.items():
        relevant_terms = terms
        if key == "portfolio_items":
            relevant_terms = tuple(term for term in terms if term not in {"照片", "图片"})
        if any(term in text for term in relevant_terms):
            matched.append(key)

    if "packages" in matched and not _explicitly_requests_multiple_resource_types(text):
        return ["packages"]
    if "portfolio_items" in matched and "photographers" in matched and not _explicitly_requests_multiple_resource_types(text):
        return ["portfolio_items"]
    if matched:
        return matched
    return ["photographers"]


def _search_sub_intent(resource_types: list[str]) -> str:
    """根据资源类型返回对应的检索子意图。"""
    if resource_types == ["packages"]:
        return "search_package"
    if resource_types == ["portfolio_items"]:
        return "search_portfolio_item"
    if resource_types == ["photographers"]:
        return "search_photographer"
    return "search_resources"


def _project_missing_slots(slots: dict[str, Any]) -> list[str]:
    """返回企划缺失的必填槽位。"""
    required = ("city", "budget_max", "style", "date", "people_count", "description")
    return [name for name in required if not slots.get(name)]


def _package_missing_slots(slots: dict[str, Any]) -> list[str]:
    """返回套餐缺失的必填槽位。"""
    missing = []
    if not slots.get("package_name") and not slots.get("style"):
        missing.append("package_name")
    if not (slots.get("price") or slots.get("budget_max")):
        missing.append("price")
    if not slots.get("duration_minutes"):
        missing.append("duration_minutes")
    if not slots.get("image_count"):
        missing.append("image_count")
    if not slots.get("package_description"):
        missing.append("package_description")
    return missing


def _unique_terms(terms: list[str]) -> list[str]:
    """对词条列表去重并丢弃空白项。"""
    seen = set()
    result = []
    for term in terms:
        normalized = str(term).strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _extract_styles(text: str) -> list[str]:
    """从文本中提取拍摄风格列表。"""
    styles = [term for term in STYLE_TERMS if term in text]
    styles.extend(_extract_explicit_style_terms(text))
    # 领域同义词：“婚庆/婚宴”归一化为“婚礼”，让检索层拿到可过滤的风格条件。
    styles.extend(detect_style_terms(text))
    if "毕业照" not in styles and ("毕业照" in text or ("毕业" in text and any(term in text for term in ("拍", "照", "写真")))):
        styles.append("毕业照")
    if "校园" not in styles and any(term in text for term in ("大学", "学院", "校园")):
        styles.append("校园")
    return _unique_terms(styles)


def _extract_explicit_style_terms(text: str) -> list[str]:
    """提取文本中显式声明的风格词。"""
    patterns = (
        r"(?:拍摄|摄影)?风格\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|叫|就是|：|:)?\s*([^，,。；;\n]{1,30})",
        r"(?:想要|需要|偏好|喜欢)\s*([^，,。；;\n]{1,20}?)(?:风格|类型)",
    )
    results: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            raw_value = match.group(1)
            parts = re.split(r"[、/／和与\s]+", raw_value)
            for part in parts:
                value = re.sub(
                    r"^(?:比较|偏|偏向|就是|是|要|想要|希望|需要)",
                    "",
                    part,
                ).strip()
                value = re.sub(r"(?:一些|一点|一点儿|左右|风格|类型|的)$", "", value).strip()
                if not value or value in {"拍摄", "摄影", "补充", "待补充"}:
                    continue
                if any(term in value for term in ("预算", "价格", "人数", "日期", "时间", "地点")):
                    continue
                results.append(value)
    return results


def _extract_budget(text: str) -> float | None:
    """从文本中提取预算上限（元）。"""
    k_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", text)
    if k_match:
        return float(k_match.group(1)) * 1000

    arabic_numbers: list[float] = []

    # 范围模式 "X到Y" → 提取 Y 作为预算上限
    range_match = re.search(r"(\d{1,6}(?:\.\d+)?)\s*(?:到|至|~|-)\s*(\d{1,6}(?:\.\d+)?)", text)
    if range_match:
        arabic_numbers.append(float(range_match.group(2)))

    for match in re.finditer(r"(?<!\d)(\d{1,6}(?:\.\d+)?)\s*(?:块钱|块|元)", text):
        arabic_numbers.append(float(match.group(1)))

    for match in re.finditer(
        r"(?:预算|费用|价格|价位|报价|不超过|最多|花)\s*"
        r"(?:改成|改为|修改为|调整为|换成|设为|设置为|到|是|为)?\s*"
        r"(?<!\d)(\d{1,6}(?:\.\d+)?)(?!\d)",
        text,
    ):
        arabic_numbers.append(float(match.group(1)))

    cn_numbers = []

    # 中文数字 + 元/块 如 "五百元" "一千块" "两千块钱"
    for match in re.finditer(
        r"([零一二三四五六七八九十百千万两]+)\s*(?:块钱|块|元)",
        text,
    ):
        cn_val = _parse_chinese_number(match.group(1))
        if cn_val:
            cn_numbers.append(float(cn_val))

    # 预算/价格/准备/打算 + 中文数字 如 "预算五百" "价格五百" "准备花一千"
    if not cn_numbers:
        for match in re.finditer(
            r"(?:预算|费用|价格|价位|报价|花)\s*"
            r"(?:改成|改为|修改为|调整为|换成|设为|设置为|到|是|为)?\s*"
            r"([零一二三四五六七八九十百千万两]+)",
            text,
        ):
            cn_val = _parse_chinese_number(match.group(1))
            if cn_val:
                cn_numbers.append(float(cn_val))

    candidates = arabic_numbers + cn_numbers
    return max(candidates) if candidates else None


def _extract_budget_range(text: str) -> tuple[float | None, float | None]:
    """提取预算范围"X到Y"中的下限和上限，返回 (budget_min, budget_max)。"""
    # 阿拉伯数字范围: "500到1000" "500至1000" "500~1000" "500-1000"
    range_match = re.search(
        r"(\d{1,6}(?:\.\d+)?)\s*(?:到|至|~|-)\s*(\d{1,6}(?:\.\d+)?)",
        text,
    )
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))
    return None, None


def _extract_city(text: str) -> str | None:
    """从文本中提取城市名。"""
    KNOWN_CITIES = (
        "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "南京", "武汉", "西安",
        "香港", "澳门", "大理", "丽江", "厦门", "三亚", "苏州", "青岛", "长沙", "昆明",
    )
    best_city = None
    best_pos = len(text)
    for city in KNOWN_CITIES:
        pos = text.find(city)
        if pos != -1 and pos < best_pos:
            best_city = city
            best_pos = pos
    if best_city:
        return best_city
    # 不带“市”的城市在自然表达中通常由介词和资源词限定，例如“推荐在大理的方案”。
    # 这里只接受短地名并要求后面紧跟明确边界，避免把整句命令误当成城市。
    preposition_match = re.search(
        r"(?:在|去|到)\s*([\u4e00-\u9fff]{2,8}?)(?=的?(?:摄影师|作品|样片|案例|套餐|方案|企划|拍摄|写真|婚纱|婚礼)|[，,。；;\s]|$)",
        text,
    )
    if preposition_match:
        candidate = preposition_match.group(1).strip()
        if _is_valid_city_candidate(candidate):
            return candidate
    match = CITY_SUFFIX_RE.search(text)
    if match:
        candidate = match.group(1).strip()
        if _is_valid_city_candidate(candidate):
            return candidate
    return None


def _is_valid_city_candidate(candidate: str) -> bool:
    """判断城市候选词是否有效。"""
    if not candidate or len(candidate) < 2:
        return False
    if any(term in candidate for term in ("根据", "实际", "需要", "不同", "不限", "不限制", "价格", "预算")):
        return False
    return candidate not in {"城市", "本地", "当地"}


def _extract_location_text(text: str, city: str | None = None) -> str | None:
    """从文本中提取拍摄地点描述。"""
    patterns = (
        r"在\s*([^，,。；;\n]{2,30}?)(?:拍|拍摄|照|进行)",
        r"地点\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|在|是|为|：|:)?\s*([^，,。；;\n]{2,30})",
        r"位置\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|在|是|为|：|:)?\s*([^，,。；;\n]{2,30})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = _clean_location_candidate(match.group(1), city)
            if candidate:
                return candidate

    suffix_match = re.search(
        r"([\u4e00-\u9fffA-Za-z0-9·_-]{2,30}(?:大学|学院|校区|公园|广场|商场|酒店|民宿|摄影棚|工作室))",
        text,
    )
    if suffix_match:
        return _clean_location_candidate(suffix_match.group(1), city)
    return None


def _clean_location_candidate(candidate: str, city: str | None = None) -> str | None:
    """清洗地点候选词，去除口语前缀与无效值。"""
    value = re.sub(r"^(?:我想|想|希望|准备|打算|要|在)", "", candidate or "").strip()
    value = re.sub(r"^(?:改成|改为|修改为|调整为|换成|设为|设置为)", "", value).strip()
    value = re.sub(r"(?:这边|附近|里面|室内|室外)$", "", value).strip()
    if not value or value == city:
        return None
    if len(value) < 2:
        return None
    return value


def _extract_photographer_name(text: str) -> str | None:
    """从文本中提取摄影师名称。"""
    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9_ -]{2,24}摄影师\d*)", text)
    if match:
        return match.group(1).strip()
    return None


def _extract_package_name(text: str) -> str | None:
    """从文本中提取方案/套餐名称。"""
    patterns = (
        r"(?:方案名称|套餐名称|服务名称|名称|名字|标题|叫|命名为)\s*(?:做|是|为|叫|：|:|，|,)?\s*([^，,。；;\n]{2,30})",
        r"(?:发布|上架|创建|新增|发)\s*(?:一个|一套|个|套)?\s*([^，,。；;]{2,30}?)(?:方案|套餐)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = re.sub(r"^(?:帮我|我想|想|准备|要|做|一个|一套|方案|套餐)", "", match.group(1)).strip()
        candidate = re.sub(r"(?:方案|套餐|的|摄影|拍摄)$", "", candidate).strip()
        if not candidate or candidate in {"方案", "套餐"}:
            continue
        if any(term in candidate for term in ("根据", "实际", "价格", "预算", "报价", "费用", "时长", "分钟", "小时")):
            continue
        return candidate
    return None


def _extract_duration_minutes(text: str) -> int | None:
    """从文本中提取拍摄时长（分钟）。"""
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:个)?\s*(?:小时|h|H)", text)
    if hour_match:
        return int(float(hour_match.group(1)) * 60)

    chinese_hour_match = re.search(r"([零一二三四五六七八九十两]+)\s*(?:个)?小时", text)
    if chinese_hour_match:
        hours = _parse_chinese_number(chinese_hour_match.group(1))
        if hours:
            return hours * 60

    minute_match = re.search(r"(\d{1,3})\s*(?:分钟|分)", text)
    if minute_match:
        return int(minute_match.group(1))

    chinese_minute_match = re.search(r"([零一二三四五六七八九十百两]+)\s*(?:分钟|分)", text)
    if chinese_minute_match:
        return _parse_chinese_number(chinese_minute_match.group(1))

    return None


def _extract_image_count(text: str) -> int | None:
    """从文本中提取精修张数。"""
    patterns = (
        r"(?:精修|修图|成片|出片)\s*(\d{1,3})\s*张",
        r"(\d{1,3})\s*张\s*(?:精修|修图|成片|出片)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    chinese_patterns = (
        r"(?:精修|修图|成片|出片)\s*([零一二三四五六七八九十百两]+)\s*张",
        r"([零一二三四五六七八九十百两]+)\s*张\s*(?:精修|修图|成片|出片)",
    )
    for pattern in chinese_patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_chinese_number(match.group(1))
    return None


def _extract_package_includes(text: str, image_count: int | None = None) -> list[str]:
    """从文本中提取套餐包含内容。"""
    includes = []
    if image_count:
        includes.append(f"精修{image_count}张")
    for term in ("底片全送", "妆造", "化妆", "服装", "外景", "棚拍", "室内", "上门拍摄"):
        if term in text:
            includes.append(term)
    clothes_match = re.search(r"(\d{1,2})\s*套\s*(?:服装|造型)", text)
    if clothes_match:
        includes.append(f"{int(clothes_match.group(1))}套服装")
    return _unique_terms(includes)


def _requires_makeup(text: str) -> bool:
    """判断文本是否要求含化妆。"""
    return any(term in text for term in ("化妆", "妆造", "带妆", "含妆"))


def _requests_single_result(text: str) -> bool:
    """判断文本是否要求只推荐一个结果。"""
    if re.search(
        r"(?:推荐|找|给我|只推荐|只要|我只要|选|挑)\s*[【\[\(（]?\s*"
        r"(?:一|1)\s*(?:份|张|组|套|条)\s*(?:作品|样片|案例|照片|图片|资源|方案|套餐)?",
        text,
    ):
        return True
    if re.search(r"(?<!第)(?:一|1)\s*(?:个|位|名)\s*(?:摄影师|摄影老师|拍摄老师|跟拍师)", text):
        return True
    if re.search(r"(?:推荐|找|给我|只推荐|只要|我只要|选|挑)\s*[【\[\(（]?\s*(?:一|1)\s*(?:个|位|名)?", text):
        return True
    return any(
        phrase in text
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
            "选一个",
            "挑一个",
        )
    )


_CHINESE_DATE_MONTH_RE = re.compile(
    r"(?:("
    r"十二|十一|十|九|八|七|六|五|四|三|二|一|元"
    r"))\s*月\s*"
    r"([零一二三四五六七八九十廿两]+)\s*(?:日|号)?"
)


def _extract_date(text: str) -> str | None:
    unicode_numeric = re.search(r"(\d{1,2})\s*[\u6708]\s*(\d{1,2})\s*[\u65e5\u53f7]?", text)
    if not unicode_numeric:
        unicode_numeric = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{1,2})", text)
    if unicode_numeric:
        month, day = int(unicode_numeric.group(1)), int(unicode_numeric.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month:02d}-{day:02d}"

    unicode_chinese = re.search(
        r"([\u96f6\u3007\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+)\s*\u6708\s*"
        r"([\u96f6\u3007\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+)\s*[\u65e5\u53f7]?",
        text,
    )
    if unicode_chinese:
        digits = {"\u4e00": 1, "\u4e8c": 2, "\u4e24": 2, "\u4e09": 3, "\u56db": 4, "\u4e94": 5, "\u516d": 6, "\u4e03": 7, "\u516b": 8, "\u4e5d": 9}

        def chinese_number(value: str) -> int | None:
            if value == "\u5341":
                return 10
            if value.startswith("\u5341"):
                return 10 + (digits.get(value[1:]) or 0)
            if value.endswith("\u5341"):
                return (digits.get(value[:-1]) or 0) * 10
            if "\u5341" in value:
                left, right = value.split("\u5341", 1)
                return (digits.get(left) or 0) * 10 + (digits.get(right) or 0)
            return digits.get(value)

        month = chinese_number(unicode_chinese.group(1))
        day = chinese_number(unicode_chinese.group(2))
        if month and day and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month:02d}-{day:02d}"

    """从文本中提取拍摄日期（MM-DD）。"""
    # 阿拉伯数字: "6月15日" "6月15"
    match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*(?:[日号])?", text)
    if match:
        return f"{int(match.group(1)):02d}-{int(match.group(2)):02d}"

    # 中文日期: "六月十五日" "三月八号" "六月十五"
    match = _CHINESE_DATE_MONTH_RE.search(text)
    if match:
        month = CHINESE_MONTH_MAP.get(match.group(1))
        day = _parse_chinese_number(match.group(2))
        if month and day and 1 <= day <= 31:
            return f"{month:02d}-{day:02d}"

    return None


_CHINESE_HOUR_DIGIT = re.compile(r"([零一二三四五六七八九十两]+)\s*点")


def _extract_time(text: str) -> str | None:
    """从文本中提取拍摄时间（HH:MM）。"""
    match = re.search(r"(\d{1,2})(?::|：)(\d{2})", text)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    # 阿拉伯数字: "下午3点" "3点"
    match = re.search(r"(上午|下午|晚上)?\s*(\d{1,2})\s*点", text)
    if match:
        hour = int(match.group(2))
        if match.group(1) in {"下午", "晚上"} and hour < 12:
            hour += 12
        return f"{hour:02d}:00"

    # 中文数字: "三点" "下午两点"
    match = re.search(r"(上午|下午|晚上)?\s*" + _CHINESE_HOUR_DIGIT.pattern, text)
    if match:
        hour = _parse_chinese_number(match.group(2))
        if hour is None or hour > 24:
            return None
        if match.group(1) in {"下午", "晚上"} and hour < 12:
            hour += 12
        return f"{hour:02d}:00"

    return None


def _extract_people_count(text: str) -> int | None:
    """从文本中提取拍摄人数。"""
    # 明确标签: "拍摄人数100人" "人数：100"
    match = re.search(
        r"(?:拍摄)?人数\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|：|:)?\s*(\d{1,6})\s*(?:个)?\s*(?:人|位)?",
        text,
    )
    if match:
        value = int(match.group(1))
        return value if value > 0 else None

    # 阿拉伯数字: "3人" "100位"
    match = re.search(r"(?<!\d)(\d{1,6})\s*(?:个)?\s*(?:人|位)", text)
    if match:
        value = int(match.group(1))
        return value if value > 0 else None

    # 中文数字: "三人" "十二人" "一百人" "两个人"
    match = re.search(
        r"(?:拍摄)?人数\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|：|:)?\s*([零一二三四五六七八九十百千万两]+)\s*(?:个)?\s*(?:人|位)?",
        text,
    )
    if match:
        return _parse_chinese_number(match.group(1))

    match = re.search(r"([零一二三四五六七八九十百千万两]+)\s*(?:个)?\s*(?:人|位)", text)
    if match:
        return _parse_chinese_number(match.group(1))

    return None


def _extract_labeled_project_text(text: str, *, labels: tuple[str, ...]) -> str | None:
    """提取指定标签后面的项目文本，并截断到下一个标签。"""
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_labels = (
        "需求描述", "拍摄需求", "具体需求", "需求说明", "需求",
        "方案简介", "套餐简介", "服务简介", "简介", "方案描述", "套餐描述", "服务描述", "描述", "介绍",
        "交付要求", "交付内容", "成片要求", "出片要求", "交付物",
        "拍摄人数", "人数", "拍摄风格", "风格", "预算", "地点", "城市", "时间", "日期",
        "方案名称", "套餐名称", "服务名称", "名称", "名字", "标题", "价格", "方案价格", "套餐价格",
        "拍摄时长", "时长", "精修张数", "精修", "包含",
    )
    stop_pattern = "|".join(re.escape(label) for label in stop_labels if label not in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|：|:|，|,)?\s*(.+)",
        text,
        flags=re.S,
    )
    if not match:
        return None

    value = match.group(1).strip()
    stop_match = re.search(
        rf"(?:{stop_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|：|:)",
        value,
    )
    if stop_match:
        value = value[:stop_match.start()].strip()
    value = re.sub(r"^[，,。；;\s]+|[，,；;\s]+$", "", value)
    return value or None


def _explicitly_requests_multiple_resource_types(text: str) -> bool:
    """判断文本是否明确要求同时检索多种资源类型。"""
    return any(
        phrase in text
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
