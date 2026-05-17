import uuid
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.config import MAX_SHEETS
from app.utils.data_sampler import DataSampler


def sanitize_name(name: str) -> str:
    """清理名称：替换特殊字符为下划线"""
    return re.sub(r'[^\w\u4e00-\u9fff]', '_', str(name)).strip('_')


def build_table_name(username: str, space_seq_id: int, sheet_name: str) -> str:
    """
    动态表名：{用户名}_{空间自增ID}_{Sheet名}
    在同一用户 + 空间下，Sheet 名唯一即可保证表名唯一。
    """
    clean_user = sanitize_name(username) or "user"
    clean_sheet = sanitize_name(sheet_name) or "sheet"
    return f"{clean_user}_{space_seq_id}_{clean_sheet}"


def quote_ident(name: str) -> str:
    return f"`{str(name).replace('`', '')}`"


def deduplicate_columns(columns: List[str]) -> List[str]:
    """处理重复列名：追加 _1, _2..."""
    seen = {}
    result = []
    for col in columns:
        clean = sanitize_name(col)
        if clean in seen:
            seen[clean] += 1
            result.append(f"{clean}_{seen[clean]}")
        else:
            seen[clean] = 0
            result.append(clean)
    return result


class XlsxParser:
    """XLSX文件解析服务"""

    @staticmethod
    def parse_file(file_path: Path) -> Dict[str, Any]:
        """
        解析XLSX文件

        Returns:
            {
                "file_id": str,
                "sheets": [
                    {
                        "index": int,
                        "name": str,
                        "columns": List[Dict],
                        "row_count": int,
                        "data": pd.DataFrame
                    }
                ]
            }
        """
        file_id = str(uuid.uuid4())

        # 读取Excel文件
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        # 限制Sheet数量
        if len(sheet_names) > MAX_SHEETS:
            raise ValueError(f"文件包含{len(sheet_names)}个Sheet，超过最大限制{MAX_SHEETS}个")

        sheets = []
        for index, sheet_name in enumerate(sheet_names):
            # 读取Sheet数据
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            # 清理列名（去除前后空格）
            df.columns = df.columns.str.strip()

            # 处理重复列名
            deduped_cols = deduplicate_columns(list(df.columns))
            df.columns = deduped_cols

            # 获取列信息（用去重后的列名）
            columns_info = DataSampler.get_column_info(df)

            sheets.append({
                "index": index,
                "name": sheet_name,
                "columns": columns_info,
                "row_count": len(df),
                "data": df
            })

        return {
            "file_id": file_id,
            "sheets": sheets
        }

    @staticmethod
    def create_table_sql(table_name: str, columns: List[Dict[str, Any]]) -> str:
        """生成建表SQL"""
        col_definitions = []

        # 处理重复列名
        col_names = [col["name"] for col in columns]
        deduped_names = deduplicate_columns(col_names)

        for i, col in enumerate(columns):
            col_name = deduped_names[i]
            col_definitions.append(f'{quote_ident(col_name)} TEXT')

        sql = f'CREATE TABLE IF NOT EXISTS {quote_ident(table_name)} (\n'
        sql += ",\n".join(col_definitions)
        sql += "\n)"

        return sql

    @staticmethod
    def insert_data_sql(table_name: str, df: pd.DataFrame) -> Tuple[str, List[tuple]]:
        """生成插入数据SQL"""
        # 列名已经通过 deduplicate_columns 处理过
        clean_columns = list(df.columns)

        # 构建INSERT语句
        placeholders = ", ".join(["?" for _ in clean_columns])
        columns_str = ", ".join([quote_ident(col) for col in clean_columns])
        sql = f'INSERT INTO {quote_ident(table_name)} ({columns_str}) VALUES ({placeholders})'

        # 转换数据为元组列表
        values = []
        for _, row in df.iterrows():
            row_values = []
            for val in row:
                if pd.isna(val):
                    row_values.append(None)
                elif isinstance(val, pd.Timestamp):
                    row_values.append(str(val))
                else:
                    row_values.append(val)
            values.append(tuple(row_values))

        return sql, values

    @staticmethod
    def get_sample_data(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """获取采样数据（前N条 + 随机N条）"""
        first_n, random_n = DataSampler.sample_dataframe(df)

        first_n_records = first_n.to_dict("records")
        random_n_records = random_n.to_dict("records")

        # 转换值为字符串（确保JSON序列化）
        for records in [first_n_records, random_n_records]:
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, pd.Timestamp):
                        record[key] = str(value)
                    else:
                        record[key] = value

        return first_n_records, random_n_records
