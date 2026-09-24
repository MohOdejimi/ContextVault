from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict 

class Settings(BaseSettings):
    mongo_uri: str
    mongo_db_name: str 
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env"
    )

settings = Settings()