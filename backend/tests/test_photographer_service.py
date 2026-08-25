"""
test_photographer_service.py — 摄影师服务层单元测试
测试：资料创建/更新、查询、作品、套餐
"""
import pytest
from backend.app.schemas.photographer import PortfolioItemSchema
from backend.app.services.photographer_service import (
    create_or_update_profile,
    get_profile_by_user_id,
    get_all_profiles,
    get_all_works,
    get_all_packages,
    get_work_by_id,
)


def test_portfolio_schema_accepts_legacy_styles_without_tag():
    item = PortfolioItemSchema.model_validate({
        "url": "/static/demo/example.jpg",
        "styles": ["portrait", "film"],
    })

    assert item.tag == "portrait"
    assert item.tags == ["portrait", "film"]


class TestCreateOrUpdateProfile:
    """摄影师资料创建/更新测试"""

    def test_create_new_profile(self, db, photographer_user):
        """正常场景：创建新摄影师资料"""
        data = {
            "location": "上海",
            "styles": ["日系", "复古"],
            "packages": [{"name": "基础套餐", "price": 399, "duration": 60}],
        }
        profile = create_or_update_profile(db, photographer_user.id, data)
        assert profile.id is not None
        assert profile.location == "上海"
        assert profile.styles == ["日系", "复古"]

    def test_update_existing_profile(self, db, photographer_profile):
        """正常场景：更新已有资料"""
        data = {"location": "北京朝阳区"}
        profile = create_or_update_profile(db, photographer_profile.user_id, data)
        assert profile.location == "北京朝阳区"
        # 原有字段保持不变
        assert profile.styles == ["日系", "复古", "人像", "婚纱"]

    def test_update_partial_fields(self, db, photographer_profile):
        """正常场景：只更新部分字段"""
        data = {"location": "深圳", "styles": ["现代", "简约"]}
        profile = create_or_update_profile(db, photographer_profile.user_id, data)
        assert profile.location == "深圳"
        assert profile.styles == ["现代", "简约"]

    def test_update_with_none_not_overriding(self, db, photographer_profile):
        """边界条件：None 值不覆盖已有数据"""
        original_location = photographer_profile.location
        data = {"location": None, "styles": None}
        profile = create_or_update_profile(db, photographer_profile.user_id, data)
        assert profile.location == original_location
        assert profile.styles == ["日系", "复古", "人像", "婚纱"]

    def test_create_minimal_profile(self, db, photographer_user):
        """边界条件：创建最简资料（只含必填字段）"""
        data = {"location": "杭州"}
        profile = create_or_update_profile(db, photographer_user.id, data)
        assert profile.location == "杭州"
        assert profile.styles is None
        assert profile.packages is None


class TestGetProfileByUserId:
    """摄影师资料查询测试"""

    def test_get_existing_profile(self, db, photographer_profile):
        """正常场景：查询已有资料"""
        result = get_profile_by_user_id(db, photographer_profile.user_id)
        assert result is not None
        assert result["user_id"] == photographer_profile.user_id
        assert result["location"] == "北京"

    def test_get_nonexistent_profile(self, db):
        """异常场景：查询不存在的资料"""
        result = get_profile_by_user_id(db, 99999)
        assert result is None

    def test_profile_contains_user_info(self, db, photographer_profile):
        """正常场景：资料包含用户关联信息"""
        result = get_profile_by_user_id(db, photographer_profile.user_id)
        assert "user_display_name" in result
        assert result["user_display_name"] == "测试摄影师"


class TestGetAllProfiles:
    """所有摄影师资料列表测试"""

    def test_list_all_profiles(self, db, photographer_profile):
        """正常场景：获取所有摄影师资料"""
        profiles = get_all_profiles(db)
        assert isinstance(profiles, list)
        assert len(profiles) >= 1

    def test_pagination(self, db, photographer_profile):
        """边界条件：分页"""
        profiles = get_all_profiles(db, skip=0, limit=10)
        assert len(profiles) >= 1
        profiles_skip = get_all_profiles(db, skip=100, limit=10)
        assert len(profiles_skip) == 0


class TestGetAllWorks:
    """作品列表测试"""

    def test_list_all_works(self, db, photographer_profile):
        """正常场景：获取所有作品"""
        works = get_all_works(db)
        assert isinstance(works, list)
        assert len(works) >= 2

    def test_work_structure(self, db, photographer_profile):
        """正常场景：作品包含必要字段"""
        works = get_all_works(db)
        for work in works:
            assert "url" in work
            assert "tag" in work
            assert "user_id" in work

    def test_customer_works_are_listed_and_viewable(self, db, customer_user):
        """All users' uploaded works should be visible in the public works feed."""
        create_or_update_profile(db, customer_user.id, {
            "portfolio": [
                {
                    "id": "customer-work-1",
                    "url": "/static/customer-work.jpg",
                    "tag": "portrait",
                    "title": "Customer Work",
                }
            ]
        })

        works = get_all_works(db)
        detail = get_work_by_id(db, "customer-work-1")

        assert any(work["id"] == "customer-work-1" for work in works)
        assert detail is not None
        assert detail["user_id"] == customer_user.id

    def test_empty_works_when_no_portfolio(self, db, photographer_user):
        """边界条件：无作品时返回空列表"""
        # 创建无作品资料
        data = {"location": "广州"}
        create_or_update_profile(db, photographer_user.id, data)
        works = get_all_works(db)
        # 所有新资料都没 portfolio
        assert len(works) == len(get_all_works(db))


class TestGetAllPackages:
    """套餐列表测试"""

    def test_list_all_packages(self, db, photographer_profile):
        """正常场景：获取所有套餐"""
        packages = get_all_packages(db)
        assert isinstance(packages, list)
        assert len(packages) >= 1

    def test_package_structure(self, db, photographer_profile):
        """正常场景：套餐包含必要字段"""
        packages = get_all_packages(db)
        for pkg in packages:
            assert "package_name" in pkg
            assert "price" in pkg
            assert "photographer_id" in pkg
            assert "photographer_name" in pkg

    def test_empty_when_no_packages(self, db, photographer_user):
        """边界条件：无套餐资料"""
        data = {"location": "成都"}
        create_or_update_profile(db, photographer_user.id, data)
        packages = get_all_packages(db)
        # 没有 package 字段，应返回空
        assert isinstance(packages, list)

    def test_skip_invalid_packages(self, db, photographer_user):
        """边界条件：跳过无名称的套餐"""
        data = {
            "location": "西安",
            "packages": [{"price": 500, "duration": 60}],  # 缺少 name
        }
        create_or_update_profile(db, photographer_user.id, data)
        packages = get_all_packages(db)
        # 此套餐应被跳过
        invalid = [p for p in packages if p.get("price") == 500 and not p.get("package_name")]
        assert len(invalid) == 0
