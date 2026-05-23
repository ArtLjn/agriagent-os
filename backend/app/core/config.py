from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，优先从环境变量读取，其次使用默认值。"""

    database_url: str = "sqlite:///./farm_manager.db"
    project_name: str = "Farm Manager API"
    ai_model: str = "qwen3.5-plus-2026-04-20"
    ai_api_key: str = ""
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    weather_latitude: float = 34.26
    weather_longitude: float = 117.18

    class Config:
        env_file = ".env"


settings = Settings()
