"""大模型 API 封装：智谱 GLM（OpenAI 兼容接口）。

职责（对应实验 5-2 步骤 1）：
- 统一从环境变量读取密钥与配置（密钥绝不硬编码在代码里）
- 封装 chat / chat_json 调用
- 内置指数退避重试（遇 429/5xx/超时等错误最多重试 3 次）与统一异常处理
- 提供 token 用量统计，供成本控制面板使用

业务代码只依赖本模块，不直接依赖 SDK 细节。
"""
import os
import time
import json
import logging

import openai

logger = logging.getLogger("ai_game_hub.llm")

# ---------------------------------------------------------------------------
# 极简 .env 加载器：避免额外依赖 python-dotenv，import 本模块时自动执行一次
# ---------------------------------------------------------------------------
def _load_dotenv(path=".env"):
    """读取项目根目录 .env 文件，仅当环境变量尚未设置时才写入。"""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


_load_dotenv()

# ---------------------------------------------------------------------------
# 配置（全部来自环境变量，可在 .env 中覆盖）
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
MODEL = os.environ.get("GLM_MODEL", "glm-4-flash")
MAX_RETRIES = 3

_client = None


def _resolve_api_key() -> str:
    """按优先级解析 API Key：环境变量 -> st.secrets -> 本地 config.json。"""
    key = os.environ.get("GLM_API_KEY")
    if key:
        return key
    try:  # 云端部署（Streamlit Cloud / HF Spaces）：从平台 Secrets 读取
        import streamlit as st

        key = st.secrets.get("GLM_API_KEY", "")
    except Exception:  # noqa: BLE001 - 非 Streamlit 环境静默跳过
        key = ""
    if key:
        return key
    try:
        from storage import load_config
        key = load_config().get("api_key")
    except Exception:  # noqa: BLE001 - storage 不可用时静默降级
        key = None
    return key or ""


def get_client() -> openai.OpenAI:
    """获取全局单例客户端（懒加载）。"""
    global _client
    if _client is None:
        api_key = _resolve_api_key()
        if not api_key:
            raise RuntimeError(
                "未配置 API Key。请在应用内「设置」弹窗中填入智谱 GLM 密钥，"
                "或设置环境变量 GLM_API_KEY。"
            )
        _client = openai.OpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


def reset_client():
    """重置客户端缓存（修改密钥/模型后调用，使新配置生效）。"""
    global _client
    _client = None


def has_api_key() -> bool:
    """判断是否已配置 API Key。"""
    return bool(_resolve_api_key())


def save_api_key(key: str):
    """保存 API Key 到本地配置并重置客户端。"""
    from storage import load_config, save_config

    cfg = load_config()
    cfg["api_key"] = key.strip()
    save_config(cfg)
    reset_client()


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否值得重试：限流 / 超时 / 连接错误 / 服务端 5xx。"""
    return isinstance(
        exc,
        (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ),
    )


def _friendly_error(exc: Exception) -> str:
    """把 SDK 抛出的异常翻译成玩家能看懂的中文原因。

    统一异常处理不只是「不崩溃」，还要让用户知道「为什么失败、该怎么办」。
    """
    if isinstance(exc, openai.AuthenticationError):
        return "API Key 无效或已过期，请到「设置」中检查密钥"
    if isinstance(exc, openai.PermissionDeniedError):
        return "当前 API Key 无权访问该模型，或账户额度已用尽"
    if isinstance(exc, openai.NotFoundError):
        return f"模型「{MODEL}」不存在，请检查 GLM_MODEL 配置"
    if isinstance(exc, openai.RateLimitError):
        return "触发了服务端限流（429），请稍后再试"
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return "连接大模型服务失败，请检查网络或代理设置"
    if isinstance(exc, openai.BadRequestError):
        return f"请求参数不合法：{exc}"
    return str(exc)


def chat(messages, temperature=0.7, max_tokens=1024, response_format=None):
    """调用大模型对话接口，带指数退避重试与统一异常处理。

    参数：
        messages: 标准对话消息列表 [{role, content}, ...]
        temperature: 采样温度（0~1，glm-4-flash 上限为 1.0）
        max_tokens: 最大输出 token 数
        response_format: 可选，{"type": "json_object"} 强制 JSON 输出
    返回：
        openai 响应对象（choices[0].message.content 为回答，usage 为用量）
    """
    client = get_client()
    last_exc = None
    attempts = 0
    for attempt in range(MAX_RETRIES):
        attempts = attempt + 1
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception as exc:  # noqa: BLE001 - 统一捕获以便重试或抛出
            last_exc = exc
            if not _is_retryable(exc):
                # 密钥错误、参数错误等重试也不会成功，立即中断并给出准确原因，
                # 避免误报「已重试 N 次」误导排查方向
                raise RuntimeError(
                    f"大模型调用失败（{type(exc).__name__}，该错误重试无效，"
                    f"已立即中断）：{_friendly_error(exc)}"
                ) from exc
            if attempt == MAX_RETRIES - 1:
                break
            wait = 2 ** attempt  # 指数退避：1s -> 2s -> 4s
            logger.warning("第 %d 次调用失败（%s），%ds 后重试", attempts, exc, wait)
            time.sleep(wait)
    raise RuntimeError(
        f"大模型调用失败（可重试错误，已尝试 {attempts} 次仍失败）："
        f"{_friendly_error(last_exc)}"
    ) from last_exc


def parse_json(raw: str):
    """健壮地解析模型返回的 JSON。

    模型偶尔会在 JSON 前后附加解释文字或使用错误引号，这里先尝试直接解析，
    失败后提取首个 {...} 子串再次解析。
    """
    if raw is None:
        raise ValueError("模型返回为空")
    text = raw.strip()
    # 去掉可能的 markdown 代码块围栏
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError(f"模型未返回合法 JSON：{text[:200]}")


def chat_json(messages, temperature=0.7, max_tokens=1024):
    """调用大模型并直接返回解析后的 dict 与响应对象。"""
    resp = chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    data = parse_json(resp.choices[0].message.content)
    return data, resp


def usage_of(resp) -> dict:
    """从响应对象提取 token 用量统计。"""
    u = resp.usage
    return {
        "prompt_tokens": u.prompt_tokens,
        "completion_tokens": u.completion_tokens,
        "total_tokens": u.total_tokens,
    }
