"""Schema cache."""
import json
import os
from typing import Dict
from db_connector import Database
from schema_inspector import SchemaInspector

CACHE_FILE = "schema_cache.json"


class SchemaCache:
    def __init__(self, db: Database):
        self.db = db
        self.cache: Dict = {}

    def refresh_current_db(self) -> Dict:
        insp = SchemaInspector(self.db)
        tables = insp.tables("dbo")
        result = {}
        for t in tables:
            if t["TABLE_TYPE"] == "BASE TABLE":
                cols = insp.columns(t["TABLE_NAME"], "dbo")
                result[t["TABLE_NAME"]] = [
                    {"name": c["COLUMN_NAME"], "type": c["DATA_TYPE"]} for c in cols]
        self.cache = {self.db.health().get("db", "current"): result}
        self._save()
        return self.cache

    def load(self) -> Dict:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}
        return self.cache

    def _save(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, default=str)
        except Exception:
            pass

    def as_prompt(self) -> str:
        if not self.cache:
            self.load()
        if not self.cache:
            return "(no schema cached)"
        lines = ["KNOWN TABLES:"]
        for db_name, tables in self.cache.items():
            if not tables:
                continue
            lines.append(f"\nDatabase: {db_name}")
            for tname, cols in tables.items():
                if not cols:
                    continue
                col_str = ", ".join(f"{c['name']}:{c['type']}" for c in cols)
                lines.append(f"  {tname}({col_str})")
        return "\n".join(lines)
