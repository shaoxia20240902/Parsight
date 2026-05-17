import pandas as pd
from typing import Tuple, List, Dict, Any
from app.config import SAMPLE_FIRST_N, SAMPLE_RANDOM_N


class DataSampler:
    """数据采样工具"""

    @staticmethod
    def sample_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        对DataFrame进行采样

        Returns:
            (前N条数据, 随机N条数据)
        """
        first_n = df.head(SAMPLE_FIRST_N)

        if len(df) <= SAMPLE_FIRST_N + SAMPLE_RANDOM_N:
            # 数据量不足，返回除前N条外的所有数据
            random_n = df.iloc[SAMPLE_FIRST_N:]
        else:
            # 随机采样
            remaining = df.iloc[SAMPLE_FIRST_N:]
            random_n = remaining.sample(n=min(SAMPLE_RANDOM_N, len(remaining)))

        return first_n, random_n

    @staticmethod
    def get_column_info(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """获取列信息"""
        columns_info = []

        for col in df.columns:
            col_data = df[col].dropna()

            # 推断类型
            col_type = DataSampler._infer_type(col_data)

            # 获取唯一值数量
            unique_count = col_data.nunique()

            # 获取样本值
            sample_values = col_data.head(5).tolist()

            columns_info.append({
                "name": str(col),
                "type": col_type,
                "unique_count": int(unique_count),
                "sample_values": [str(v) for v in sample_values]
            })

        return columns_info

    @staticmethod
    def _infer_type(series: pd.Series) -> str:
        """推断列的数据类型 — 统一为 text，避免导入时格式推断错误"""
        return "text"
