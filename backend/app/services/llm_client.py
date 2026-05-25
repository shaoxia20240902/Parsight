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
from app.config import LLM_MAX_TOKENS, LLM_TEMPERATURE

# 全局动态配置（仅管理端启用项，启动或 activate 时注入）
_dynamic_config: Optional[Dict[str, Any]] = None

_MISSING_ACTIVE_LLM_MSG = (
    "未加载管理端 LLM 配置：请在管理后台创建并「启用」一条 LLM 配置后重启服务"
)


def set_llm_config(config: Optional[Dict[str, Any]]) -> None:
    """设置全局 LLM 动态配置（管理端调用）"""
    global _dynamic_config
    _dynamic_config = config


def get_llm_config() -> Optional[Dict[str, Any]]:
    """获取当前全局 LLM 动态配置"""
    return _dynamic_config


def require_active_llm_config() -> Dict[str, Any]:
    """返回当前启用的管理端 LLM 配置；无配置时直接失败，不回退 .env。"""
    dyn = get_llm_config()
    if not dyn:
        raise RuntimeError(_MISSING_ACTIVE_LLM_MSG)
    api_base = (dyn.get("api_base") or "").strip()
    api_key = (dyn.get("api_key") or "").strip()
    primary_model = (dyn.get("primary_model") or "").strip()
    if not api_base:
        raise RuntimeError("管理端 LLM 配置缺少 api_base")
    if not api_key:
        raise RuntimeError("管理端 LLM 配置缺少 api_key")
    if not primary_model:
        raise RuntimeError("管理端 LLM 配置缺少 primary_model")
    return dyn


def get_primary_model() -> str:
    return (require_active_llm_config().get("primary_model") or "").strip()


def get_alt_model() -> str:
    alt = (require_active_llm_config().get("alt_model") or "").strip()
    if not alt:
        raise RuntimeError("管理端 LLM 配置缺少 alt_model，请在管理后台补全备用模型")
    return alt


logger = logging.getLogger(__name__)


def runtime_error_from_http_status(
    error: httpx.HTTPStatusError,
    *,
    context: str = "调用",
) -> RuntimeError:
    """将上游 LLM HTTP 错误转为可展示的运行时异常（不做静默兜底）。"""
    status = error.response.status_code
    if status == 402:
        return RuntimeError(
            "LLM API 账户余额不足（HTTP 402），请在模型服务商处充值后重试"
        )
    if status == 401:
        return RuntimeError(
            "LLM API Key 无效或未授权（HTTP 401），请检查管理后台 LLM 配置"
        )
    if status == 403:
        return RuntimeError("LLM API 访问被拒绝（HTTP 403），请检查 Key 与模型权限")
    if status == 429:
        return RuntimeError("LLM API 请求过于频繁（HTTP 429），请稍后重试")
    return RuntimeError(f"LLM API {context}失败: HTTP {status}")


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


# 全局共享 httpx 客户端（减少连接池碎片，增加并发能力）
_http_client_instance: httpx.AsyncClient | None = None


def _get_global_http_client() -> httpx.AsyncClient:
    global _http_client_instance
    if _http_client_instance is None or _http_client_instance.is_closed:
        # 不设置客户端级超时，让每个请求自行控制（避免 client timeout 与 request timeout 冲突）
        _http_client_instance = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _http_client_instance


class LLMClient:
    """OpenAI 兼容的 LLM 客户端（仅使用管理端已启用的配置）"""

    def __init__(self):
        # 不在构造时读取配置：路由模块导入早于 lifespan 加载 llm_configs
        self.max_tokens = LLM_MAX_TOKENS
        self.temperature = LLM_TEMPERATURE

    def _resolve_runtime(self) -> tuple[str, str, str]:
        """每次调用前解析当前启用的管理端配置（支持热更新）。"""
        dyn = require_active_llm_config()
        return (
            dyn["api_base"].rstrip("/"),
            dyn["api_key"],
            dyn["primary_model"],
        )

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
        api_base, api_key, primary_model = self._resolve_runtime()
        url = f"{api_base}/chat/completions"
        model = model_override or primary_model
        temp_val = temperature if temperature is not None else self.temperature
        tokens_val = max_tokens if max_tokens is not None else self.max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp_val,
            "max_tokens": tokens_val,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = _get_global_http_client()
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=httpx.Timeout(timeout))
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            _log_ai_call("chat_completion", model, messages, temp_val, tokens_val, content)
            return content
        except httpx.HTTPStatusError as e:
            _log_ai_call("chat_completion", model, messages, temp_val, tokens_val, None,
                         error=f"HTTP {e.response.status_code}: {e.response.text[:500]}")
            logger.error(f"LLM API HTTP error: {e.response.status_code} - {e.response.text}")
            raise runtime_error_from_http_status(e, context="调用") from e
        except httpx.RequestError as e:
            err_detail = f"{type(e).__name__}: {e}"
            if e.__cause__:
                err_detail += f" (caused by {type(e.__cause__).__name__}: {e.__cause__})"
            _log_ai_call("chat_completion", model, messages, temp_val, tokens_val, None,
                         error=f"网络错误: {err_detail}")
            logger.error(f"LLM API 网络错误: {err_detail}")
            raise RuntimeError(f"LLM API 网络错误: {err_detail}")

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 300.0,
        model_override: Optional[str] = None,
    ):
        """
        发送流式聊天请求，逐块 yield 文本内容

        Yields:
            每个 delta content 片段（可能为空字符串）
        """
        api_base, api_key, primary_model = self._resolve_runtime()
        url = f"{api_base}/chat/completions"
        model = model_override or primary_model
        temp_val = temperature if temperature is not None else self.temperature
        tokens_val = max_tokens if max_tokens is not None else self.max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp_val,
            "max_tokens": tokens_val,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = _get_global_http_client()
        try:
            async with client.stream(
                "POST", url, json=payload, headers=headers, timeout=httpx.Timeout(timeout)
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip() or line.startswith(":"):
                        continue
                    if line == "data: [DONE]":
                        return
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content is not None:
                                yield content
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM Stream HTTP error: {e.response.status_code} - {e.response.text[:500]}")
            raise runtime_error_from_http_status(e, context="流式调用") from e
        except httpx.RequestError as e:
            err_detail = f"{type(e).__name__}: {e}"
            if e.__cause__:
                err_detail += f" (caused by {type(e.__cause__).__name__}: {e.__cause__})"
            logger.error(f"LLM Stream 网络错误: {err_detail}")
            raise RuntimeError(f"LLM API 网络错误: {err_detail}")

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
        api_base, api_key, primary_model = self._resolve_runtime()
        url = f"{api_base}/chat/completions"
        model = model_override or primary_model
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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = _get_global_http_client()
        data = None
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=httpx.Timeout(timeout))
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
            raise runtime_error_from_http_status(e, context="JSON 调用") from e
        except httpx.RequestError as e:
            err_detail = f"{type(e).__name__}: {e}"
            if e.__cause__:
                err_detail += f" (caused by {type(e.__cause__).__name__}: {e.__cause__})"
            _log_ai_call("chat_completion_json", model, json_messages, temp_val, tokens_val, None,
                         error=f"网络错误: {err_detail}")
            logger.error(f"LLM API 网络错误: {err_detail}")
            raise RuntimeError(f"LLM API 网络错误: {err_detail}")

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
