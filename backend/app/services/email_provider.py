"""邮件验证码发送 Provider 的抽象与本地内存实现。"""

from __future__ import annotations

from threading import Lock

from backend.app.core.config import settings


class EmailProviderError(RuntimeError):
    """邮件 Provider 错误异常。"""
    pass


class EmailProvider:
    """邮件 Provider 抽象基类。"""

    def send_verification_code(self, email: str, code: str) -> None:
        """发送验证码（子类实现）。"""
        raise NotImplementedError


class MemoryEmailProvider(EmailProvider):
    """本地开发与测试 Provider；不会打印或写入数据库。"""

    def __init__(self) -> None:
        """初始化验证码存储与锁。"""
        self._codes: dict[str, str] = {}
        self._lock = Lock()

    def send_verification_code(self, email: str, code: str) -> None:
        """在内存中保存邮箱对应的验证码。"""
        with self._lock:
            self._codes[email] = code

    def get_last_code(self, email: str) -> str | None:
        """取回邮箱最近一次保存的验证码。"""
        with self._lock:
            return self._codes.get(email)

    def reset(self) -> None:
        """清空全部内存验证码。"""
        with self._lock:
            self._codes.clear()


class UnavailableEmailProvider(EmailProvider):
    """不可用时的兜底 Provider，直接抛错。"""

    def send_verification_code(self, email: str, code: str) -> None:
        """抛出邮件服务不可用错误。"""
        raise EmailProviderError("邮件服务暂时不可用")


_memory_provider = MemoryEmailProvider()


def get_email_provider() -> EmailProvider:
    """按配置返回可用的邮件 Provider。"""
    if settings.EMAIL_PROVIDER.lower() == "memory":
        return _memory_provider
    return UnavailableEmailProvider()
