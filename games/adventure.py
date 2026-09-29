"""AI 文字冒险游戏逻辑（对应实验 2-1 / 实验 5-2）。

实现「玩家行动 -> 调用大模型 -> 解析 JSON -> 状态校验 -> 更新历史」的完整循环。
"""
from llm import chat, parse_json, usage_of
from prompts import ADVENTURE_SYSTEM_PROMPT


def new_history() -> list:
    """初始化对话历史，预置 system 消息固定 GM 身份与规则。"""
    return [{"role": "system", "content": ADVENTURE_SYSTEM_PROMPT}]


def adventure_turn(history: list, action: str, temperature: float = 0.9, max_retries: int = 2):
    """执行一轮文字冒险（含自我纠错重试）。

    参数：
        history: 对话历史（会被原地更新，追加 user 与 assistant 消息）
        action: 玩家本次行动
        temperature: 剧情生成用高温，保证剧情多样性
        max_retries: JSON 解析/字段校验失败时的最大重试次数
    返回：
        (state, usage) 其中 state 为 {"story", "options", "game_over"} 字典
    """
    history.append({"role": "user", "content": f"玩家行动：{action}"})
    last_err = None
    for attempt in range(max_retries + 1):
        messages = history[:]
        if last_err:
            # 自我纠错：把上次的格式错误反馈给模型，要求重新生成合法 JSON
            messages = history + [
                {"role": "user",
                 "content": f"你上次返回的内容不符合规则（{last_err}），"
                            f"请严格按照 system 要求重新返回合法 JSON。"}
            ]
        resp = chat(
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        try:
            state = _validate_state(parse_json(raw))
            history.append({"role": "assistant", "content": raw})
            return state, usage_of(resp)
        except ValueError as exc:
            last_err = str(exc)
    raise ValueError(f"多次尝试仍无法生成合法游戏状态：{last_err}")


def _validate_state(state) -> dict:
    """状态校验（对应思考题 2 的「第二层：状态校验」）。

    校验 story / options 字段存在、options 恰好 3 个、game_over 为布尔值。
    缺失或非法时抛出异常，由上层触发重新生成，避免带残缺状态继续游戏。
    额外兜底：模型遇到注入时可能误用 answer/reply/message 字段返回拒绝话术，
    此时将该内容转写为 story 并补充默认选项，保证游戏不中断。
    """
    if not isinstance(state, dict):
        raise ValueError("游戏状态必须是 JSON 对象")
    if "story" not in state:
        alt = state.get("answer") or state.get("reply") or state.get("message")
        if alt and isinstance(alt, str) and alt.strip():
            state["story"] = alt.strip()
            state.setdefault("options", ["继续前进", "观察四周", "稍作休息"])
            state.setdefault("game_over", False)
        else:
            raise ValueError("游戏状态缺少 story 字段")
    if "options" not in state:
        raise ValueError("游戏状态缺少 options 字段")
    if not isinstance(state.get("story"), str) or not state["story"].strip():
        raise ValueError("story 字段缺失或为空")
    opts = state.get("options")
    if not isinstance(opts, list) or len(opts) != 3:
        raise ValueError("options 必须是 3 个选项")
    if "game_over" in state and not isinstance(state["game_over"], bool):
        raise ValueError("game_over 必须是布尔值")
    # 统一字段类型，避免下游崩溃
    state["game_over"] = bool(state.get("game_over", False))
    state["options"] = [str(o) for o in opts]
    return state
