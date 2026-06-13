import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def json_safe(value: Any) -> Any:
    """Recursively convert DB/driver values into JSON-serializable primitives."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    return value


def normalize_columns(columns_data: Any) -> List[Dict[str, Any]]:
    """将 columns 数据规范化为统一的 List[Dict] 格式。

    兼容两种存储格式：
    - List[Dict]: [{"name": "col1", "type": "text"}, ...]  （正确格式）
    - List[str]:   ["col1", "col2", ...]                     （旧格式/异常数据）
    """
    if not columns_data:
        return []
    if isinstance(columns_data, str):
        columns_data = json.loads(columns_data)
    if not isinstance(columns_data, list):
        return []
    normalized = []
    for c in columns_data:
        if isinstance(c, dict):
            normalized.append(c)
        elif isinstance(c, str):
            normalized.append({"name": c, "type": "text"})
    return normalized


def quote_identifier(name: str) -> str:
    return f"`{str(name).replace('`', '')}`"


def serialize_cell(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (datetime,)):
        return val.isoformat()
    return val
