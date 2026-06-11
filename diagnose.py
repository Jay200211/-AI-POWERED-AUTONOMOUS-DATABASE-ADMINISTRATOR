"""Quick diagnostic - run this to check everything."""
import requests
import sys

print("=" * 60)
print("AutoDBA Quick Diagnostic")
print("=" * 60)

# 1. Ollama running?
print("\n[1] Checking Ollama...")
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    if r.ok:
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"  ✓ Ollama is RUNNING")
        print(f"  ✓ {len(models)} model(s) installed:")
        for m in models:
            print(f"    - {m}")
        if not models:
            print(f"  ⚠ No models! Run: ollama pull qwen2.5:3b")
    else:
        print(f"  ✗ Ollama returned error: {r.status_code}")
        sys.exit(1)
except requests.ConnectionError:
    print(f"  ✗ Ollama NOT reachable at localhost:11434")
    print(f"  → Start it: open new terminal and run 'ollama serve'")
    sys.exit(1)
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

# 2. Test LLM chat
print("\n[2] Testing LLM chat...")
try:
    r = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen2.5:3b",
            "messages": [{"role": "user", "content": "say hi"}],
            "stream": False
        },
        timeout=30
    )
    if r.ok:
        msg = r.json().get("message", {}).get("content", "")
        print(f"  ✓ LLM responded: {msg[:100]}")
    else:
        print(f"  ✗ Chat failed: {r.status_code} - {r.text[:200]}")
except Exception as e:
    print(f"  ✗ Chat error: {e}")

# 3. SQL Server
print("\n[3] Checking SQL Server...")
try:
    from db_connector import Database
    h = Database().health()
    print(f"  ✓ Connected: {h['server']}")
    print(f"  ✓ Database: {h['db']}")
except Exception as e:
    print(f"  ✗ SQL Server error: {e}")

print("\n" + "=" * 60)
print("Done!")
