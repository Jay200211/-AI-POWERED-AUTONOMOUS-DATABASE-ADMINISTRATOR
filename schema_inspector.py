"""Schema discovery."""
from typing import Dict, List
from db_connector import Database


class SchemaInspector:
    def __init__(self, db: Database):
        self.db = db

    def databases(self) -> List[str]:
        rows = self.db.query("SELECT name FROM sys.databases WHERE state=0 ORDER BY name")
        return [r["name"] for r in rows]

    def tables(self, schema: str = "dbo") -> List[Dict]:
        return self.db.query(
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = ? ORDER BY TABLE_NAME", [schema])

    def columns(self, table: str, schema: str = "dbo") -> List[Dict]:
        return self.db.query(
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
            [schema, table])

    def summarize(self, schema: str = "dbo") -> str:
        tables = self.tables(schema)
        lines = [f"Schema {schema} contains {len(tables)} tables:"]
        for t in tables:
            if t["TABLE_TYPE"] != "BASE TABLE":
                continue
            cols = self.columns(t["TABLE_NAME"], schema)
            col_str = ", ".join(f"{c['COLUMN_NAME']} ({c['DATA_TYPE']})" for c in cols)
            lines.append(f"- {t['TABLE_NAME']}({col_str})")
        return "\n".join(lines)
