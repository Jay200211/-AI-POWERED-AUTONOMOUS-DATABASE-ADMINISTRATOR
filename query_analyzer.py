"""Performance analysis + Pt-stat monitoring."""
from typing import List, Dict
from db_connector import Database


class QueryAnalyzer:
    def __init__(self, db: Database):
        self.db = db

    def expensive_queries(self, top: int = 5) -> List[Dict]:
        sql = f"""
        SELECT TOP {int(top)} 
            total_worker_time/execution_count AS avg_cpu,
            total_elapsed_time/execution_count AS avg_elapsed,
            execution_count,
            SUBSTRING(st.text, (qs.statement_start_offset/2)+1,
                      (CASE qs.statement_end_offset WHEN -1 THEN DATALENGTH(st.text)
                       ELSE qs.statement_end_offset END - qs.statement_start_offset)/2 + 1
            ) AS query_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
        ORDER BY total_worker_time DESC
        """
        return self.db.query(sql)

    def missing_indexes(self, top: int = 5) -> List[Dict]:
        sql = f"""
        SELECT TOP {int(top)} 
            s.avg_total_user_cost * s.avg_user_impact * (s.user_seeks + s.user_scans) AS impact,
            d.statement AS table_name, d.equality_columns
        FROM sys.dm_db_missing_index_group_stats s
        JOIN sys.dm_db_missing_index_groups g ON s.group_handle = g.index_group_handle
        JOIN sys.dm_db_missing_index_details d ON g.index_handle = d.index_handle
        ORDER BY impact DESC
        """
        return self.db.query(sql)

    def blocking_sessions(self) -> List[Dict]:
        sql = """
        SELECT r.session_id, r.blocking_session_id, r.wait_type, r.wait_time,
               SUBSTRING(t.text, r.statement_start_offset/2,
                         (CASE r.statement_end_offset WHEN -1 THEN DATALENGTH(t.text)
                          ELSE r.statement_end_offset END - r.statement_start_offset)/2 + 1
               ) AS statement
        FROM sys.dm_exec_requests r
        CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
        WHERE r.blocking_session_id <> 0
        """
        return self.db.query(sql)

    def backup_status(self) -> List[Dict]:
        sql = """
        SELECT d.name AS database_name,
               ISNULL(CONVERT(varchar, MAX(b.backup_finish_date), 120), 'NEVER') AS last_backup
        FROM sys.databases d
        LEFT JOIN msdb.dbo.backupset b ON b.database_name = d.name AND b.type = 'D'
        WHERE d.state = 0
        GROUP BY d.name
        """
        return self.db.query(sql)

    def pt_stats(self) -> List[Dict]:
        """Server-level Pt (Performance Totals) statistics."""
        return self.db.query("""
            SELECT 
                cntr_value AS connection_count,
                (SELECT cntr_value FROM sys.dm_os_performance_counters 
                 WHERE counter_name = 'Batch Requests/sec') AS batch_requests,
                (SELECT cntr_value FROM sys.dm_os_performance_counters 
                 WHERE counter_name = 'SQL Compilations/sec') AS compilations,
                (SELECT cntr_value FROM sys.dm_os_performance_counters 
                 WHERE counter_name = 'Page life expectancy') AS page_life_expectancy
            FROM sys.dm_os_performance_counters
            WHERE counter_name = 'User Connections'
        """)

    def database_size(self) -> List[Dict]:
        return self.db.query("""
            SELECT DB_NAME(database_id) AS database_name,
                   SUM(size * 8.0 / 1024) AS size_mb
            FROM sys.master_files
            GROUP BY database_id
            ORDER BY size_mb DESC
        """)

    def active_sessions(self) -> List[Dict]:
        return self.db.query("""
            SELECT login_name, COUNT(*) AS session_count, 
                   MIN(login_time) AS oldest_session
            FROM sys.dm_exec_sessions
            WHERE is_user_process = 1
            GROUP BY login_name
            ORDER BY session_count DESC
        """)

    def wait_stats(self) -> List[Dict]:
        return self.db.query("""
            SELECT TOP 10 wait_type, waiting_tasks_count, 
                   wait_time_ms, max_wait_time_ms
            FROM sys.dm_os_wait_stats
            WHERE wait_type NOT LIKE '%SLEEP%' AND wait_type NOT LIKE '%IDLE%'
            ORDER BY wait_time_ms DESC
        """)
