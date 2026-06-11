"""SQL safety classifier."""
import sqlparse


def classify(sql: str):
    if not sql or not sql.strip():
        return "dangerous", ""

    normalized = sqlparse.format(sql, strip_comments=True).strip()
    upper = normalized.upper()

    dangerous = ["DROP", "TRUNCATE", "ALTER", "CREATE", "EXEC", "GRANT", "REVOKE",
                 "DENY", "SHUTDOWN", "KILL", "BACKUP", "RESTORE"]
    if any(kw in upper for kw in dangerous):
        return "dangerous", normalized

    mutating = ["INSERT", "UPDATE", "DELETE", "MERGE", "BULK"]
    first = normalized.split()[0].upper() if normalized.split() else ""
    if first in mutating:
        return "mutating", normalized
    return "read_only", normalized
