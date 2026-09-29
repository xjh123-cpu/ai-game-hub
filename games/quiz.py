"""AI 猜谜闯关游戏逻辑（对应实验 2-2）。

实现「AI 出题 -> 玩家作答 -> AI 裁判 -> 更新积分」的完整闭环。
出题用高温保证多样性，裁判用低温保证判定稳定（生成与判定分离）。
"""
import random

from llm import chat_json, usage_of
from prompts import QUIZ_PROMPT, JUDGE_PROMPT, QUIZ_FACT_CHECK_PROMPT


def _empty_usage() -> dict:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _merge_usage(acc: dict, usage: dict | None) -> dict:
    """把单次调用用量累加进累计器。"""
    if usage:
        for key in acc:
            acc[key] += usage.get(key, 0)
    return acc


def _fact_check(topic: str, data: dict):
    """低温事实核查：核实谜面史实是否属实。返回 (ok, reason, usage)。"""
    prompt = QUIZ_FACT_CHECK_PROMPT.format(
        topic=topic, question=data["question"],
        answer=data["answer"], hint=data["hint"],
    )
    result, resp = chat_json(
        messages=[{"role": "user", "content": prompt}], temperature=0.0
    )
    usage = usage_of(resp)
    ok = bool(result.get("ok", False))
    return ok, str(result.get("reason", "")), usage


def ai_quiz(topic: str, difficulty: str = "中等", temperature: float = 1.0,
            exclude_answers=None, max_fact_retries: int = 2):
    """让大模型围绕主题生成一道猜谜题，并经事实核查把关。

    exclude_answers: 已出过的谜底列表，注入提示词禁止重复。
    生成后用低温核查史实，未通过则把错误点反馈给模型重新出题；
    连续重试仍不通过则抛出 ValueError，避免把胡编的题发给玩家。
    返回：(data, usage)，data 为 {"question", "answer", "hint"}，usage 为全流程累计 token。
    """
    exclude_line = ""
    if exclude_answers:
        items = "、".join(dict.fromkeys(str(a) for a in exclude_answers))
        exclude_line = (f"6. 以下谜底已经出过，本轮绝不能再出，"
                        f"也不得出其同义词或别称：{items}。")

    total = _empty_usage()
    feedback = None  # 上一版题目不合格的原因，反馈给模型重新出题
    for _ in range(max_fact_retries + 1):
        prompt = QUIZ_PROMPT.format(
            topic=topic, difficulty=difficulty,
            nonce=random.randint(1000, 9999),
            exclude_line=exclude_line,
        )
        if feedback:
            prompt += (f"\n注意：你上一版题目不合格（{feedback}），"
                       f"本轮必须修正该问题后重新出题。")
        data, resp = chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        _merge_usage(total, usage_of(resp))
        _validate_quiz(data)
        if _answer_leaked(data):
            feedback = (f"谜面或提示中直接出现了谜底「{data['answer']}」，"
                        f"泄露了答案，必须用间接描述让玩家猜")
            continue
        try:
            ok, reason, check_usage = _fact_check(topic, data)
        except Exception:  # noqa: BLE001 - 核查通道故障时放行，保证游戏可用
            return data, total
        _merge_usage(total, check_usage)
        if ok:
            return data, total
        feedback = f"事实核查未通过：{reason}"
    raise ValueError(
        f"连续 {max_fact_retries + 1} 次生成的谜题不合格"
        f"（最近一次问题：{feedback}），请重试或更换主题。"
    )


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


def _answer_leaked(data: dict) -> bool:
    """检查谜底是否直接出现在谜面或提示中（泄露答案）。

    例如谜面「白天是鸟儿，晚上是兽……名字叫蝙蝠」而谜底为「蝙蝠」，
    属于把答案写进了题目，必须拦截重新出题。
    """
    answer = str(data.get("answer", "")).strip()
    if not answer:
        return False
    text = str(data.get("question", "")) + str(data.get("hint", ""))
    return answer in text


def _validate_quiz(data: dict):
    """校验出题结果字段完整性。"""
    for field in ("question", "answer", "hint"):
        if field not in data or not str(data[field]).strip():
            raise ValueError(f"题目缺少 {field} 字段")
    return data
