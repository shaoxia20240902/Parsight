import itertools
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.db_service import DBService


NUMERIC_KEYWORDS = (
    "金额", "销售额", "收入", "营收", "利润", "成本", "费用", "价格", "单价",
    "数量", "销量", "件数", "人数", "次数", "订单数", "库存", "目标", "预算",
    "实际", "完成", "达成", "率", "占比", "比例", "score", "amount", "price",
    "cost", "revenue", "profit", "qty", "quantity", "count", "target", "actual",
    "rate", "ratio",
)
DATE_KEYWORDS = ("日期", "时间", "月份", "年月", "季度", "年份", "date", "time", "month", "year", "quarter")
ID_KEYWORDS = ("id", "编号", "编码", "单号", "订单号", "客户id", "商品id", "sku", "phone", "电话", "手机号")
RELATION_KEYWORDS = (
    "客户", "产品", "商品", "销售员", "人员", "员工", "区域", "省份", "城市",
    "门店", "渠道", "部门", "名称", "name", "customer", "product", "employee",
    "sales", "region", "city", "department",
)
DIMENSION_KEYWORDS = (
    "区域", "地区", "省", "城市", "渠道", "平台", "门店", "部门", "团队", "人员",
    "客户", "品类", "分类", "类型", "状态", "阶段", "品牌", "region", "city",
    "channel", "department", "category", "type", "status",
)
TARGET_KEYWORDS = ("目标", "预算", "计划", "target", "budget", "goal", "quota")
ACTUAL_KEYWORDS = ("实际", "完成", "达成", "销售额", "收入", "actual", "done", "finish", "revenue", "amount")


def normalize_name(name: str) -> str:
    return re.sub(r"[\s_\-（）()\[\]【】]+", "", str(name).lower())


def quote_ident(name: str) -> str:
    return f"`{str(name).replace('`', '')}`"


def numeric_expr(field: str) -> str:
    ident = quote_ident(field)
    return f"CAST(REPLACE(REPLACE(REPLACE({ident}, ',', ''), '￥', ''), '%', '') AS DECIMAL(18,4))"


def safe_alias(name: str) -> str:
    return str(name).replace("`", "").replace('"', "")


@dataclass
class FieldProfile:
    table_name: str
    sheet_name: str
    field: str
    semantic_type: str
    data_role: str
    unique_count: int
    row_count: int
    null_ratio: float
    numeric_ratio: float
    date_ratio: float
    sample_values: List[Any]
    filterable: bool
    groupable: bool
    recommended_aggregations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "sheet_name": self.sheet_name,
            "field": self.field,
            "semantic_type": self.semantic_type,
            "data_role": self.data_role,
            "unique_count": self.unique_count,
            "row_count": self.row_count,
            "null_ratio": self.null_ratio,
            "numeric_ratio": self.numeric_ratio,
            "date_ratio": self.date_ratio,
            "sample_values": self.sample_values,
            "filterable": self.filterable,
            "groupable": self.groupable,
            "recommended_aggregations": self.recommended_aggregations,
        }


class BIProfiler:
    """Builds BI-specific field profiles from imported Sheet tables."""

    def __init__(self, db_service: DBService):
        self.db = db_service

    async def profile_sheet(self, sheet: Dict[str, Any]) -> Dict[str, Any]:
        table_name = sheet["table_name"]
        row_count = int(sheet.get("row_count") or await self.db.get_table_row_count(table_name) or 0)
        columns = sheet.get("columns") or await self.db.get_table_columns(table_name)
        if isinstance(columns, str):
            columns = json.loads(columns)
            if isinstance(columns, str):
                columns = json.loads(columns)
        if not isinstance(columns, list):
            raise ValueError(f"Sheet {sheet.get('sheet_name') or table_name} 的 columns 元数据不是数组")
        sample = await self.db.fetch_sample_rows_from_table(table_name)
        sample_rows = sample.get("rows", [])

        fields = []
        for col in columns:
            field = col.get("name") if isinstance(col, dict) else str(col)
            values = [r.get(field) for r in sample_rows if r.get(field) not in (None, "")]
            sample_values = [v for v in values]
            unique_count = int((col.get("unique_count") if isinstance(col, dict) else 0) or len({str(v) for v in values}))
            null_ratio = self._null_ratio(sample_rows, field)
            numeric_ratio = self._numeric_ratio(values)
            date_ratio = self._date_ratio(values)
            semantic_type, data_role = self._classify_field(field, numeric_ratio, date_ratio, unique_count, row_count)
            filterable = data_role == "dimension" and unique_count > 1 and unique_count <= min(50, max(8, row_count * 0.3))
            groupable = data_role in ("dimension", "time") and unique_count > 1 and unique_count <= max(50, row_count * 0.5)
            aggregations = self._aggregations(data_role, semantic_type, numeric_ratio)
            fields.append(FieldProfile(
                table_name=table_name,
                sheet_name=sheet.get("sheet_name") or sheet.get("name") or table_name,
                field=field,
                semantic_type=semantic_type,
                data_role=data_role,
                unique_count=unique_count,
                row_count=row_count,
                null_ratio=null_ratio,
                numeric_ratio=numeric_ratio,
                date_ratio=date_ratio,
                sample_values=sample_values,
                filterable=filterable,
                groupable=groupable,
                recommended_aggregations=aggregations,
            ).to_dict())

        profile = {
            "sheet_name": sheet.get("sheet_name") or sheet.get("name") or table_name,
            "sheet_index": sheet.get("sheet_index") if sheet.get("sheet_index") is not None else sheet.get("index", 0),
            "table_name": table_name,
            "row_count": row_count,
            "summary": sheet.get("summary", ""),
            "fields": fields,
        }
        return await self.enrich_time_coverage(profile)

    async def enrich_time_coverage(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        time_fields = [f for f in profile["fields"] if f.get("data_role") == "time"]
        if not time_fields:
            profile["time_coverage"] = {"has_time": False, "period_count": 0}
            return profile
        tf = time_fields[0]["field"]
        table_name = profile["table_name"]
        bucket = f"DATE_FORMAT({quote_ident(tf)}, '%Y-%m')"
        try:
            rows = await self.db.execute_query(
                f"SELECT COUNT(DISTINCT {bucket}) AS cnt FROM {quote_ident(table_name)} "
                f"WHERE {quote_ident(tf)} IS NOT NULL AND {quote_ident(tf)} <> ''"
            )
            period_count = int(rows[0]["cnt"]) if rows else 0
        except Exception:
            period_count = 0
        profile["time_coverage"] = {
            "has_time": True,
            "time_field": tf,
            "period_count": period_count,
            "grain": "month",
        }
        return profile

    async def detect_relationships(self, sheet_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        relationships: List[Dict[str, Any]] = []
        for left, right in itertools.combinations(sheet_profiles, 2):
            left_fields = self._relationship_fields(left)
            right_fields = self._relationship_fields(right)
            for lf in left_fields:
                for rf in right_fields:
                    name_score = self._name_similarity(lf["field"], rf["field"])
                    if name_score < 0.55:
                        continue
                    overlap = await self._overlap_score(left["table_name"], right["table_name"], lf["field"], rf["field"])
                    score = round((name_score * 0.45 + overlap["overlap_ratio"] * 0.55) * 100)
                    if score >= 55 and overlap["overlap_count"] > 0:
                        relationships.append({
                            "id": f"rel_{len(relationships) + 1}",
                            "left_table": left["table_name"],
                            "left_sheet": left["sheet_name"],
                            "left_field": lf["field"],
                            "right_table": right["table_name"],
                            "right_sheet": right["sheet_name"],
                            "right_field": rf["field"],
                            "score": score,
                            "overlap_count": overlap["overlap_count"],
                            "overlap_ratio": overlap["overlap_ratio"],
                            "sample_values": overlap["sample_values"],
                            "relationship_type": self._relationship_type(lf["field"], rf["field"]),
                        })
        relationships.sort(key=lambda r: r["score"], reverse=True)
        return relationships[:5]

    def build_filter_candidates(self, sheet_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for sheet in sheet_profiles:
            for field in sheet["fields"]:
                if not field.get("filterable"):
                    continue
                key = self._canonical_key(field["field"])
                item = grouped.setdefault(key, {
                    "canonical_key": key,
                    "label": self._filter_label(key, field["field"]),
                    "type": "enum",
                    "options": [],
                    "applies_to": [],
                    "priority": self._filter_priority(key, field),
                })
                item["applies_to"].append({
                    "table_name": sheet["table_name"],
                    "field": field["field"],
                })
                for value in field.get("sample_values", []):
                    if value not in item["options"] and len(item["options"]) < 20:
                        item["options"].append(value)
                item["priority"] = max(item["priority"], self._filter_priority(key, field))

        filters = list(grouped.values())
        filters.sort(key=lambda f: (len(f["applies_to"]), f["priority"]), reverse=True)
        return filters[:6]

    def _relationship_fields(self, sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
        fields = []
        for field in sheet["fields"]:
            name = normalize_name(field["field"])
            if field["unique_count"] <= 1:
                continue
            if (
                any(k in name for k in ID_KEYWORDS)
                or any(k in name for k in RELATION_KEYWORDS)
                or field["data_role"] == "dimension"
            ):
                fields.append(field)
        return fields[:12]

    async def _overlap_score(self, left_table: str, right_table: str, left_field: str, right_field: str) -> Dict[str, Any]:
        sql = f"""
            SELECT COUNT(DISTINCT a.{quote_ident(left_field)}) AS overlap_count
            FROM {quote_ident(left_table)} a
            WHERE a.{quote_ident(left_field)} IS NOT NULL
              AND a.{quote_ident(left_field)} <> ''
              AND a.{quote_ident(left_field)} IN (
                SELECT DISTINCT b.{quote_ident(right_field)}
                FROM {quote_ident(right_table)} b
                WHERE b.{quote_ident(right_field)} IS NOT NULL
                  AND b.{quote_ident(right_field)} <> ''
              )
        """
        rows = await self.db.execute_query(sql)
        overlap_count = int(rows[0].get("overlap_count") or 0) if rows else 0
        sample_sql = f"""
            SELECT DISTINCT a.{quote_ident(left_field)} AS val
            FROM {quote_ident(left_table)} a
            WHERE a.{quote_ident(left_field)} IS NOT NULL
              AND a.{quote_ident(left_field)} <> ''
              AND a.{quote_ident(left_field)} IN (
                SELECT DISTINCT b.{quote_ident(right_field)}
                FROM {quote_ident(right_table)} b
                WHERE b.{quote_ident(right_field)} IS NOT NULL
                  AND b.{quote_ident(right_field)} <> ''
              )
            LIMIT 10
        """
        sample_rows = await self.db.execute_query(sample_sql)
        sample_values = [r.get("val") for r in sample_rows]
        left_unique = await self._distinct_count(left_table, left_field)
        right_unique = await self._distinct_count(right_table, right_field)
        denom = max(1, min(left_unique, right_unique))
        return {
            "overlap_count": overlap_count,
            "overlap_ratio": min(1.0, overlap_count / denom),
            "sample_values": sample_values,
        }

    async def _distinct_count(self, table_name: str, field: str) -> int:
        rows = await self.db.execute_query(
            f"SELECT COUNT(DISTINCT {quote_ident(field)}) AS cnt FROM {quote_ident(table_name)} "
            f"WHERE {quote_ident(field)} IS NOT NULL AND {quote_ident(field)} <> ''"
        )
        return int(rows[0].get("cnt") or 0) if rows else 0

    def _classify_field(self, field: str, numeric_ratio: float, date_ratio: float, unique_count: int, row_count: int) -> tuple[str, str]:
        name = normalize_name(field)
        if any(k in name for k in DATE_KEYWORDS) or date_ratio >= 0.7:
            return "date", "time"
        if any(k in name for k in ID_KEYWORDS):
            return "identifier", "dimension"
        if numeric_ratio >= 0.8 or any(k in name for k in NUMERIC_KEYWORDS):
            if any(k in name for k in TARGET_KEYWORDS):
                return "target", "metric"
            if "率" in name or "占比" in name or "rate" in name or "ratio" in name:
                return "ratio", "metric"
            if "金额" in name or "收入" in name or "利润" in name or "cost" in name or "amount" in name:
                return "currency", "metric"
            return "number", "metric"
        if any(k in name for k in DIMENSION_KEYWORDS) or unique_count <= min(50, max(8, row_count * 0.3)):
            return "category", "dimension"
        return "text", "detail"

    def _aggregations(self, data_role: str, semantic_type: str, numeric_ratio: float) -> List[str]:
        if data_role != "metric":
            return ["count"]
        if semantic_type == "ratio":
            return ["avg", "max", "min"]
        if numeric_ratio >= 0.8 or semantic_type in ("currency", "number", "target"):
            return ["sum", "avg", "max", "min"]
        return ["count"]

    def _numeric_ratio(self, values: List[Any]) -> float:
        if not values:
            return 0.0
        hits = 0
        for value in values:
            text = str(value).strip().replace(",", "").replace("￥", "").replace("%", "")
            try:
                float(text)
                hits += 1
            except ValueError:
                pass
        return hits / len(values)

    def _date_ratio(self, values: List[Any]) -> float:
        if not values:
            return 0.0
        patterns = [
            r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}",
            r"^\d{4}[-/]\d{1,2}$",
            r"^\d{4}年\d{1,2}月",
            r"^\d{4}Q[1-4]$",
        ]
        hits = sum(1 for v in values if any(re.search(p, str(v)) for p in patterns))
        return hits / len(values)

    def _null_ratio(self, rows: List[Dict[str, Any]], field: str) -> float:
        if not rows:
            return 0.0
        nulls = sum(1 for r in rows if r.get(field) in (None, ""))
        return nulls / len(rows)

    def _canonical_key(self, field: str) -> str:
        name = normalize_name(field)
        if any(k in name for k in ("区域", "地区", "大区", "region")):
            return "region"
        if any(k in name for k in ("城市", "city")):
            return "city"
        if any(k in name for k in ("月份", "年月", "month")):
            return "month"
        if any(k in name for k in ("日期", "date")):
            return "date"
        if any(k in name for k in ("渠道", "平台", "channel")):
            return "channel"
        if any(k in name for k in ("部门", "团队", "department")):
            return "department"
        if any(k in name for k in ("品类", "分类", "category")):
            return "category"
        if any(k in name for k in ("状态", "status")):
            return "status"
        return name[:24] or "filter"

    def _filter_label(self, key: str, default_label: str) -> str:
        labels = {
            "region": "区域",
            "city": "城市",
            "month": "月份",
            "date": "日期",
            "channel": "渠道",
            "department": "部门",
            "category": "分类",
            "status": "状态",
        }
        return labels.get(key, default_label)

    def _filter_priority(self, key: str, field: Dict[str, Any]) -> int:
        base = {
            "month": 95,
            "date": 92,
            "region": 90,
            "channel": 86,
            "city": 82,
            "department": 80,
            "category": 76,
            "status": 70,
        }.get(key, 55)
        if field.get("unique_count", 0) > 30:
            base -= 10
        return base

    def _name_similarity(self, left: str, right: str) -> float:
        l_name = normalize_name(left)
        r_name = normalize_name(right)
        if not l_name or not r_name:
            return 0.0
        if l_name == r_name:
            return 1.0
        if l_name in r_name or r_name in l_name:
            return 0.8
        l_tokens = set(re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", l_name))
        r_tokens = set(re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", r_name))
        if not l_tokens or not r_tokens:
            return 0.0
        return len(l_tokens & r_tokens) / len(l_tokens | r_tokens)

    def _relationship_type(self, left_field: str, right_field: str) -> str:
        name = normalize_name(left_field + right_field)
        if "客户" in name or "customer" in name:
            return "customer"
        if "商品" in name or "sku" in name or "产品" in name or "product" in name:
            return "product"
        if "订单" in name or "order" in name:
            return "order"
        return "lookup"
