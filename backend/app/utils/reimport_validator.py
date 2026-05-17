"""校验更新导入文件与当前空间表结构是否一致。"""
from typing import Any, Dict, List


def _column_names(columns_data: Any) -> List[str]:
    if not columns_data:
        return []
    normalized: List[Dict[str, Any]] = []
    for c in columns_data:
        if isinstance(c, dict):
            normalized.append(c)
        elif isinstance(c, str):
            normalized.append({"name": c})
    return [str(c.get("name", "")) for c in normalized]


def validate_reimport_sheets(
    existing_tables: List[Dict[str, Any]],
    new_sheets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    对比当前空间已导入表与新文件各 Sheet 的字段名（含顺序）。

    Returns:
        {"valid": bool, "issues": [...], "warnings": [...]}
    """
    issues: List[Dict[str, Any]] = []
    existing_by_name = {t["sheet_name"]: t for t in existing_tables}
    new_by_name = {s["name"]: s for s in new_sheets}

    for sheet_name, table in existing_by_name.items():
        if sheet_name not in new_by_name:
            issues.append({
                "sheet_name": sheet_name,
                "type": "missing_sheet",
                "message": f"新文件中缺少 Sheet「{sheet_name}」",
            })
            continue

        existing_cols = _column_names(table.get("columns"))
        new_cols = _column_names(new_by_name[sheet_name].get("columns"))

        if existing_cols == new_cols:
            continue

        removed = [c for c in existing_cols if c not in new_cols]
        added = [c for c in new_cols if c not in existing_cols]
        reordered = (
            not removed
            and not added
            and set(existing_cols) == set(new_cols)
            and existing_cols != new_cols
        )

        detail_parts: List[str] = []
        if removed:
            detail_parts.append(f"缺少字段：{', '.join(removed)}")
        if added:
            detail_parts.append(f"新增字段：{', '.join(added)}")
        if reordered:
            detail_parts.append("字段顺序与当前表不一致")

        issues.append({
            "sheet_name": sheet_name,
            "type": "column_mismatch",
            "message": f"Sheet「{sheet_name}」字段与当前不一致",
            "detail": "；".join(detail_parts) if detail_parts else "字段名或顺序已变更",
            "expected_columns": existing_cols,
            "actual_columns": new_cols,
            "removed": removed,
            "added": added,
        })

    extra_sheets = [name for name in new_by_name if name not in existing_by_name]
    warnings = []
    for sheet_name in extra_sheets:
        warnings.append({
            "sheet_name": sheet_name,
            "type": "extra_sheet",
            "message": f"新文件包含未导入的 Sheet「{sheet_name}」，更新时将被忽略",
        })

    blocking = [i for i in issues if i["type"] in ("missing_sheet", "column_mismatch")]
    return {
        "valid": len(blocking) == 0,
        "issues": issues,
        "warnings": warnings,
    }
