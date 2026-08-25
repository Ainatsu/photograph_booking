"""
test_security.py — 安全模块单元测试
测试：密码哈希、密码验证、JWT 生成与验证
"""
import pytest
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
)


class TestHashPassword:
    """密码哈希测试"""

    def test_hash_returns_different_from_plaintext(self):
        """正常场景：哈希结果不等于原始密码"""
        result = hash_password("mypassword123")
        assert result != "mypassword123"

    def test_hash_returns_bcrypt_format(self):
        """正常场景：哈希结果以 $2b$ 开头（bcrypt 格式）"""
        result = hash_password("test123456")
        assert result.startswith("$2b$")

    def test_hash_is_deterministic_in_format(self):
        """正常场景：每次哈希生成不同盐值，格式统一"""
        r1 = hash_password("same_password")
        r2 = hash_password("same_password")
        assert r1 != r2  # 盐值不同
        assert len(r1) == len(r2)  # 长度一致

    def test_hash_short_password(self):
        """边界条件：最短密码"""
        result = hash_password("a")
        assert result.startswith("$2b$")

    def test_hash_long_password(self):
        """边界条件：较长密码（72字节以内）"""
        long_pw = "a" * 70
        result = hash_password(long_pw)
        assert result.startswith("$2b$")

    def test_hash_special_characters(self):
        """边界条件：特殊字符密码"""
        result = hash_password("!@#$%^&*()_+-=[]{}|;':\",./<>?")
        assert result.startswith("$2b$")

    def test_hash_empty_string(self):
        """边界条件：空字符串密码"""
        result = hash_password("")
        assert result.startswith("$2b$")

    def test_hash_unicode_password(self):
        """边界条件：Unicode 密码"""
        result = hash_password("密码测试123!@#")
        assert result.startswith("$2b$")


class TestVerifyPassword:
    """密码验证测试"""

    def test_verify_correct_password(self):
        """正常场景：正确密码验证通过"""
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_wrong_password(self):
        """异常场景：错误密码验证失败"""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_case_sensitive(self):
        """边界条件：大小写敏感"""
        hashed = hash_password("TestPassword")
        assert verify_password("testpassword", hashed) is False
        assert verify_password("TestPassword", hashed) is True

    def test_verify_empty_password(self):
        """边界条件：空密码"""
        hashed = hash_password("somepassword")
        assert verify_password("", hashed) is False

    def test_verify_different_encoding(self):
        """正常场景：中文字符密码"""
        hashed = hash_password("中文密码123")
        assert verify_password("中文密码123", hashed) is True


class TestCreateAccessToken:
    """JWT 令牌生成测试"""

    def test_creates_valid_token(self):
        """正常场景：生成有效 JWT"""
        token = create_access_token({"sub": "1"})
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT 格式: header.payload.signature

    def test_token_contains_expiry(self):
        """正常场景：令牌包含过期时间"""
        token = create_access_token({"sub": "1"})
        payload = verify_access_token(token)
        assert payload is not None
        assert "exp" in payload

    def test_token_with_empty_data(self):
        """边界条件：空 payload"""
        token = create_access_token({})
        payload = verify_access_token(token)
        assert payload is not None

    def test_token_with_complex_data(self):
        """边界条件：含多种数据类型的 payload"""
        data = {"sub": "1", "role": "photographer", "name": "测试"}
        token = create_access_token(data)
        payload = verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["role"] == "photographer"


class TestVerifyAccessToken:
    """JWT 令牌验证测试"""

    def test_verify_valid_token(self):
        """正常场景：验证有效令牌"""
        token = create_access_token({"sub": "5"})
        payload = verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == "5"

    def test_verify_invalid_token(self):
        """异常场景：验证无效格式"""
        payload = verify_access_token("invalid.token.here")
        assert payload is None

    def test_verify_empty_token(self):
        """异常场景：验证空令牌"""
        payload = verify_access_token("")
        assert payload is None

    def test_verify_none_token(self):
        """异常场景：验证 None 令牌（底层 jose 库会抛异常，需捕获）"""
        with pytest.raises(Exception):
            verify_access_token(None)

    def test_verify_tampered_token(self):
        """异常场景：验证被篡改的令牌"""
        token = create_access_token({"sub": "1"})
        parts = token.split(".")
        tampered = parts[0] + ".tampered_payload." + parts[2]
        payload = verify_access_token(tampered)
        assert payload is None

    def test_verify_missing_sub(self):
        """边界条件：无 sub 字段的令牌"""
        token = create_access_token({"role": "admin"})
        payload = verify_access_token(token)
        assert payload is not None
        assert "sub" not in payload
