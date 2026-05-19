"""
对话推荐问题生成 Agent：基于 Sheet 六维理解和关联总结，生成 3 个对话模式的推荐问题。
"""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

RECOMMENDATION_SYSTEM = """你是数据对话推荐问题设计专家。

## 任务
根据用户上传的 Excel 文件中所有 Sheet 的六维业务理解、字段画像和关联总结，为对话系统的 3 个模式分别设计推荐问题。

## 输入说明
- `sheets`: 每个 Sheet 的六维理解全文、字段列表、样本数据
- `relations_summary`: 跨表关联总结（可能为空）
- `file_summary`: 文件整体业务描述

## 输出格式（严格 JSON）
{
  "insight_groups": [
    {
      "title": "分组标题（4-8字，基于数据特征）",
      "questions": ["问题1", "问题2", "问题3"]
    }
  ],
  "deep_questions": ["深度问题1", "深度问题2", "深度问题3"],
  "builder_questions": ["构建问题1", "构建问题2", "构建问题3"]
}

## 设计原则
1. **字段真实存在**：问题中的字段名必须来自输入中的真实字段，禁止编造。
2. **去业务化**：不要出现"销售""客户""订单""库存"等具体业务词汇。使用"数据""记录""字段""维度""指标"等通用词。
3. **中性表达**：问题应适用于任何类型的数据文件（财务、人事、运营、教育等）。
4. **insight 模式**：3 组 × 3 个问题，每组有一个主题。主题基于数据的实际维度/指标特征。
5. **deep 模式**：3 个需要多步分析、对比、根因探索的问题。
6. **builder 模式**：3 个明确的报表/图表构建需求。
7. **多样性**：不同模式的问题不要重复。

## 示例（仅供参考，不要直接复制）
- insight: "各分类的数据量分布如何？", "数值最高的分组是哪些？", "不同维度间的对比情况如何？"
- deep: "某维度近阶段的变化趋势及可能原因", "各维度之间的关联性分析", "异常数据的识别与根因探索"
- builder: "查看某字段 Top10 和 Bottom10", "按某维度汇总对比", "筛选特定条件的数据明细"
"""


class ChatRecommendationAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["sheets"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": RECOMMENDATION_SYSTEM},
                {"role": "user", "content": json.dumps({
                    "sheets": input_data["sheets"],
                    "relations_summary": input_data.get("relations_summary", ""),
                    "file_summary": input_data.get("file_summary", ""),
                }, ensure_ascii=False)},
            ],
            temperature=0.3,
            max_tokens=4096,
            timeout=120,
        )
        if not result.get("insight_groups"):
            raise ValueError("推荐问题生成未返回 insight_groups")
        return result
