"""AI 对话服务提供者的协议与多供应商实现。"""

from typing import Protocol

import httpx
from fastapi import HTTPException, status

from backend.app.core.config import settings


class AIProvider(Protocol):
    """AI 对话提供者的统一协议接口。"""
    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """按消息列表调用 AI 并返回回复内容与元数据。"""
        ...


# 检索/工具上下文的固定开头（见 ai_retrieval_service.build_retrieval_context 与
# ai_search_tool_service.build_tool_result_prompt）：模型不可用时靠它判断
# “这一轮后端其实已经查到了真实候选”，好在降级话术里把结果指出来。
_CANDIDATE_CONTEXT_MARKERS = ("平台数据库检索结果如下", "的真实返回结果如下")


def _last_user_text(messages: list[dict]) -> tuple[str, bool]:
    """取最后一条用户消息的纯文本，并说明它是否带图。"""
    user_messages = [message for message in messages if message.get("role") == "user"]
    last_msg = user_messages[-1] if user_messages else {}
    content = last_msg.get("content")
    if isinstance(content, list):
        text = ""
        has_image = False
        for part in content:
            if part.get("type") == "text":
                text = part.get("text", "")
            elif part.get("type") == "image_url":
                has_image = True
        return text, has_image
    return content or "", False


def _has_candidate_context(messages: list[dict]) -> bool:
    """判断消息中是否包含检索或工具调用的候选上下文。"""
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if any(marker in content for marker in _CANDIDATE_CONTEXT_MARKERS):
            return True
    return False


class MockAIProvider:
    """本地开发用的假 provider（AI_PROVIDER=mock）。

    它只在没有接入真实模型时使用，所以回复必须一眼看得出是占位内容，
    也不能把每条消息都当成"拍摄需求"——否则用户发"你好"也会收到一段需求引导话术。
    真实 provider 故障时的降级回复请用 DegradedAIProvider，不要复用这里。
    """

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """生成占位回复，供本地开发环境使用。"""
        text, has_image = _last_user_text(messages)
        image_hint = "我看到你上传的图片了。" if has_image else ""
        if _has_candidate_context(messages):
            body = "下面是平台上符合条件的候选，你可以点开看详细信息，也可以让我按城市、预算或风格再筛一遍。"
        elif text.strip():
            body = f"（本地 mock 回复，未接入真实模型）你说的是「{text.strip()[:60]}」。"
        else:
            body = "（本地 mock 回复，未接入真实模型）"
        return {
            "content": f"{image_hint}{body}",
            "metadata": {
                "model": {
                    "provider": "mock",
                    "model": "mock",
                }
            },
        }


class DegradedAIProvider:
    """真实模型不可用时的降级回复。

    以前这里直接复用 MockAIProvider，结果模型欠费、超时的时候，用户对每一条消息
    （包括"你好"）都会收到同一段"我已经收到你的拍摄需求…"，看起来像是 agent 答错了，
    真正的故障却被藏了起来。降级回复必须说实话：这轮没能正常回答，原因在服务侧。
    具体错误只放在 metadata.fallback 里，不写给用户。
    """

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """生成真实模型不可用时的降级回复。"""
        lines = ["抱歉，AI 对话服务暂时不可用，这条消息我没能正常回答。"]
        if _has_candidate_context(messages):
            # 检索和工具调用是后端做的，模型挂掉不影响这部分结果，别把它藏起来。
            lines.append("本次在平台上查到的候选仍然在下方，可以直接点开查看。")
        lines.append("请稍后再发一次；如果一直这样，请联系管理员检查 AI 服务配置。")
        return {
            "content": "".join(lines),
            "metadata": {
                "model": {
                    "provider": "platform_degraded",
                    "model": "provider-unavailable",
                },
                "degraded": True,
            },
        }


class OpenAICompatibleProvider:
    """基于 OpenAI 兼容接口的 AI 对话实现。"""
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        provider_name: str = "openai_compatible",
        max_completion_tokens: int | None = None,
        extra_body: dict | None = None,
        supports_response_format: bool = True,
    ):
        """初始化兼容接口的地址、模型、密钥与超时配置。"""
        self.api_key = api_key
        self.base_url = (base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        self.model = model or settings.AI_MODEL
        self.timeout = timeout or settings.AI_REQUEST_TIMEOUT
        self.provider_name = provider_name
        self.max_completion_tokens = max_completion_tokens
        self.extra_body = dict(extra_body or {})
        self.supports_response_format = supports_response_format

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """调用兼容接口完成一次对话并返回回复内容。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else 0.7,
        }
        if response_format and self.supports_response_format:
            payload["response_format"] = response_format
        if self.max_completion_tokens is not None:
            payload["max_completion_tokens"] = self.max_completion_tokens
        payload.update(self.extra_body)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = "AI 服务请求失败"
            try:
                error_data = exc.response.json()
                detail = error_data.get("error", {}).get("message") or error_data.get("message") or detail
            except ValueError:
                pass
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 服务暂时不可用") from exc

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = _response_text(choices[0].get("message", {}).get("content"))

        if not content:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 服务未返回有效内容")

        usage = data.get("usage") or {}
        return {
            "content": content,
            "metadata": {
                "model": {
                    "provider": self.provider_name,
                    "model": self.model,
                    "input_tokens": usage.get("prompt_tokens"),
                    "output_tokens": usage.get("completion_tokens"),
                }
            },
        }


class MimoProvider(OpenAICompatibleProvider):
    """小米 MiMo 全模态模型的 OpenAI 兼容实现。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int,
        max_completion_tokens: int,
        thinking_mode: str,
        response_format_enabled: bool,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            provider_name="mimo",
            max_completion_tokens=max_completion_tokens,
            extra_body={"thinking": {"type": thinking_mode}},
            supports_response_format=response_format_enabled,
        )


def _response_text(content: object) -> str:
    """兼容字符串和 OpenAI 多段内容格式，统一提取文本。"""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return "".join(parts)


def _last_user_message_has_image(messages: list[dict]) -> bool:
    """判断最后一条用户消息是否包含图片。"""
    user_messages = [message for message in messages if message.get("role") == "user"]
    if not user_messages:
        return False

    content = user_messages[-1].get("content")
    if not isinstance(content, list):
        return False

    return any(part.get("type") == "image_url" for part in content)


def _text_only_messages(messages: list[dict]) -> list[dict]:
    """移除消息中的图片部分，仅保留文本内容。"""
    sanitized = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            sanitized.append(message)
            continue

        text_parts = [
            part.get("text", "")
            for part in content
            if part.get("type") == "text" and part.get("text")
        ]
        if any(part.get("type") == "image_url" for part in content):
            text_parts.append("[历史图片已省略，当前由文本模型继续对话]")
        sanitized.append({
            **message,
            "content": "\n".join(text_parts).strip(),
        })
    return sanitized


class MultiAgentProvider:
    """按最后一条用户消息是否含图路由到文本或图像模型。"""
    def __init__(self, text_provider: AIProvider, image_provider: AIProvider):
        """保存文本与图像两个子提供者实例。"""
        self.text_provider = text_provider
        self.image_provider = image_provider

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """根据消息内容选择文本或图像模型完成对话。"""
        selected_agent = "image" if _last_user_message_has_image(messages) else "text"
        provider = self.image_provider if selected_agent == "image" else self.text_provider
        provider_messages = messages if selected_agent == "image" else _text_only_messages(messages)
        result = await provider.chat(
            provider_messages,
            temperature=temperature,
            response_format=response_format,
        )
        metadata = result.get("metadata") or {}
        return {
            **result,
            "metadata": {
                **metadata,
                "router": {
                    "provider": "multi_agent",
                    "selected_agent": selected_agent,
                    "rule": "last_user_message_contains_image",
                },
            },
        }


class ResilientAIProvider:
    """主 provider 失败时自动降级到备用 provider 的包装。"""
    def __init__(self, primary: AIProvider, fallback: AIProvider):
        """保存主用与备用两个提供者实例。"""
        self.primary = primary
        self.fallback = fallback

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """优先调用主提供者，异常时回退到备用提供者。"""
        try:
            return await self.primary.chat(
                messages,
                temperature=temperature,
                response_format=response_format,
            )
        except Exception as exc:
            result = await self.fallback.chat(
                messages,
                temperature=temperature,
                response_format=response_format,
            )
            metadata = result.get("metadata") or {}
            return {
                **result,
                "metadata": {
                    **metadata,
                    "fallback": {
                        "used": True,
                        "reason": type(exc).__name__,
                        "primary_error": str(exc)[:300],
                    },
                },
            }


class ResilientMultiAgentProvider(MultiAgentProvider):
    """带降级能力的多代理路由提供者。"""
    def __init__(self, text_provider: AIProvider, image_provider: AIProvider, fallback: AIProvider):
        """在父类基础上额外保存降级提供者。"""
        super().__init__(text_provider=text_provider, image_provider=image_provider)
        self.fallback = fallback

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """多代理对话失败时回退到备用提供者。"""
        try:
            return await super().chat(
                messages,
                temperature=temperature,
                response_format=response_format,
            )
        except Exception as exc:
            result = await self.fallback.chat(
                messages,
                temperature=temperature,
                response_format=response_format,
            )
            return {
                **result,
                "metadata": {
                    **(result.get("metadata") or {}),
                    "fallback": {
                        "used": True,
                        "reason": type(exc).__name__,
                        "primary_error": str(exc)[:300],
                    },
                },
            }


def _require_api_key(api_key: str | None, name: str) -> str:
    """校验 API 密钥已配置，缺失时抛出 500。"""
    if not api_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{name} 未配置")
    return api_key


def _mimo_provider() -> AIProvider:
    """创建统一承载文本、图片和结构化任务的 MiMo provider。"""
    primary = MimoProvider(
        api_key=_require_api_key(settings.MIMO_API_KEY or settings.AI_API_KEY, "MIMO_API_KEY 或 AI_API_KEY"),
        base_url=settings.MIMO_BASE_URL,
        model=settings.MIMO_MODEL,
        timeout=settings.AI_REQUEST_TIMEOUT,
        max_completion_tokens=settings.MIMO_MAX_COMPLETION_TOKENS,
        thinking_mode=settings.MIMO_THINKING_MODE,
        response_format_enabled=settings.MIMO_RESPONSE_FORMAT_ENABLED,
    )
    return ResilientAIProvider(primary, DegradedAIProvider()) if settings.AI_PROVIDER_FALLBACK_ENABLED else primary


def get_ai_provider() -> AIProvider:
    """根据配置创建并返回合适的 AI 提供者实例。"""
    provider = (settings.AI_PROVIDER or "mock").lower()
    if provider == "mock":
        return MockAIProvider()
    if provider == "mimo":
        return _mimo_provider()
    if provider == "openai_compatible":
        if not settings.AI_API_KEY:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI API key 未配置")
        primary = OpenAICompatibleProvider(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
            model=settings.AI_MODEL,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
        return ResilientAIProvider(primary, DegradedAIProvider()) if settings.AI_PROVIDER_FALLBACK_ENABLED else primary
    if provider == "multi_agent":
        text_provider = OpenAICompatibleProvider(
            api_key=_require_api_key(settings.DEEPSEEK_API_KEY, "DEEPSEEK_API_KEY"),
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            timeout=settings.AI_REQUEST_TIMEOUT,
            provider_name="deepseek",
        )
        image_provider = OpenAICompatibleProvider(
            api_key=_require_api_key(settings.QWEN_API_KEY or settings.AI_API_KEY, "QWEN_API_KEY 或 AI_API_KEY"),
            base_url=settings.QWEN_BASE_URL,
            model=settings.QWEN_MODEL,
            timeout=settings.AI_REQUEST_TIMEOUT,
            provider_name="qwen",
        )
        if settings.AI_PROVIDER_FALLBACK_ENABLED:
            return ResilientMultiAgentProvider(text_provider, image_provider, DegradedAIProvider())
        return MultiAgentProvider(text_provider=text_provider, image_provider=image_provider)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI provider 未配置")


def get_text_provider() -> AIProvider:
    """
    返回意图分类、决策等文本任务使用的 provider。
    MiMo 模式与主对话共用同一全模态模型；legacy multi_agent 模式仍绕过图片路由。
    """
    provider = (settings.AI_PROVIDER or "mock").lower()
    if provider == "mock":
        return MockAIProvider()
    if provider == "mimo":
        return _mimo_provider()
    if provider in ("openai_compatible",):
        if not settings.AI_API_KEY:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI API key 未配置")
        primary = OpenAICompatibleProvider(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
            model=settings.AI_MODEL,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
        return ResilientAIProvider(primary, DegradedAIProvider()) if settings.AI_PROVIDER_FALLBACK_ENABLED else primary
    if provider == "multi_agent":
        text_provider = OpenAICompatibleProvider(
            api_key=_require_api_key(settings.DEEPSEEK_API_KEY, "DEEPSEEK_API_KEY"),
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            timeout=settings.AI_REQUEST_TIMEOUT,
            provider_name="deepseek",
        )
        if settings.AI_PROVIDER_FALLBACK_ENABLED:
            return ResilientAIProvider(text_provider, DegradedAIProvider())
        return text_provider
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI provider 未配置")
