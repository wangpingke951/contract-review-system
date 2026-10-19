"""
app/config.py — 全局配置
使用 pydantic-settings 从 .env 文件读取，带类型校验
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",     # 忽略 .env 里没用到的变量
    )

    # ——— MySQL ———
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "rootpass"
    MYSQL_DATABASE: str = "contract_review"

    # ——— Redis ———
    REDIS_URL: str = "redis://localhost:6379/0"

    # ——— JWT ———
    JWT_SECRET_KEY: str = Field("dev-secret-change-me", alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ——— ChromaDB ———
    # 本地开发：CHROMA_MODE=embedded（单进程无并发问题，数据存 CHROMA_PERSIST_DIR）
    # 生产：CHROMA_MODE=http，连 standalone server（CHROMA_HOST/CHROMA_PORT）
    CHROMA_MODE: str = "embedded"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # ——— LLM（在线 API）———
    LLM_PROVIDER: str = "doubao"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = ""

    # ——— Embedding（在线 API）———
    # EMBEDDING_PROVIDER: online=在线 API；local=ChromaDB 内置本地模型（无 Key 的开发兜底）
    # 注意：切换 provider 会改变向量维度，需清空 collection 重建
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_DIM: int = 1024
    EMBEDDING_BASE_URL: str = ""

    # ——— 多模态（图片合同识别）———
    # 图片不做本地 OCR，交给多模态模型逐字转录。
    # VISION_MODEL 必填（如 doubao-vision / qwen-vl-plus / Qwen/Qwen2.5-VL-7B-Instruct）；
    # VISION_API_KEY、VISION_BASE_URL 留空则继承 LLM_API_KEY / LLM_BASE_URL。
    VISION_MODEL: str = ""
    VISION_API_KEY: str = ""
    VISION_BASE_URL: str = ""

    # ——— 文件 ———
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ——— 服务 ———
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True

    # 单次审查的最长等待时间（秒）。超过则中断并提示用户稍后重试，
    # 避免同步请求长时间挂起占用连接（PRD 4.3 异常处理假设值 120 秒）
    REVIEW_TIMEOUT_SECONDS: int = 120

    # 审查执行方式（PRD 5.4 要求后台异步，用户可离开页面）
    # background = 进程内后台任务（本地开发默认，无需 Redis）
    # celery     = 交给 Celery worker（Docker 部署形态）
    # inline     = 请求内同步跑完（仅用于调试/测试）
    REVIEW_EXECUTION_MODE: str = "background"

    # 单次追问的最长等待时间（秒）。PRD 4.4 异常处理假设值 30 秒：
    # 超时先回已生成的部分，再提示「回复超时，请重试」
    CHAT_TIMEOUT_SECONDS: int = 30

    # ——— 限流（每用户每分钟），<=0 表示不限 ———
    RATE_LIMIT_REVIEW_PER_MINUTE: int = 10
    RATE_LIMIT_CHAT_PER_MINUTE: int = 30

    # ——— 自助注册 ———
    ALLOW_REGISTER: bool = True
    # 禁止注册的用户名（逗号分隔，小写比较），避免与系统/演示账号混淆
    RESERVED_USERNAMES_TEXT: str = "admin,root,system,administrator,superadmin,guest"

    # ——— 生产模式：由 FastAPI 托管前端构建产物 ———
    # 开启后访问 http://<host>:8000 直接是前端页面（SPA），无需再起 vite / nginx。
    # 前置条件：先执行 cd frontend && npm run build，生成 frontend/dist。
    # 适用于「内网穿透只映射一个端口」或「单机交付」的场景。
    SERVE_FRONTEND: bool = False

    @property
    def reserved_usernames(self) -> set[str]:
        return {
            n.strip().lower()
            for n in (self.RESERVED_USERNAMES_TEXT or "").split(",")
            if n.strip()
        }

    # ——— 计算属性 ———
    @property
    def mysql_dsn(self) -> str:
        """SQLAlchemy async 连接串（aiomysql）"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    @property
    def chroma_url(self) -> str:
        return f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例：全进程唯一 settings 实例"""
    return Settings()
