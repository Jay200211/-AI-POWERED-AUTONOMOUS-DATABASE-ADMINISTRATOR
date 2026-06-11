"""Tools for the agent."""
import json
from typing import Dict, Any
from db_connector import Database
from schema_inspector import SchemaInspector
from query_analyzer import QueryAnalyzer
from safety import classify
from config import CONFIG


class Tools:
    def __init__(self, db: Database):
        self.db = db
        self.current_database: str = CONFIG.db_name

    def list_databases(self) -> str:
        return json.dumps(SchemaInspector(self.db).databases())

    def set_database(self, database: str) -> str:
        CONFIG.db_name = database
        new_conn_str = CONFIG.connection_string()
        self.db.close()
        self.db._conn_str = new_conn_str
        self.db._connect()
        self.current_database = database
        return json.dumps({"status": "ok", "database": database})

    def get_schema_summary(self, schema: str = "dbo", database: str = None) -> str:
        if database and database != self.current_database:
            self.set_database(database)
        return SchemaInspector(self.db).summarize(schema)

    def run_query(self, sql: str, confirm: bool = False) -> str:
        category, normalized = classify(sql)
        if category == "dangerous":
            return json.dumps({"error": "dangerous_sql_blocked"})
        if category == "mutating" and CONFIG.read_only_mode and not confirm:
            return json.dumps({"error": "mutating_blocked_in_readonly"})
        try:
            rows = self.db.query(normalized)
            if not rows:
                return json.dumps({"rows": [], "rowcount": 0, "table": "(0 rows)"})
            return json.dumps({
                "rows": rows[:200], "rowcount": len(rows), "table": _to_table(rows)
            }, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def expensive_queries(self, top: int = 5) -> str:
        try:
            rows = QueryAnalyzer(self.db).expensive_queries(top)
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def missing_indexes(self, top: int = 5) -> str:
        try:
            rows = QueryAnalyzer(self.db).missing_indexes(top)
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def blocking_sessions(self) -> str:
        try:
            rows = QueryAnalyzer(self.db).blocking_sessions()
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def backup_status(self) -> str:
        try:
            rows = QueryAnalyzer(self.db).backup_status()
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def health_check(self) -> str:
        try:
            return json.dumps(self.db.health(), default=str)
        except Exception as e:
            return json.dumps({"error": "health_failed", "reason": str(e)})

    def pt_stats(self) -> str:
        try:
            rows = QueryAnalyzer(self.db).pt_stats()
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def database_size(self) -> str:
        try:
            rows = QueryAnalyzer(self.db).database_size()
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def active_sessions(self) -> str:
        try:
            rows = QueryAnalyzer(self.db).active_sessions()
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})

    def wait_stats(self) -> str:
        try:
            rows = QueryAnalyzer(self.db).wait_stats()
            return json.dumps({"rows": rows, "table": _to_table(rows)}, default=str)
        except Exception as e:
            return json.dumps({"error": "execution_failed", "reason": str(e)})


def _to_table(rows):
    if not rows:
        return "(no rows)"
    cols = list(rows[0].keys())
    widths = {c: max(len(c), max(len(str(r.get(c, ""))[:60]) for r in rows)) for c in cols}
    sep = "+".join("-" * (widths[c] + 2) for c in cols)
    sep = f"+{sep}+"
    header = "| " + " | ".join(c.ljust(widths[c]) for c in cols) + " |"
    lines = [sep, header, sep]
    for r in rows:
        line = "| " + " | ".join(str(r.get(c, ""))[:60].ljust(widths[c]) for c in cols) + " |"
        lines.append(line)
    lines.append(sep)
    return "\n".join(lines)
