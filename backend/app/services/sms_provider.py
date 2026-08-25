"""短信服务 Provider：验证码短信发送的抽象与本地内存实现。"""

from __future__ import annotations

from threading import Lock

from backend.app.core.config import settings


class SmsProviderError(RuntimeError):
    """短信服务异常。"""
    pass


class SmsProvider:
    """短信服务抽象基类。"""

    def send_verification_code(self, phone: str, code: str) -> None:
        """发送验证码短信。"""
        raise NotImplementedError


class MemorySmsProvider(SmsProvider):
    """本地开发与测试 Provider；不会打印或写入数据库。"""

    def __init__(self) -> None:
        """初始化内存验证码存储。"""
        self._codes: dict[str, str] = {}
        self._lock = Lock()

    def send_verification_code(self, phone: str, code: str) -> None:
        """记录手机号对应的验证码。"""
        with self._lock:
            self._codes[phone] = code

    def get_last_code(self, phone: str) -> str | None:
        """获取指定手机号最近发送的验证码。"""
        with self._lock:
            return self._codes.get(phone)

    def reset(self) -> None:
        """清空所有已发送的验证码。"""
        with self._lock:
            self._codes.clear()


class UnavailableSmsProvider(SmsProvider):
    """短信服务不可用时的兜底 Provider。"""

    def send_verification_code(self, phone: str, code: str) -> None:
        """抛出短信服务不可用异常。"""
        raise SmsProviderError("短信服务暂时不可用")


_memory_provider = MemorySmsProvider()


def get_sms_provider() -> SmsProvider:
    """根据配置返回短信 Provider 实例。"""
    if settings.SMS_PROVIDER.lower() == "memory":
        return _memory_provider
    return UnavailableSmsProvider()
