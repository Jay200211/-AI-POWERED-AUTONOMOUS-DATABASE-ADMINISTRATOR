"""Test the agent directly."""
import sys
import traceback
from config import CONFIG
from db_connector import Database
from llm_engine import ModelRouter
from tools import Tools
from dba_agent import AutonomousDBA
from schema_cache import SchemaCache

print("=" * 50)
print("Testing AutoDBA Agent")
print("=" * 50)

# Step 1: Database
print("\n[1] Connecting to database...")
try:
    db = Database()
    h = db.health()
    print(f"  ✓ Connected: {h['server']} / {h['db']}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: Tools
print("\n[2] Setting up tools...")
try:
    tools = Tools(db)
    print(f"  ✓ Tools ready")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 3: LLM
print("\n[3] Setting up LLM...")
try:
    llm = ModelRouter()
    if llm.health():
        print(f"  ✓ Ollama is running")
    else:
        print(f"  ⚠ Ollama not reachable")
except Exception as e:
    print(f"  ✗ FAILED: {e}")

# Step 4: Schema cache
print("\n[4] Loading schema cache...")
try:
    cache = SchemaCache(db)
    agent = AutonomousDBA(llm, tools, max_steps=4)
    agent.prime(cache)
    print(f"  ✓ Schema loaded, {len(agent._known_tables)} databases known")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 5: Test query
print("\n[5] Testing query: 'give me ids from customers'...")
try:
    result = agent.ask("give me ids from customers")
    print(f"  ✓ Result: {result}")
    print(f"  ✓ Rows: {len(agent.last_rows)}")
    if agent.last_rows:
        print(f"  ✓ First row: {agent.last_rows[0]}")
    print(f"  ✓ Model: {agent.last_model_used}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()

print("\n" + "=" * 50)
print("Test complete!")
