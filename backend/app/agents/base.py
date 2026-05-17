from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """智能体基类 - 所有神州问学智能体的接口定义"""

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
