"""AI 互动小游戏包。

除两个游戏的业务逻辑外，本包还提供跨游戏复用的**输入防护**工具：
公开部署后任何人可访问，所有用户输入都先经过长度约束，
避免超长文本烧穿 token 预算、撑爆上下文窗口，或把无关内容塞进提示词。
"""

# 单次行动的最大字符数（超出部分直接截断，保证游戏不中断）
MAX_ACTION_CHARS = 500
# 题目主题的最大字符数
MAX_TOPIC_CHARS = 30
# 猜谜作答的最大字符数
MAX_REPLY_CHARS = 200


def clamp_text(text, max_chars: int):
    """把用户输入裁剪到安全长度。

    返回 (安全文本, 是否被截断)。空输入返回 ("", False)，由调用方决定如何提示。
    """
    s = str(text or "").strip()
    if len(s) <= max_chars:
        return s, False
    return s[:max_chars], True
