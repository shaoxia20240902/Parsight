"""BI 上下文：向 LLM 传递完整六维理解与字段画像（不做截断或压缩）。"""

from typing import Any, Dict, List


def full_field_profiles(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """返回 Sheet 全部字段画像，保留 profiler 中的完整 sample_values。"""
    rows: List[Dict[str, Any]] = []
    for field in profile.get("fields", []):
        rows.append({
            "field": field.get("field"),
            "semantic_type": field.get("semantic_type"),
            "data_role": field.get("data_role"),
            "unique_count": field.get("unique_count"),
            "row_count": field.get("row_count"),
            "null_ratio": field.get("null_ratio"),
            "numeric_ratio": field.get("numeric_ratio"),
            "date_ratio": field.get("date_ratio"),
            "filterable": field.get("filterable"),
            "groupable": field.get("groupable"),
            "recommended_aggregations": field.get("recommended_aggregations", []),
            "sample_values": field.get("sample_values", []),
        })
    return rows


def sheet_payload_for_llm(
    profile: Dict[str, Any],
    understanding_text: str,
    industry_guess: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "sheet_name": profile.get("sheet_name"),
        "table_name": profile.get("table_name"),
        "sheet_index": profile.get("sheet_index"),
        "row_count": profile.get("row_count"),
        "summary": profile.get("summary", ""),
        "key_dimensions": profile.get("key_dimensions", []),
        "key_metrics": profile.get("key_metrics", []),
        "data_granularity": profile.get("data_granularity", ""),
        "time_range": profile.get("time_range", ""),
        "time_coverage": profile.get("time_coverage", {}),
        "understanding_content": (understanding_text or "").strip(),
        "fields": full_field_profiles(profile),
        "industry_guess": industry_guess or {},
    }


def file_payload_for_industry(
    profiles: List[Dict[str, Any]],
    understanding_by_table: Dict[str, str],
) -> Dict[str, Any]:
    sheets = []
    for p in profiles:
        tn = p["table_name"]
        sheets.append({
            "sheet_name": p.get("sheet_name"),
            "table_name": tn,
            "row_count": p.get("row_count"),
            "summary": p.get("summary", ""),
            "key_dimensions": p.get("key_dimensions", []),
            "key_metrics": p.get("key_metrics", []),
            "understanding_content": (understanding_by_table.get(tn, "") or "").strip(),
            "fields": full_field_profiles(p),
        })
    return {"sheets": sheets}


def profile_for_planner(profile: Dict[str, Any], understanding_text: str = "") -> Dict[str, Any]:
    """BIPlanner 使用的完整 Sheet 上下文。"""
    payload = sheet_payload_for_llm(profile, understanding_text)
    return payload
