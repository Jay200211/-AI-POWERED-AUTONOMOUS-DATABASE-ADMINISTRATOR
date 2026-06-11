"""Configuration loader for AutoDBA."""
import os
from dataclasses import dataclass

# Try to load .env, but don't fail if dotenv is missing
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed - that's ok, we have hardcoded fallbacks
    pass


def _bool(value: str, default: bool = False) -> bool:
    return (value or str(default)).strip().lower() in ("1", "yes", "true", "y")


@dataclass
class Config:
    db_server: str = os.getenv("DB_SERVER", "JAYENDRA\\SQLEXPRESS")
    db_name: str = os.getenv("DB_NAME", "MyDatabase")
    db_user: str = os.getenv("DB_USER", "")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_trusted: bool = _bool(os.getenv("DB_TRUSTED"), True)
    db_driver: str = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model_fast: str = os.getenv("OLLAMA_MODEL_FAST", "qwen2.5-coder:7b")
    ollama_model_smart: str = os.getenv("OLLAMA_MODEL_SMART", "qwen2.5-coder:7b")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    read_only_mode: bool = _bool(os.getenv("READ_ONLY_MODE"), True)
    auto_execute_safe: bool = _bool(os.getenv("AUTO_EXECUTE_SAFE"), False)

    def connection_string(self) -> str:
        if self.db_trusted:
            return (f"DRIVER={{{self.db_driver}}};SERVER={self.db_server};"
                    f"DATABASE={self.db_name};Trusted_Connection=yes;")
        return (f"DRIVER={{{self.db_driver}}};SERVER={self.db_server};"
                f"DATABASE={self.db_name};UID={self.db_user};PWD={self.db_password};")


CONFIG = Config()
