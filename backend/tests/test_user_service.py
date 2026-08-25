"""
test_user_service.py — 用户服务层单元测试
测试：用户注册、查询、认证、更新
"""
import pytest
from backend.app.services.user_service import (
    create_user,
    get_user_by_email,
    authenticate_user,
    update_user,
)
from backend.app.core.security import hash_password, verify_password


class TestCreateUser:
    """用户创建测试"""

    def test_create_customer(self, db):
        """正常场景：创建客户"""
        user = create_user(
            db,
            email="newuser@test.com",
            phone="13800000001",
            password="password123",
            display_name="新用户",
            role="customer",
        )
        assert user.id is not None
        assert user.email == "newuser@test.com"
        assert user.role == "customer"
        assert user.display_name == "新用户"

    def test_create_photographer(self, db):
        """正常场景：创建摄影师"""
        user = create_user(
            db,
            email="photographer2@test.com",
            phone="13800000002",
            password="pass123456",
            display_name="摄影师A",
            role="photographer",
        )
        assert user.role == "photographer"

    def test_password_is_hashed(self, db):
        """正常场景：密码被哈希存储"""
        user = create_user(
            db,
            email="hash@test.com",
            phone=None,
            password="mysecret",
            display_name="哈希测试",
            role="customer",
        )
        assert user.hashed_password != "mysecret"
        assert user.hashed_password.startswith("$2b$")
        assert verify_password("mysecret", user.hashed_password) is True

    def test_create_without_phone(self, db):
        """边界条件：手机号为空"""
        user = create_user(
            db,
            email="nophone@test.com",
            phone=None,
            password="password123",
            display_name="无手机",
            role="customer",
        )
        assert user.phone is None

    def test_create_with_empty_display_name(self, db):
        """边界条件：极短显示名"""
        user = create_user(
            db,
            email="shortname@test.com",
            phone=None,
            password="password123",
            display_name="A",
            role="customer",
        )
        assert user.display_name == "A"

    def test_create_duplicate_email(self, db):
        """异常场景：重复邮箱"""
        create_user(db, "dup@test.com", None, "pass123", "用户1", "customer")
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            create_user(db, "dup@test.com", None, "pass456", "用户2", "customer")


class TestGetUserByEmail:
    """用户查询测试"""

    def test_find_existing_user(self, db):
        """正常场景：根据邮箱找到用户"""
        create_user(db, "findme@test.com", "138", "password", "查找", "customer")
        user = get_user_by_email(db, "findme@test.com")
        assert user is not None
        assert user.email == "findme@test.com"

    def test_return_none_for_unknown_email(self, db):
        """异常场景：未知邮箱返回 None"""
        user = get_user_by_email(db, "noone@test.com")
        assert user is None

    def test_case_insensitive_search(self, db):
        """边界条件：大小写敏感（SQLite 默认区分大小写）"""
        create_user(db, "CaseTest@test.com", None, "pass", "大小写", "customer")
        user = get_user_by_email(db, "casetest@test.com")
        # SQLite 默认区分大小写
        assert user is None


class TestAuthenticateUser:
    """用户认证测试"""

    def test_authenticate_valid_credentials(self, db):
        """正常场景：正确凭据认证成功"""
        create_user(db, "auth@test.com", "138", "correct123", "认证", "customer")
        user = authenticate_user(db, "auth@test.com", "correct123")
        assert user is not None
        assert user.email == "auth@test.com"

    def test_authenticate_wrong_password(self, db):
        """异常场景：错误密码认证失败"""
        create_user(db, "auth2@test.com", "138", "correct123", "认证2", "customer")
        user = authenticate_user(db, "auth2@test.com", "wrongpassword")
        assert user is None

    def test_authenticate_unknown_email(self, db):
        """异常场景：未知邮箱认证失败"""
        user = authenticate_user(db, "nobody@test.com", "any123456")
        assert user is None

    def test_authenticate_empty_password(self, db):
        """边界条件：空密码"""
        create_user(db, "auth3@test.com", None, "correct123", "用户", "customer")
        user = authenticate_user(db, "auth3@test.com", "")
        assert user is None


class TestUpdateUser:
    """用户更新测试"""

    def test_update_display_name(self, db):
        """正常场景：更新显示名"""
        user = create_user(db, "update@test.com", "138", "password", "旧名", "customer")
        updated = update_user(db, user, display_name="新名")
        assert updated.display_name == "新名"

    def test_update_phone(self, db):
        """正常场景：更新手机号"""
        user = create_user(db, "phone@test.com", "138", "password", "手机", "customer")
        updated = update_user(db, user, phone="13900000000")
        assert updated.phone == "13900000000"

    def test_update_bio(self, db):
        """正常场景：更新个人简介"""
        user = create_user(db, "bio@test.com", None, "password", "简介", "customer")
        updated = update_user(db, user, bio="摄影爱好者")
        assert updated.bio == "摄影爱好者"

    def test_update_avatar_url(self, db):
        """正常场景：更新头像URL"""
        user = create_user(db, "avatar@test.com", None, "password", "头像", "customer")
        updated = update_user(db, user, avatar_url="/static/avatars/test.jpg")
        assert updated.avatar_url == "/static/avatars/test.jpg"

    def test_update_multiple_fields(self, db):
        """正常场景：同时更新多个字段"""
        user = create_user(db, "multi@test.com", "138", "password", "多人", "customer")
        updated = update_user(db, user, display_name="新名", phone="139", bio="新简介")
        assert updated.display_name == "新名"
        assert updated.phone == "139"
        assert updated.bio == "新简介"

    def test_update_with_none_values(self, db):
        """边界条件：传入 None 不修改原值"""
        user = create_user(db, "none@test.com", "138", "password", "原名", "customer")
        user.bio = "原始简介"
        db.commit()
        updated = update_user(db, user, display_name=None, bio=None)
        assert updated.display_name == "原名"
        assert updated.bio == "原始简介"
