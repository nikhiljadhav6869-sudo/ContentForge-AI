from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_dir: str = ".data"
    database_url: str = "sqlite:///.data/contentforge.db"
    checkpoint_url: str = ""
    redis_url: str = ""
    frontend_origin: str = "http://localhost:3000"
    demo_auth: bool = True
    registration_enabled: bool = True
    secure_cookies: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    source_hosts: str = "www.iea.org,afdc.energy.gov,www.energy.gov"
    input_cost_per_million: float = 0
    output_cost_per_million: float = 0
    demo_step_delay: float = 0.35


settings = Settings()
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
