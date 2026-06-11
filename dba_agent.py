"""AutoDBA agent - fast-path + LLM."""
import json
import re
from typing import List, Dict, Any, Optional
from llm_engine import OllamaLLM
from tools import Tools
from schema_cache import SchemaCache


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
        self.system_prompt: str = "You are AutoDBA."
        self._known_tables: Dict = {}

    def prime(self, schema_cache: SchemaCache):
        try:
            cache = schema_cache.load()
            if not cache:
                cache = schema_cache.refresh_current_db()
            self.system_prompt = self._build_prompt(cache)
            for db_name, tables in cache.items():
                self._known_tables[db_name.lower()] = list(tables.keys())
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
        name_lower = name.lower().strip().rstrip('.,!?s')
        for db_name, tables in self._known_tables.items():
            for t in tables:
                t_lower = t.lower()
                if t_lower == name_lower or t_lower.rstrip('s') == name_lower or name_lower in t_lower:
                    return (db_name, t)
        return None

    def _try_fast_path(self, user_message: str) -> bool:
        msg = user_message.lower().strip()
        # Find a table name
        found = None
        for db, tables in self._known_tables.items():
            for t in tables:
                if t.lower() in msg or t.lower().rstrip('s') in msg:
                    found = (db, t)
                    break
            if found:
                break

        if not found:
            return False

        db_name, full_table = found
        sql = None
        intent = "full"

        if any(kw in msg for kw in ["count", "how many"]):
            sql = f"SELECT COUNT(*) AS row_count FROM {db_name}.dbo.{full_table}"
            intent = "count"
        elif "id" in msg.split() or "ids" in msg:
            sql = f"SELECT id FROM {db_name}.dbo.{full_table}"
            intent = "ids"
        elif any(kw in msg for kw in ["column", "schema", "describe"]):
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

        result = self.tools.run_query(sql)
        try:
            obj = json.loads(result)
            if "rows" in obj:
                self.last_rows = obj["rows"]
                self.last_table = obj.get("table")
                self.last_model_used = f"fast-path ({intent})"
                self.last_action = {"step": 1, "tool": "run_query", "args": {"sql": sql}, "fast_path": True}
                return True
        except Exception:
            pass
        return False

    def ask(self, user_message: str) -> str:
        self.last_table = None
        self.last_rows = []
        self.last_action = None
        self.last_model_used = "unknown"

        if self._try_fast_path(user_message):
            if self.last_rows:
                return f"Found {len(self.last_rows)} row(s)."

        # LLM path
        self.last_model_used = "qwen2.5-coder:7b"
        self.history.append({"role": "user", "content": user_message})
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            raw = self.llm.chat(messages)
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

    def _dispatch(self, tool: str, args: Dict[str, Any]) -> str:
        fn = getattr(self.tools, tool, None)
        if fn is None:
            return json.dumps({"error": f"unknown tool: {tool}"})
        try:
            return fn(**args)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _extract_json(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"final": text}
