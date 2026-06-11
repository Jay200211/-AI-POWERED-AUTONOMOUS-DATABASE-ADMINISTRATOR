"""CLI version - run with: python main.py"""
import json
import sys
import argparse
from config import CONFIG
from db_connector import Database
from llm_engine import ModelRouter
from tools import Tools
from dba_agent import AutonomousDBA
import json

print(f"🤖 AutoDBA — Server: {CONFIG.db_server} | DB: {CONFIG.db_name}")

if not ModelRouter().health():
    print(f"❌ Ollama not reachable. Start it and: ollama pull {CONFIG.ollama_model_fast}")
    sys.exit(1)

try:
    print(f"✓ Connected: {Database().health()['server']}")
except Exception as e:
    print(f"❌ SQL Server: {e}")
    sys.exit(1)

db = Database()
tools = Tools(db)
agent = AutonomousDBA(ModelRouter(), tools, max_steps=6)

parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", help="Single query")
args = parser.parse_args()

if args.query:
    print(agent.ask(args.query))
else:
    print("Commands: :exit | :health | :tables | :expensive | :missing | :blocks | :backups | :sizes | :sessions")
    while True:
        try:
            q = input("\nautodba> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q in (":exit", ":quit"): break
        if q == ":health": print(tools.health_check()); continue
        if q == ":tables": [print(t) for t in json.loads(tools.list_databases())]; continue
        if q == ":expensive": print(tools.expensive_queries()); continue
        if q == ":missing": print(tools.missing_indexes()); continue
        if q == ":blocks": print(tools.blocking_sessions()); continue
        if q == ":backups": print(tools.backup_status()); continue
        if q == ":sizes": print(tools.database_size()); continue
        if q == ":sessions": print(tools.active_sessions()); continue
        if q: print(agent.ask(q))
