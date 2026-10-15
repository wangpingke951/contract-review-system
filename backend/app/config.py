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

    # ——— 文件 ———
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ——— 服务 ———
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True

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
