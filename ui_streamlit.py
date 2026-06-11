"""AutoDBA Streamlit UI - Full version."""
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
from llm_engine import OllamaLLM
from tools import Tools
from dba_agent import AutonomousDBA
from schema_cache import SchemaCache

st.set_page_config(
    page_title="AI Powered Autonomous DBA",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    .pt-card { background: linear-gradient(135deg, #17a2b8 0%, #20c997 100%); padding: 10px; border-radius: 8px; color: white; margin: 4px 0; font-size: 12px; }
    .recent-query { background-color: #f0f2f6; padding: 5px 9px; border-radius: 5px; margin: 2px 0; font-size: 11px; border-left: 3px solid #4A90E2; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🤖 AI Powered Autonomous DBA</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="subtitle">Server: <b>{CONFIG.db_server}</b> | DB: <b>{CONFIG.db_name}</b> | '
    f'LLM: <b>{CONFIG.ollama_model_fast}</b></p>',
    unsafe_allow_html=True
)
st.markdown("---")

if "agent_ready" not in st.session_state:
    st.session_state.history = []
    st.session_state.recent = deque(maxlen=10)
    st.session_state.metrics = {"total": 0, "success": 0}
    st.session_state.last_model = "none"
    st.session_state.agent_ready = False
    st.session_state.agent = None
    st.session_state.db = None
    st.session_state.tools = None


@st.cache_resource
def bootstrap():
    db = Database()
    tools = Tools(db)
    llm = OllamaLLM(model=CONFIG.ollama_model_fast)
    agent = AutonomousDBA(llm, tools, max_steps=4)
    try:
        cache = SchemaCache(db)
        cache.refresh_all_databases()
        agent.prime(cache)
    except Exception as e:
        st.warning(f"Cache warning: {e}")
    return db, tools, llm, agent


if not st.session_state.agent_ready:
    with st.spinner("🔌 Connecting..."):
        try:
            db, tools, llm, agent = bootstrap()
            st.session_state.db = db
            st.session_state.tools = tools
            st.session_state.agent = agent
            st.session_state.agent_ready = True
        except Exception as e:
            st.error(f"❌ Bootstrap failed: {e}")
            st.code(traceback.format_exc())
            st.stop()

agent = st.session_state.agent
db = st.session_state.db
tools = st.session_state.tools

ollama_ok = OllamaLLM().health()
if not ollama_ok:
    st.warning("⚠️ Ollama not running! Start it: `ollama serve`")

# Sidebar
with st.sidebar:
    st.header("📊 Metrics")
    c1, c2 = st.columns(2)
    c1.markdown(
        f'<div class="metric-card"><div class="metric-label">Total</div>'
        f'<div class="metric-value">{st.session_state.metrics["total"]}</div></div>',
        unsafe_allow_html=True
    )
    c2.markdown(
        f'<div class="metric-card metric-card-green"><div class="metric-label">Success</div>'
        f'<div class="metric-value">{st.session_state.metrics["success"]}</div></div>',
        unsafe_allow_html=True
    )

    c3, c4 = st.columns(2)
    try:
        dbs = json.loads(tools.list_databases())
        c3.markdown(
            f'<div class="metric-card metric-card-orange"><div class="metric-label">Databases</div>'
            f'<div class="metric-value">{len(dbs)}</div></div>',
            unsafe_allow_html=True
        )
        tables = db.query("SELECT name FROM sys.tables")
        c4.markdown(
            f'<div class="metric-card metric-card-purple"><div class="metric-label">Tables</div>'
            f'<div class="metric-value">{len(tables)}</div></div>',
            unsafe_allow_html=True
        )
    except Exception:
        c3.markdown(
            f'<div class="metric-card metric-card-orange"><div class="metric-label">Databases</div>'
            f'<div class="metric-value">-</div></div>',
            unsafe_allow_html=True
        )
        c4.markdown(
            f'<div class="metric-card metric-card-purple"><div class="metric-label">Tables</div>'
            f'<div class="metric-value">-</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.subheader("🤖 Last Model")
    st.info(st.session_state.last_model)

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

    if st.button("📋 All Tables", use_container_width=True):
        try:
            rows = db.query("SELECT name FROM sys.tables ORDER BY name")
            st.dataframe(rows, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))

    if st.button("💰 Expensive", use_container_width=True):
        try:
            r = json.loads(tools.expensive_queries())
            if r.get("rows"):
                st.dataframe(r["rows"][:5], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))

    if st.button("🔍 Missing Idx", use_container_width=True):
        try:
            r = json.loads(tools.missing_indexes())
            if r.get("rows"):
                st.dataframe(r["rows"][:5], use_container_width=True, hide_index=True)
            else:
                st.info("✅ No missing indexes")
        except Exception as e:
            st.error(str(e))

    if st.button("🚫 Blocking", use_container_width=True):
        try:
            r = json.loads(tools.blocking_sessions())
            if r.get("rows"):
                st.dataframe(r["rows"], use_container_width=True, hide_index=True)
            else:
                st.success("✅ No blocking")
        except Exception as e:
            st.error(str(e))

    if st.button("💾 Backups", use_container_width=True):
        try:
            r = json.loads(tools.backup_status())
            if r.get("rows"):
                st.dataframe(r["rows"], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))

    st.markdown("---")
    st.subheader("📈 Pt Stats (Live)")
    try:
        pt = json.loads(tools.pt_stats())
        if pt.get("rows"):
            for row in pt["rows"]:
                st.markdown(
                    f'<div class="pt-card">'
                    f'<b>Connections:</b> {row.get("connection_count", row.get("user_connections", "-"))}<br>'
                    f'<b>Batch Req/s:</b> {row.get("batch_requests", row.get("batch_requests_per_sec", "-"))}<br>'
                    f'<b>Page Life Exp:</b> {row.get("page_life_expectancy", "-")}'
                    f'</div>',
                    unsafe_allow_html=True
                )
    except Exception:
        st.caption("Pt stats unavailable")

    st.markdown("---")
    st.subheader("🕒 Recent Queries")
    if st.session_state.recent:
        for q in reversed(list(st.session_state.recent)):
            st.markdown(
                f'<div class="recent-query"><b>{q["timestamp"]}</b><br>{q["query"][:50]}</div>',
                unsafe_allow_html=True
            )
    else:
        st.caption("No queries yet")

    st.markdown("---")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.recent.clear()
        st.session_state.metrics = {"total": 0, "success": 0}
        st.rerun()

# Main chat
st.subheader("💬 Chat with AutoDBA")

# Show chat history
for idx, h in enumerate(st.session_state.history):
    with st.chat_message(h["role"], avatar="🧑" if h["role"] == "user" else "🤖"):
        if h["role"] == "user":
            st.write(h["content"])
        else:
            if h.get("multi") and hasattr(agent, 'all_results') and len(agent.all_results) > 1:
                tab_labels = [f"Q{i+1}: {r['query'][:25]}" for i, r in enumerate(agent.all_results)]
                tabs = st.tabs(tab_labels)
                for tab, result in zip(tabs, agent.all_results):
                    with tab:
                        st.markdown(f"**Query:** `{result['query']}`")
                        st.markdown(f"**Result:** {result['result']}")
                        if result.get('rows') and len(result['rows']) > 0:
                            st.dataframe(
                                result['rows'],
                                use_container_width=True,
                                hide_index=True,
                                key=f"hist_multi_{idx}_{hash(result['query'])}"
                            )
            elif h.get("rows") and len(h["rows"]) > 0:
                st.dataframe(
                    h["rows"],
                    use_container_width=True,
                    hide_index=True,
                    key=f"hist_df_{idx}"
                )
            elif h.get("table"):
                st.code(h["table"], language="text")
            if h.get("error"):
                st.error(h["error"])
            else:
                content = h.get("content", "")
                if content:
                    clean = re.sub(r"<[^>]+>", "", content).strip()
                    if clean and not clean.startswith("+---"):
                        st.markdown(clean)
            if h.get("model"):
                st.caption(f"🤖 {h['model']}")

# Chat input
prompt = st.chat_input("Ask AutoDBA... (e.g. 'show customers; show orders' or 'give me ids from persons')")

if prompt:
    st.session_state.metrics["total"] += 1
    st.session_state.recent.append({
        "query": prompt,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.write(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        step_ph = st.empty()

        if not ollama_ok:
            st.error("❌ Ollama is not running. Start it: `ollama serve`")
            ans = "Ollama not running"
            err = "Ollama is not running"
            all_results = []
        else:
            with st.spinner("🧠 Thinking..."):
                try:
                    ans = agent.ask(prompt)
                    err = None
                    all_results = list(agent.all_results) if hasattr(agent, 'all_results') else []
                except Exception as e:
                    ans = ""
                    err = f"{e}"
                    all_results = []

            if err:
                st.error(err)
            elif agent.last_action and "tool" in agent.last_action:
                step_ph.markdown(
                    f'<div class="step-box"><b>Step {agent.last_action["step"]}</b> — '
                    f'{agent.last_action["tool"]} | {agent.last_model_used}</div>',
                    unsafe_allow_html=True
                )

            # Multi-query display
            if len(all_results) > 1:
                st.markdown(
                    f'<div class="result-box">✅ Multi-Query Results — '
                    f'{len(all_results)} queries executed</div>',
                    unsafe_allow_html=True
                )
                tab_labels = [f"Q{i+1}: {r['query'][:30]}" for i, r in enumerate(all_results)]
                tabs = st.tabs(tab_labels)
                for tab, result in zip(tabs, all_results):
                    with tab:
                        st.markdown(f"**Query:** `{result['query']}`")
                        st.markdown(f"**Status:** {result['result']}")
                        if result.get('rows') and len(result['rows']) > 0:
                            st.dataframe(
                                result['rows'],
                                use_container_width=True,
                                hide_index=True,
                                key=f"res_multi_{len(st.session_state.history)}_{hash(result['query'])}"
                            )
                        elif result.get('table'):
                            st.code(result['table'], language="text")
                        else:
                            st.warning(f"No rows returned for: {result['query']}")
            elif agent.last_rows and len(agent.last_rows) > 0:
                st.markdown(
                    f'<div class="result-box">✅ Query Results — '
                    f'{len(agent.last_rows)} row(s)</div>',
                    unsafe_allow_html=True
                )
                st.dataframe(
                    agent.last_rows,
                    use_container_width=True,
                    hide_index=True,
                    key=f"result_df_{len(st.session_state.history)}"
                )
            elif agent.last_table:
                st.markdown('<div class="result-box">✅ Query Results</div>', unsafe_allow_html=True)
                st.code(agent.last_table, language="text")
            elif not err:
                st.markdown(re.sub(r"<[^>]+>", "", ans))

            if not err:
                st.session_state.metrics["success"] += 1
                st.session_state.last_model = agent.last_model_used
                st.caption(f"🤖 {agent.last_model_used} | {len(agent.last_rows)} rows")

    is_multi = len(all_results) > 1
    st.session_state.history.append({
        "role": "assistant",
        "content": ans if not err else "",
        "table": agent.last_table if not err else None,
        "rows": agent.last_rows if not err else None,
        "model": agent.last_model_used if not err else None,
        "error": err,
        "multi": is_multi
    })
    st.rerun()
