import re
from typing import Optional


class SQLValidator:
    """SQL安全校验工具"""

    # 禁止的SQL关键字
    FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
        "UNION", "INTO", "OUTFILE", "DUMPFILE"
    ]

    @classmethod
    def validate_select_only(cls, sql: str) -> bool:
        """验证SQL是否仅为SELECT语句"""
        # 去除注释和多余空白
        sql_clean = cls._clean_sql(sql)

        upper = sql_clean.upper()

        # 检查是否以 SELECT 或 WITH ... SELECT 开头
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            return False

        # 检查是否包含禁止的关键字
        for keyword in cls.FORBIDDEN_KEYWORDS:
            # 使用词边界匹配，避免误匹配
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, upper):
                return False

        if upper.startswith("WITH") and "SELECT" not in upper:
            return False

        return True

    @classmethod
    def sanitize_sql(cls, sql: str) -> Optional[str]:
        """清理和验证SQL，返回安全的SQL或None"""
        if not cls.validate_select_only(sql):
            return None

        # 移除尾部分号
        sql = sql.rstrip(";").strip()

        return sql

    @classmethod
    def _clean_sql(cls, sql: str) -> str:
        """清理SQL字符串"""
        # 移除单行注释
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        # 移除多行注释
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        # 移除多余空白
        sql = ' '.join(sql.split())
        return sql
