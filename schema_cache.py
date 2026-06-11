"""Schema cache - scans all user databases."""
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

    def refresh_all_databases(self) -> Dict:
        """Scan ALL user databases and cache their tables."""
        insp = SchemaInspector(self.db)
        all_dbs = insp.databases()
        result = {}

        for db_name in all_dbs:
            # Skip system databases
            if db_name.lower() in ['master', 'model', 'msdb', 'tempdb']:
                continue
            try:
                db_conn_str = self._get_conn_for(db_name)
                db_inst = Database(db_conn_str)
                db_insp = SchemaInspector(db_inst)
                tables = db_insp.tables("dbo")
                table_info = {}
                for t in tables:
                    if t["TABLE_TYPE"] == "BASE TABLE":
                        cols = db_insp.columns(t["TABLE_NAME"], "dbo")
                        table_info[t["TABLE_NAME"]] = [
                            {"name": c["COLUMN_NAME"], "type": c["DATA_TYPE"]} for c in cols
                        ]
                if table_info:
                    result[db_name] = table_info
                db_inst.close()
            except Exception:
                continue

        self.cache = result
        self._save()
        return result

    def refresh_current_db(self) -> Dict:
        """Cache only the current database."""
        insp = SchemaInspector(self.db)
        tables = insp.tables("dbo")
        result = {}
        for t in tables:
            if t["TABLE_TYPE"] == "BASE TABLE":
                cols = insp.columns(t["TABLE_NAME"], "dbo")
                result[t["TABLE_NAME"]] = [
                    {"name": c["COLUMN_NAME"], "type": c["DATA_TYPE"]} for c in cols
                ]
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

    def _get_conn_for(self, db_name: str) -> str:
        """Build a connection string for a specific database."""
        from config import CONFIG
        if CONFIG.db_trusted:
            return (f"DRIVER={{{CONFIG.db_driver}}};SERVER={CONFIG.db_server};"
                    f"DATABASE={db_name};Trusted_Connection=yes;")
        return (f"DRIVER={{{CONFIG.db_driver}}};SERVER={CONFIG.db_server};"
                f"DATABASE={db_name};UID={CONFIG.db_user};PWD={CONFIG.db_password};")
