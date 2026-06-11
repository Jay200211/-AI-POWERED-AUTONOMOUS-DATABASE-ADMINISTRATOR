"""AutoDBA agent - with multi-query, multi-database, and schema fallback support."""
import json
import re
from typing import List, Dict, Any, Optional
from llm_engine import OllamaLLM
from tools import Tools
from schema_cache import SchemaCache
from config import CONFIG


class AutonomousDBA:
    def __init__(self, llm, tools: Tools, max_steps: int = 3):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history: List[Dict[str, str]] = []
        self.last_table: Optional[str] = None
        self.last_rows: List[Dict] = []
        self.last_action: Optional[Dict] = None
        self.last_model_used: str = "none"
        self.last_sql: Optional[str] = None  # NEW: track SQL for debugging
        self.system_prompt: str = "You are AutoDBA."
        self._known_tables: Dict = {}
        self._table_to_db: Dict = {}
        self.all_results: List[Dict] = []

    def prime(self, schema_cache: SchemaCache):
        """Initialize the agent with schema from all databases."""
        try:
            cache = schema_cache.load()
            if not cache:
                cache = schema_cache.refresh_all_databases()
            self.system_prompt = self._build_prompt(cache)
            for db_name, tables in cache.items():
                self._known_tables[db_name.lower()] = list(tables.keys())
                for t in tables:
                    self._table_to_db[t.lower()] = db_name
        except Exception:
            self.system_prompt = "You are AutoDBA. Use run_query."

    def _build_prompt(self, cache: Dict) -> str:
        lines = ["Schema:"]
        for db_name, tables in cache.items():
            for tname, cols in tables.items():
                if not cols:
                    continue
                col_str = ", ".join(f"{c['name']}:{c['type']}" for c in cols)
                lines.append(f"  {db_name}.dbo.{tname}({col_str})")
        lines.append('Reply with JSON: {"tool":"run_query","args":{"sql":"..."}} or {"final":"answer"}')
        return "\n".join(lines)

    def _find_table(self, name: str):
        """Find a table by fuzzy name matching. Returns (db_name, table_name) or None."""
        name_lower = name.lower().strip().rstrip('.,!?s')
        for db_name, tables in self._known_tables.items():
            for t in tables:
                t_lower = t.lower()
                if t_lower == name_lower:
                    return (db_name, t)
                if t_lower.rstrip('s') == name_lower.rstrip('s'):
                    return (db_name, t)
                if name_lower in t_lower or t_lower in name_lower:
                    return (db_name, t)
        return None

    def _try_fast_path(self, user_message: str) -> bool:
        """Try to answer the query without calling the LLM."""
        msg = user_message.lower().strip()
        current_db = CONFIG.db_name

        # Find which database has the table
        target_db = None
        target_table = None
        for db_name, tables in self._known_tables.items():
            for t in tables:
                t_lower = t.lower()
                if t_lower in msg or t_lower.rstrip('s') in msg:
                    target_table = t
                    target_db = db_name
                    break
            if target_table:
                break

        if not target_table:
            return False

        # Use the table's actual database
        db_name = target_db if target_db else current_db
        full_table = target_table

        sql = None
        intent = "full"

        if any(kw in msg for kw in ["count", "how many"]):
            sql = f"SELECT COUNT(*) AS row_count FROM {db_name}.dbo.{full_table}"
            intent = "count"
        elif "id" in msg.split() or "ids" in msg.split():
            sql = f"SELECT id FROM {db_name}.dbo.{full_table}"
            intent = "ids"
        elif any(kw in msg for kw in ["column", "schema", "describe", "structure"]):
            sql = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{full_table}'"
            intent = "columns"
        elif "where" in msg:
            m = re.search(r"where\s+(\w+)\s*([<>=!]+)\s*(\w+)", msg)
            if m:
                col, op, val = m.groups()
                sql = f"SELECT * FROM {db_name}.dbo.{full_table} WHERE [{col}] {op} '{val}'"
                intent = "where"
        elif any(kw in msg for kw in ["top", "first"]):
            m = re.search(r"(?:top|first)\s+(\d+)", msg)
            if m:
                sql = f"SELECT TOP {m.group(1)} * FROM {db_name}.dbo.{full_table}"
                intent = "top"

        if not sql:
            sql = f"SELECT * FROM {db_name}.dbo.{full_table}"

        # Execute with schema fallback
        result_str = None
        actual_sql = sql
        for schema_try in ['dbo', 'guest', 'person', 'sales', 'hr', 'inventory']:
            try_sql = sql.replace(f".dbo.", f".{schema_try}.")
            res = self.tools.run_query(try_sql)
            try:
                obj = json.loads(res)
                if "rows" in obj:
                    if len(obj["rows"]) > 0 or "error" not in obj:
                        result_str = res
                        actual_sql = try_sql
                        break
                elif "error" not in obj:
                    result_str = res
                    actual_sql = try_sql
                    break
            except Exception:
                continue

        if result_str is None:
            result_str = self.tools.run_query(sql)
            actual_sql = sql

        self.last_sql = actual_sql

        try:
            obj = json.loads(result_str)
            if "rows" in obj:
                self.last_rows = obj["rows"]
                self.last_table = obj.get("table")
                self.last_model_used = f"fast-path ({intent}) from {db_name}"
                self.last_action = {
                    "step": 1,
                    "tool": "run_query",
                    "args": {"sql": actual_sql},
                    "fast_path": True,
                    "intent": intent,
                    "database": db_name
                }
                return True
            elif "error" in obj:
                self.last_rows = []
                self.last_table = None
                self.last_model_used = f"error: {obj.get('reason', 'unknown')}"
                self.last_action = {
                    "step": 1,
                    "tool": "run_query",
                    "args": {"sql": actual_sql},
                    "fast_path": True,
                    "error": obj.get('reason')
                }
                return True
        except Exception as e:
            self.last_rows = []
            self.last_model_used = f"exception: {e}"
        return False

    def ask(self, user_message: str) -> str:
        """Main entry point - supports multiple queries separated by ; or newlines."""
        queries = self._split_queries(user_message)
        if len(queries) > 1:
            return self._handle_multiple_queries(queries)
        return self._handle_single_query(user_message, is_multi=False)

    def _split_queries(self, user_message: str) -> List[str]:
        """Split a message into multiple queries."""
        parts = re.split(r'[;\n]', user_message)
        queries = []
        for p in parts:
            cleaned = p.strip()
            if cleaned and len(cleaned) > 3:
                queries.append(cleaned)
        return queries

    def _handle_single_query(self, user_message: str, is_multi: bool = False) -> str:
        """Handle a single query."""
        # Only reset if NOT part of multi-query
        if not is_multi:
            self.last_table = None
            self.last_rows = []
            self.last_action = None
            self.last_model_used = "unknown"
            self.last_sql = None
            self.all_results = []

        # Try fast path
        if self._try_fast_path(user_message):
            if self.last_rows:
                return f"Found {len(self.last_rows)} row(s)."
            elif "error" in self.last_model_used:
                return self.last_model_used

        # LLM path
        self.last_model_used = CONFIG.ollama_model_fast
        llm = self.llm
        if hasattr(self.llm, 'pick'):
            try:
                llm = self.llm.pick(user_message)
                if self.llm.last_used == "smart":
                    self.last_model_used = CONFIG.ollama_model_smart
            except Exception:
                pass

        self.history.append({"role": "user", "content": user_message})
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            raw = llm.chat(messages)
        except Exception as e:
            return f"LLM error: {e}"

        action = self._extract_json(raw)
        self.last_action = {"step": 1, "action": action}

        if "final" in action:
            return re.sub(r"<[^>]+>", "", action["final"]).strip() or "Done."

        if "tool" in action:
            observation = self._dispatch(action["tool"], action.get("args", {}))
            try:
                obs_obj = json.loads(observation)
                if "rows" in obs_obj and obs_obj["rows"]:
                    self.last_rows = obs_obj["rows"]
                    self.last_table = obs_obj.get("table")
                    return f"Found {len(self.last_rows)} row(s)."
                elif "error" in obs_obj:
                    return f"Error: {obs_obj.get('reason')}"
            except Exception:
                pass
            return observation[:500]

        return raw[:500]

    def _handle_multiple_queries(self, queries: List[str]) -> str:
        """Execute multiple queries and combine results."""
        self.all_results = []
        self.last_rows = []
        self.last_table = None
        self.last_action = None
        self.last_model_used = "multi-query"
        self.last_sql = None

        combined_summary = []
        for i, q in enumerate(queries, 1):
            # Keep connection alive
            try:
                self.tools.db.query("SELECT 1")
            except Exception:
                try:
                    self.tools.db._connect()
                except Exception:
                    pass

            result_msg = self._handle_single_query(q, is_multi=True)
            # Capture BEFORE next iteration overwrites
            captured_rows = list(self.last_rows) if self.last_rows else []
            captured_table = self.last_table
            captured_model = self.last_model_used
            captured_sql = self.last_sql

            self.all_results.append({
                "query": q,
                "result": result_msg,
                "rows": captured_rows,
                "table": captured_table,
                "model": captured_model,
                "sql": captured_sql
            })
            combined_summary.append(f"Q{i}: {q} → {result_msg}")

        # Set last_rows to ALL combined rows (for display)
        all_combined_rows = []
        for r in self.all_results:
            all_combined_rows.extend(r.get("rows", []))
        if all_combined_rows:
            self.last_rows = all_combined_rows

        return "\n".join(combined_summary)

    def _dispatch(self, tool: str, args: Dict[str, Any]) -> str:
        """Safely call a tool."""
        fn = getattr(self.tools, tool, None)
        if fn is None:
            return json.dumps({"error": f"unknown tool: {tool}"})
        try:
            return fn(**args)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"final": text}
