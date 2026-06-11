"""Create .env file."""
content = """DB_SERVER=JAYENDRA\\SQLEXPRESS
DB_NAME=MyDatabase
DB_USER=
DB_PASSWORD=
DB_TRUSTED=yes
DB_DRIVER=ODBC Driver 17 for SQL Server

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_FAST=qwen2.5:3b
OLLAMA_MODEL_SMART=llama3.1
LLM_TEMPERATURE=0.0

READ_ONLY_MODE=yes
AUTO_EXECUTE_SAFE=no
"""

with open(".env", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ .env file created!")
 