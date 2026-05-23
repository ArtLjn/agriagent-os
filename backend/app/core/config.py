from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./farm_manager.db"
    project_name: str = "Farm Manager API"

    class Config:
        env_file = ".env"


settings = Settings()
