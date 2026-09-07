from backend.app.services.ai_tool_policy_service import (
    ToolRiskLevel,
    authorize_tool_call,
    build_action_summary,
)


def test_read_only_profile_blocks_write_tools():
    result = authorize_tool_call(
        "create_booking",
        arguments={"photographer_id": 1, "appointment_date": "2099-08-01"},
        user_role="customer",
        tool_permission_profile="read_only",
        confirmation_count=1,
    )

    assert result.allowed is False
    assert result.error_code == "tool_not_in_profile:read_only"


def test_publisher_profile_allows_publishing_proposal_but_keeps_confirmation():
    result = authorize_tool_call(
        "publish_package",
        arguments={"name": "人像套餐", "price": 999, "duration": 120},
        user_role="photographer",
        tool_permission_profile="publisher",
        confirmation_count=0,
    )

    assert result.allowed is False
    assert result.requires_confirmation is True
    assert result.error_code.startswith("proposal_only_tool:")


def test_auto_policy_never_bypasses_high_risk_confirmation():
    result = authorize_tool_call(
        "create_booking",
        arguments={"photographer_id": 1, "appointment_date": "2099-08-01"},
        user_role="customer",
        approval_policy="auto",
        confirmation_count=0,
    )

    assert result.allowed is False
    assert result.requires_confirmation is True
    assert result.error_code == "proposal_only_tool:create_booking"


def test_action_summary_contains_only_audited_fields():
    summary = build_action_summary(
        "create_booking",
        {
            "photographer_id": 8,
            "package_id": "pkg-8",
            "appointment_date": "2099-08-01",
            "notes": "门口集合",
            "secret": "must-not-leak",
        },
    )

    assert summary["risk_level"] == ToolRiskLevel.REVERSIBLE_WRITE.value
    assert summary["title"] == "创建预约"
    assert {item["field"] for item in summary["details"]} == {
        "photographer_id",
        "package_id",
        "appointment_date",
    }
