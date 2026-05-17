"""
LLM 客户端 - 封装 OpenAI 兼容 API 调用

支持 OpenAI 官方及任意 OpenAI 兼容 API（通义千问、DeepSeek 等）。
未配置 API Key 时直接抛出异常，不使用 Mock 或规则兜底。
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from app.config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  AI 调用专用日志
# ─────────────────────────────────────────────

_AI_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "ai_calls.log"


def _init_ai_logger() -> logging.Logger:
    """初始化 AI 调用专用 logger，输出到独立日志文件"""
    ai_logger = logging.getLogger("ai_calls")
    ai_logger.setLevel(logging.INFO)
    ai_logger.propagate = False  # 不传播到根 logger

    if not ai_logger.handlers:
        _AI_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(_AI_LOG_PATH), encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        ai_logger.addHandler(handler)

    return ai_logger


ai_log = _init_ai_logger()
_ai_call_counter = 0

_SEPARATOR = "═" * 80
_SEPARATOR_THIN = "─" * 80


def _log_ai_call(
    call_type: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    result: Any,
    error: Optional[str] = None,
) -> None:
    """记录一次 AI 调用的完整请求和响应"""
    global _ai_call_counter
    _ai_call_counter += 1
    call_no = _ai_call_counter

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 标题 ──
    lines = [
        "",
        _SEPARATOR,
        f"  AI 调用 #{call_no}  |  {ts}  |  {call_type}  |  Model: {model}",
        f"  Temperature: {temperature}  |  Max Tokens: {max_tokens}",
        _SEPARATOR_THIN,
    ]

    # ── 请求：Messages ──
    lines.append("  【请求 - Messages】")
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "system":
            # 系统提示词只显示前 200 字符
            preview = content[:200].replace("\n", "\\n")
            if len(content) > 200:
                preview += f"... (总长 {len(content)} 字符)"
            lines.append(f"    [{i}] system: {preview}")
        else:
            lines.append(f"    [{i}] {role}:")
            # 用户消息缩进显示，便于阅读
            for line in content.split("\n"):
                lines.append(f"          {line}")

    lines.append(_SEPARATOR_THIN)

    # ── 响应 ──
    if error:
        lines.append(f"  【响应 - 错误】")
        lines.append(f"    {error}")
    else:
        lines.append(f"  【响应 - 返回内容】")
        if isinstance(result, dict):
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
            for line in result_str.split("\n"):
                lines.append(f"    {line}")
        elif isinstance(result, str):
            # 尝试格式化 JSON
            try:
                parsed = json.loads(result)
                result_str = json.dumps(parsed, ensure_ascii=False, indent=2)
                for line in result_str.split("\n"):
                    lines.append(f"    {line}")
            except (json.JSONDecodeError, TypeError):
                for line in result.split("\n"):
                    lines.append(f"    {line}")
        else:
            lines.append(f"    {result}")

    lines.append(_SEPARATOR)
    lines.append("")

    ai_log.info("\n".join(lines))


class LLMClient:
    """OpenAI 兼容的 LLM 客户端"""

    def __init__(self):
        self.api_base = LLM_API_BASE.rstrip("/")
        self.api_key = LLM_API_KEY
        self.model = LLM_MODEL
        self.max_tokens = LLM_MAX_TOKENS
        self.temperature = LLM_TEMPERATURE

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY 未配置，无法调用大模型")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 120.0,
        model_override: Optional[str] = None,
    ) -> str:
        """
        发送聊天请求，返回文本内容

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间（秒）
            model_override: 覆盖默认模型（用于多模型切换）

        Returns:
            模型回复的文本内容
        """
        self._require_api_key()

        url = f"{self.api_base}/chat/completions"
        model = model_override or self.model
        temp_val = temperature if temperature is not None else self.temperature
        tokens_val = max_tokens if max_tokens is not None else self.max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp_val,
            "max_tokens": tokens_val,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                _log_ai_call("chat_completion", model, messages, temp_val, tokens_val, content)
                return content
            except httpx.HTTPStatusError as e:
                _log_ai_call("chat_completion", model, messages, temp_val, tokens_val, None,
                             error=f"HTTP {e.response.status_code}: {e.response.text[:500]}")
                logger.error(f"LLM API HTTP error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"LLM API 调用失败: HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                _log_ai_call("chat_completion", model, messages, temp_val, tokens_val, None,
                             error=f"网络错误: {e}")
                logger.error(f"LLM API 网络错误: {e}")
                raise RuntimeError(f"LLM API 网络错误: {e}")

    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 120.0,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        发送聊天请求，返回解析后的 JSON

        优先使用 response_format 强制 JSON 输出，
        如果 API 不支持则从文本中提取 JSON
        """
        self._require_api_key()

        url = f"{self.api_base}/chat/completions"
        model = model_override or self.model
        temp_val = temperature if temperature is not None else self.temperature
        tokens_val = max_tokens if max_tokens is not None else self.max_tokens
        json_messages = self._ensure_json_instruction(messages)

        payload = {
            "model": model,
            "messages": json_messages,
            "temperature": temp_val,
            "max_tokens": tokens_val,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            data = None
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)
                _log_ai_call("chat_completion_json", model, json_messages, temp_val, tokens_val, result)
                return result
            except json.JSONDecodeError:
                if data:
                    content = data["choices"][0]["message"]["content"]
                    extracted = self._extract_json(content)
                    _log_ai_call("chat_completion_json", model, json_messages, temp_val, tokens_val, extracted,
                                 error=f"原始返回非JSON，已提取。原始内容前200字: {content[:200]}")
                    return extracted
                _log_ai_call("chat_completion_json", model, json_messages, temp_val, tokens_val, None,
                             error="LLM 返回内容无法解析（data is None）")
                raise RuntimeError("LLM 返回内容无法解析")
            except httpx.HTTPStatusError as e:
                _log_ai_call("chat_completion_json", model, json_messages, temp_val, tokens_val, None,
                             error=f"HTTP {e.response.status_code}: {e.response.text[:500]}")
                logger.error(f"LLM API HTTP error: {e.response.status_code} - {e.response.text[:500]}")
                raise RuntimeError(f"LLM API JSON 调用失败: HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                _log_ai_call("chat_completion_json", model, json_messages, temp_val, tokens_val, None,
                             error=f"网络错误: {e}")
                logger.error(f"LLM API 网络错误: {e}")
                raise RuntimeError(f"LLM API 网络错误: {e}")

    def _ensure_json_instruction(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Some OpenAI-compatible APIs require the literal word 'json' when response_format=json_object."""
        if any("json" in (msg.get("content") or "").lower() for msg in messages):
            return messages
        injected = list(messages)
        instruction = "You must output a valid JSON object only. Do not output markdown or extra text."
        if injected and injected[0].get("role") == "system":
            injected[0] = {
                **injected[0],
                "content": f"{injected[0].get('content', '')}\n\n{instruction}",
            }
        else:
            injected.insert(0, {"role": "system", "content": instruction})
        return injected

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON 对象"""
        # 尝试找到最外层的 JSON 对象
        text = text.strip()

        # 移除 markdown 代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试找到 JSON 对象边界
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:500]}...")
