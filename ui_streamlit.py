"""AutoDBA Streamlit UI - Bulletproof version."""
import streamlit as st
import re
import sys
import io
import json
import time
import traceback
from datetime import datetime
from collections import deque

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

from config import CONFIG
from db_connector import Database
from llm_engine import ModelRouter, OllamaLLM
from tools import Tools
from dba_agent import AutonomousDBA
from schema_cache import SchemaCache

st.set_page_config(page_title="AI Powered Autonomous DBA", page_icon="🤖",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-title { font-size: 30px; font-weight: 700; color: #4A90E2; text-align: center; }
    .subtitle { font-size: 13px; color: #888; text-align: center; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 14px; border-radius: 10px; color: white; text-align: center; margin-bottom: 6px; }
    .metric-card-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .metric-card-orange { background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%); }
    .metric-card-purple { background: linear-gradient(135deg, #8e2de2 0%, #4a00e0 100%); }
    .metric-value { font-size: 22px; font-weight: bold; }
    .metric-label { font-size: 10px; opacity: 0.9; }
    .step-box { background-color: #E3F2FD; padding: 5px 9px; border-radius: 5px; border-left: 3px solid #1E88E5; margin: 3px 0; font-size: 11px; font-family: monospace; }
    .result-box { background-color: #E8F5E9; padding: 6px 10px; border-radius: 5px; border-left: 3px solid #4CAF50; margin: 4px 0; font-weight: bold; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🤖 AI Powered Autonomous DBA</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="subtitle">Server: <b>{CONFIG.db_server}</b> | DB: <b>{CONFIG.db_name}</b> | '
    f'LLM: <b>{CONFIG.ollama_model_fast}</b> / <b>{CONFIG.ollama_model_smart}</b></p>',
    unsafe_allow_html=True)
st.markdown("---")

# Session state
if "agent" not in st.session_state:
    st.session_state.history = []
    st.session_state.metrics = {"total": 0, "success": 0}


@st.cache_resource
def bootstrap():
    db = Database()
    tools = Tools(db)
    llm = ModelRouter()
    agent = AutonomousDBA(llm, tools, max_steps=4)
    try:
        cache = SchemaCache(db)
        agent.prime(cache)
    except Exception as e:
        st.error(f"Cache error: {e}")
    return db, tools, llm, agent


try:
    db, tools, llm, agent = bootstrap()
except Exception as e:
    st.error(f"❌ Bootstrap failed: {e}")
    st.code(traceback.format_exc())
    st.stop()

# Check Ollama
ollama_ok = OllamaLLM().health()
if not ollama_ok:
    st.warning("⚠️ Ollama not running! Open a terminal and run: `ollama serve`")

# Sidebar
with st.sidebar:
    st.header("📊 Metrics")
    c1, c2 = st.columns(2)
    c1.markdown(f'<div class="metric-card"><div class="metric-label">Total</div><div class="metric-value">{st.session_state.metrics["total"]}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card metric-card-green"><div class="metric-label">Success</div><div class="metric-value">{st.session_state.metrics["success"]}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("⚡ Quick Tools")
    try:
        dbs = json.loads(tools.list_databases())
        idx = dbs.index(CONFIG.db_name) if CONFIG.db_name in dbs else 0
        new_db = st.selectbox("Database", dbs, index=idx, key="db_sel")
        if new_db != CONFIG.db_name:
            tools.set_database(new_db)
            CONFIG.db_name = new_db
            st.rerun()
    except Exception as e:
        st.error(f"DB: {e}")

    if st.button("🏥 Health", use_container_width=True):
        try:
            st.json(json.loads(tools.health_check()))
        except Exception as e:
            st.error(str(e))
    if st.button("📋 Tables", use_container_width=True):
        try:
            st.dataframe(db.query("SELECT name FROM sys.tables ORDER BY name"), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))
    if st.button("💰 Expensive", use_container_width=True):
        try:
            r = json.loads(tools.expensive_queries())
            if r.get("rows"): st.dataframe(r["rows"][:5], use_container_width=True, hide_index=True)
            else: st.info("No data")
        except Exception as e:
            st.error(str(e))
    if st.button("🔍 Missing Idx", use_container_width=True):
        try:
            r = json.loads(tools.missing_indexes())
            if r.get("rows"): st.dataframe(r["rows"][:5], use_container_width=True, hide_index=True)
            else: st.info("No missing indexes")
        except Exception as e:
            st.error(str(e))
    if st.button("🚫 Blocking", use_container_width=True):
        try:
            r = json.loads(tools.blocking_sessions())
            if r.get("rows"): st.dataframe(r["rows"], use_container_width=True, hide_index=True)
            else: st.success("✅ None")
        except Exception as e:
            st.error(str(e))
    if st.button("💾 Backups", use_container_width=True):
        try:
            r = json.loads(tools.backup_status())
            if r.get("rows"): st.dataframe(r["rows"], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))

    st.markdown("---")
    st.subheader("📈 Pt Stats")
    if st.button("🔄 Refresh Pt Stats", use_container_width=True):
        try:
            r = json.loads(tools.pt_stats())
            if r.get("rows"):
                for row in r["rows"]:
                    st.json(row)
        except Exception as e:
            st.error(f"Pt stats error: {e}")

# Main chat area
st.subheader("💬 Chat")

# Show chat history
for h in st.session_state.history:
    with st.chat_message(h["role"], avatar="🧑" if h["role"] == "user" else "🤖"):
        if h["role"] == "user":
            st.write(h["content"])
        else:
            if h.get("rows"):
                st.dataframe(h["rows"], use_container_width=True, hide_index=True)
            elif h.get("table"):
                st.code(h["table"], language="text")
            if h.get("error"):
                st.error(h["error"])
            else:
                content = h.get("content", "")
                if content:
                    st.markdown(re.sub(r"<[^>]+>", "", content))
            if h.get("model"):
                st.caption(f"🤖 {h['model']}")

# Chat input
prompt = st.chat_input("Ask AutoDBA... (e.g. 'give me ids from customers')")

if prompt:
    st.session_state.metrics["total"] += 1

    # User message
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.write(prompt)

    # Agent response
    with st.chat_message("assistant", avatar="🤖"):
        step_ph = st.empty()

        if not ollama_ok:
            st.error("❌ Ollama is not running. Start it: `ollama serve` in a new terminal")
            ans = "Ollama not running"
            err = "Ollama is not running. Start it with: ollama serve"
        else:
            with st.spinner("🧠 Thinking..."):
                try:
                    ans = agent.ask(prompt)
                    err = None
                except Exception as e:
                    ans = ""
                    err = f"{e}\n\n{traceback.format_exc()}"

            # Show step
            if err:
                st.error(err)
            elif agent.last_action and "tool" in agent.last_action:
                step_ph.markdown(
                    f'<div class="step-box"><b>Step {agent.last_action["step"]}</b> — '
                    f'{agent.last_action["tool"]} | '
                    f'{agent.last_model_used}</div>',
                    unsafe_allow_html=True
                )

            # Show results
            if agent.last_rows:
                st.markdown('<div class="result-box">✅ Query Results</div>', unsafe_allow_html=True)
                st.dataframe(agent.last_rows, use_container_width=True, hide_index=True)
            elif agent.last_table:
                st.markdown('<div class="result-box">✅ Query Results</div>', unsafe_allow_html=True)
                st.code(agent.last_table, language="text")
            elif not err:
                st.markdown(re.sub(r"<[^>]+>", "", ans))

            # Update metrics
            if not err:
                st.session_state.metrics["success"] += 1
                st.caption(f"🤖 {agent.last_model_used}")

    # Save to history
    st.session_state.history.append({
        "role": "assistant",
        "content": ans if not err else "",
        "table": agent.last_table if not err else None,
        "rows": agent.last_rows if not err else None,
        "model": agent.last_model_used if not err else None,
        "error": err
    })
    st.rerun()
