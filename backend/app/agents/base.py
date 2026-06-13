from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.config import AGENT_MAX_RETRIES

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """智能体基类 — 统一 LLM 客户端、JSON 提取与重试逻辑。"""

    def __init__(self):
        # 延迟导入 LLMClient，避免 services 与 agents 包之间的循环导入
        from app.services.llm_client import LLMClient
        self.llm = LLMClient()

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行智能体任务

        Args:
            input_data: 输入数据，根据智能体类型不同而不同

        Returns:
            结构化JSON输出
        """
        pass

    def validate_input(self, input_data: Dict[str, Any], required_keys: list) -> bool:
        """验证输入数据是否包含必需的字段"""
        for key in required_keys:
            if key not in input_data:
                raise ValueError(f"Missing required key: {key}")
        return True

    async def _call_llm_with_retry(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """调用 LLM 并解析 JSON，失败自动重试。"""
        if max_retries is None:
            max_retries = AGENT_MAX_RETRIES

        # 延迟导入，避免循环导入
        from app.services.llm_client import get_primary_model
        model = model or get_primary_model()
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await self.llm.chat_completion_json(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    model_override=model,
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                msg = str(e)
                # 认证/授权/余额类错误直接抛出，不再重试
                if any(
                    token in msg
                    for token in ("HTTP 401", "HTTP 402", "HTTP 403", "余额不足", "未授权", "访问被拒绝")
                ):
                    raise
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"LLM 调用在 {max_retries + 1} 次尝试后仍失败: {last_error}")
