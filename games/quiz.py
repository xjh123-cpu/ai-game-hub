"""AI 猜谜闯关游戏逻辑（对应实验 2-2）。

实现「AI 出题 -> 玩家作答 -> AI 裁判 -> 更新积分」的完整闭环。
出题用高温保证多样性，裁判用低温保证判定稳定（生成与判定分离）。
"""
import random

from llm import chat_json, usage_of
from prompts import QUIZ_PROMPT, JUDGE_PROMPT


def ai_quiz(topic: str, difficulty: str = "中等", temperature: float = 1.0,
            exclude_answers=None):
    """让大模型围绕主题生成一道猜谜题。

    exclude_answers: 已出过的谜底列表，会注入提示词禁止重复，提升连续出题的多样性。
    返回：(data, usage)，data 为 {"question", "answer", "hint"}
    """
    exclude_line = ""
    if exclude_answers:
        items = "、".join(dict.fromkeys(str(a) for a in exclude_answers))
        exclude_line = (f"5. 以下谜底已经出过，本轮绝不能再出，"
                        f"也不得出其同义词或别称：{items}。")
    prompt = QUIZ_PROMPT.format(
        topic=topic, difficulty=difficulty,
        nonce=random.randint(1000, 9999),
        exclude_line=exclude_line,
    )
    data, resp = chat_json(
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    _validate_quiz(data)
    return data, usage_of(resp)


def judge(question: str, answer: str, user_reply: str):
    """让大模型判定玩家回答是否正确。

    裁判任务需要确定性，temperature 固定为 0.0。
    返回：(result, usage)，result 为 {"correct", "comment"}
    """
    prompt = JUDGE_PROMPT.format(
        question=question, answer=answer, user_reply=user_reply
    )
    data, resp = chat_json(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    if "correct" not in data:
        raise ValueError("裁判结果缺少 correct 字段")
    data["correct"] = bool(data["correct"])
    data["comment"] = str(data.get("comment", ""))
    return data, usage_of(resp)


def _validate_quiz(data: dict):
    """校验出题结果字段完整性。"""
    for field in ("question", "answer", "hint"):
        if field not in data or not str(data[field]).strip():
            raise ValueError(f"题目缺少 {field} 字段")
    return data
