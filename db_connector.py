"""SQL Server connection - production version."""
import pyodbc
import threading
from typing import Any, Iterable, List, Dict, Optional
from config import CONFIG


class Database:
    def __init__(self, conn_str: Optional[str] = None):
        self._conn_str = conn_str or CONFIG.connection_string()
        self._lock = threading.Lock()
        self._conn: Optional[pyodbc.Connection] = None
        self._connect()

    def _connect(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = pyodbc.connect(self._conn_str, timeout=10, autocommit=True)
        cur = self._conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchall()
        cur.close()

    def close(self):
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def query(self, sql, params=None):
        with self._lock:
            try:
                cur = self._conn.cursor()
                cur.execute(sql, list(params) if params else [])
                if cur.description is None:
                    cur.close()
                    return []
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                cur.close()
                return rows
            except Exception:
                try:
                    if self._conn:
                        self._conn.close()
                except Exception:
                    pass
                self._conn = None
                self._connect()
                cur = self._conn.cursor()
                cur.execute(sql, list(params) if params else [])
                if cur.description is None:
                    cur.close()
                    return []
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                cur.close()
                return rows

    def execute(self, sql, params=None):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, list(params) if params else [])
            rc = cur.rowcount
            cur.close()
            return rc

    def health(self):
        rows = self.query("SELECT @@SERVERNAME AS server, @@VERSION AS version, "
                          "DB_NAME() AS db, GETDATE() AS now")
        return rows[0] if rows else {}
