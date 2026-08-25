"""
应用配置：通过环境变量与 .env 加载全部配置项
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 使用 pathlib 定位项目根目录，更简单可靠
# config.py 位于 backend/app/core/ 下，.parent.parent.parent.parent 就是项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    """应用全局配置，从 .env 与环境变量加载"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"

    # 数据库
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'photographer.db'}"
    AUTO_RUN_MIGRATIONS: bool = True

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # 账户身份与验证
    DEFAULT_PHONE_REGION: str = "CN"
    MULTI_IDENTIFIER_LOGIN_ENABLED: bool = True
    PHONE_REGISTRATION_REQUIRED: bool = True
    IDENTITY_VERIFICATION_ENABLED: bool = True
    PUBLIC_PROFILE_EMAIL_ENABLED: bool = True
    TOKEN_VERSION_ENFORCEMENT_ENABLED: bool = True
    VERIFICATION_CODE_TTL_SECONDS: int = 300
    VERIFICATION_TOKEN_TTL_SECONDS: int = 600
    VERIFICATION_RESEND_INTERVAL_SECONDS: int = 60
    VERIFICATION_MAX_ATTEMPTS: int = 5
    VERIFICATION_HOURLY_LIMIT: int = 5
    VERIFICATION_DAILY_LIMIT: int = 20
    SMS_PROVIDER: str = "memory"
    EMAIL_PROVIDER: str = "memory"

    # HTTP / CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # 支付与担保（阶段 C 默认使用内置模拟支付网关）
    PAYMENT_PROVIDER: str = "mock"
    PAYMENT_CALLBACK_SECRET: str = "change-payment-callback-secret-in-production"
    PAYMENT_WINDOW_MINUTES: int = 30
    DEFAULT_DEPOSIT_RATE: float = 0.30
    PLATFORM_FEE_RATE: float = 0.10
    ACCEPTANCE_WINDOW_DAYS: int = 5
    REVISION_RESPONSE_HOURS: int = 48
    ORDER_CONFIRMATION_HOURS: int = 24
    ORDER_AUTOMATION_POLL_SECONDS: int = 60
    OUTBOX_MAX_ATTEMPTS: int = 5
    PLATFORM_TIMEZONE: str = "Asia/Hong_Kong"

    # Cache
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    WEB_SEARCH_ENABLED: bool = False
    WEB_SEARCH_PROVIDER: str = "tavily"
    WEB_SEARCH_FALLBACK_PROVIDERS: str = ""
    WEB_SEARCH_API_KEY: str | None = None
    WEB_SEARCH_TIMEOUT_SECONDS: int = 10
    WEB_SEARCH_MAX_RESULTS: int = 5
    WEB_SEARCH_CACHE_TTL_SECONDS: int = 900
    WEB_SEARCH_MAX_PAGE_BYTES: int = 1000000
    WEB_SEARCH_MAX_CONTENT_CHARS: int = 12000
    WEB_SEARCH_MAX_TOTAL_CONTENT_CHARS: int = 50000
    WEB_SEARCH_MAX_REDIRECTS: int = 3
    WEB_SEARCH_RETRIES: int = 2
    WEB_SEARCH_CIRCUIT_FAILURE_THRESHOLD: int = 3
    WEB_SEARCH_CIRCUIT_COOLDOWN_SECONDS: int = 60

    # Map + weather context for the AI assistant
    GEOCODING_PROVIDER: str = "open_meteo"
    GEOCODING_API_KEY: str | None = None
    WEATHER_PROVIDER: str = "open_meteo"
    WEATHER_API_KEY: str | None = None
    MAP_WEATHER_TIMEOUT_SECONDS: int = 8
    MAP_WEATHER_CACHE_TTL_SECONDS: int = 900

    # Joint package recommendation rollout
    JOINT_RECOMMENDATION_ENABLED: bool = True
    JOINT_RECOMMENDATION_ROLLOUT_PERCENT: int = 100

    # 文件上传（现在会正确指向项目根目录下的 uploads 文件夹）
    UPLOAD_STORAGE: str = "local"
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB (图片)
    MAX_VIDEO_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB (视频)

    # S3 / MinIO
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET: str | None = None
    S3_PUBLIC_BASE_URL: str | None = None

    # AI assistant
    AI_PROVIDER: str = "mock"
    AI_API_KEY: str | None = None
    AI_BASE_URL: str | None = None
    AI_MODEL: str = "gpt-4.1-mini"
    AI_REQUEST_TIMEOUT: int = 60
    AI_MAX_HISTORY_MESSAGES: int = 20
    MIMO_API_KEY: str | None = None
    MIMO_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    MIMO_MODEL: str = "mimo-v2.5"
    MIMO_MAX_COMPLETION_TOKENS: int = 1024
    MIMO_THINKING_MODE: str = "disabled"
    MIMO_RESPONSE_FORMAT_ENABLED: bool = False
    AI_EMBEDDING_PROVIDER: str = "mock"
    AI_TEXT_EMBEDDING_PROVIDER: str | None = None
    AI_EMBEDDING_API_KEY: str | None = None
    AI_EMBEDDING_BASE_URL: str | None = None
    AI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    AI_EMBEDDING_VERSION: str = "v1"
    AI_EMBEDDING_DIMENSIONS: int = 1536
    AI_EMBEDDING_BATCH_SIZE: int = 32
    AI_HYBRID_SEMANTIC_WEIGHT: float = 0.40
    AI_HYBRID_KEYWORD_WEIGHT: float = 0.25
    AI_HYBRID_BUSINESS_WEIGHT: float = 0.20
    AI_HYBRID_QUALITY_WEIGHT: float = 0.10
    AI_HYBRID_FRESHNESS_WEIGHT: float = 0.05
    AI_HYBRID_MIN_SEMANTIC_SCORE: float = 0.18
    AI_MULTIMODAL_IMAGE_WEIGHT: float = 0.55
    AI_IMAGE_SEARCH_VISUAL_WEIGHT: float = 0.75
    AI_IMAGE_SEARCH_TEXT_WEIGHT: float = 0.10
    AI_IMAGE_SEARCH_KEYWORD_WEIGHT: float = 0.05
    AI_IMAGE_SEARCH_BUSINESS_WEIGHT: float = 0.03
    AI_IMAGE_SEARCH_QUALITY_WEIGHT: float = 0.05
    AI_IMAGE_SEARCH_FRESHNESS_WEIGHT: float = 0.02
    # Two-stage portfolio retrieval. RRF weights are rank weights, not score weights.
    AI_PORTFOLIO_RRF_K: int = 60
    AI_PORTFOLIO_RRF_IMAGE_WEIGHT: float = 1.0
    AI_PORTFOLIO_RRF_TEXT_WEIGHT: float = 1.0
    AI_PORTFOLIO_RRF_CANDIDATE_MULTIPLIER: int = 20
    AI_IMAGE_EMBEDDING_VERSION: str = "v1"
    AI_IMAGE_EMBEDDING_BATCH_SIZE: int = 32
    AI_IMAGE_EMBEDDING_PROVIDER: str = "mock"
    AI_IMAGE_EMBEDDING_MODEL: str = "google/siglip-base-patch16-224"
    AI_IMAGE_EMBEDDING_DIMENSIONS: int = 768
    AI_IMAGE_EMBEDDING_DEVICE: str = "cpu"
    AI_IMAGE_EMBEDDING_MAX_BYTES: int = 12 * 1024 * 1024
    AI_IMAGE_EMBEDDING_TIMEOUT_SECONDS: int = 20
    AI_PROMPT_VERSION: str = "agent_prompt_v1"
    AI_ORCHESTRATOR_VERSION: str = "deterministic_orchestrator_v2"
    AI_INDEX_VERSION: str = "resource_index_v3"
    AI_PROVIDER_FALLBACK_ENABLED: bool = True

    # LLM Intent Classifier
    AI_INTENT_CLASSIFIER_MODE: str = "hybrid"
    AI_INTENT_CLASSIFIER_MIN_CONFIDENCE: float = 0.72
    AI_INTENT_CLASSIFIER_TIMEOUT_SECONDS: int = 8
    AI_INTENT_CLASSIFIER_JSON_MODE: bool = True
    AI_INTENT_PROMPT_VERSION: str = "intent_classifier_v1"

    # 统一 Agent 决策层（阶段B）
    # legacy: 完全走既有意图路由；shadow: 只记录决策与差异，不改变行为；
    # tool_loop: 由决策层接管"聊天 + 读检索"，写操作仍走既有确认流程。
    AGENT_ROUTING_MODE: str = "tool_loop"
    # 阶段C 灰度：AGENT_ROUTING_MODE 是"命中灰度的目标模式"，未命中的身份走 BASELINE_MODE。
    # ROLLOUT_PERCENT 默认 100，所以只改 AGENT_ROUTING_MODE 时行为与阶段B 完全一致；
    # 想按比例灰度就把百分比调低（例如 tool_loop + 10），未命中的人仍旧留在 baseline。
    AGENT_ROUTING_BASELINE_MODE: str = "legacy"
    AGENT_ROUTING_ROLLOUT_PERCENT: int = 100
    # user: 按用户稳定分桶（默认，同一用户体验不跳变）；conversation: 按会话；global: 全量生效。
    AGENT_ROUTING_ROLLOUT_UNIT: str = "user"
    # 逗号分隔的 user id：白名单直接命中（测试环境与内测账号），黑名单优先级最高。
    AGENT_ROUTING_ROLLOUT_ALLOWLIST: str = ""
    AGENT_ROUTING_ROLLOUT_DENYLIST: str = ""
    # 阶段C §4-C.4：决策层接管时不再重复跑一次分类 LLM。默认关闭，等灰度指标稳定后再开。
    AI_DECISION_SKIPS_INTENT_CLASSIFIER: bool = False
    AI_AGENT_DECISION_MIN_CONFIDENCE: float = 0.72
    AI_AGENT_DECISION_JSON_MODE: bool = True
    AI_AGENT_DECISION_MAX_HISTORY: int = 6
    # 写工具是否进入给模型看的工具目录。即使为 True，决策层也只允许"提出"，
    # 真正落库仍由既有确认流程执行（§5.2）。
    AI_AGENT_DECISION_ALLOW_WRITE_TOOLS: bool = True
    AI_INDEX_WORKER_ENABLED: bool = True
    AI_INDEX_WORKER_POLL_SECONDS: int = 10
    AI_INDEX_MAX_ATTEMPTS: int = 5
    AI_CONVERSION_PRIOR_RATE: float = 0.10
    AI_CONVERSION_PRIOR_WEIGHT: int = 10
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    QWEN_API_KEY: str | None = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-vl-plus"

    @property
    def cors_origins_list(self) -> list[str]:
        """将 CORS_ORIGINS 字符串解析为允许的源列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
