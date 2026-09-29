"""AI 游戏乐园 —— Streamlit 主程序（对应实验 5-2 步骤 3）。

只负责界面与流程编排，业务逻辑通过 import 调用 llm.py / prompts.py / games 包。
运行方式：streamlit run app.py
"""
import time

import streamlit as st

from prompts import ADVENTURE_SYSTEM_PROMPT
from games.adventure import new_history, adventure_turn
from games.quiz import ai_quiz, judge

# 智谱 glm-4-flash 为免费模型；此处保留单价占位，便于后续切换付费模型时估算成本
COST_PER_M_INPUT = 0.0      # 输入单价（元 / 百万 token）
COST_PER_M_OUTPUT = 0.0     # 输出单价（元 / 百万 token）

# ---------------------------------------------------------------------------
# 限流配置（公开部署防刷量，对应拓展任务）
# ---------------------------------------------------------------------------
RATE_MIN_INTERVAL = 2.0     # 相邻两次 API 调用的最小间隔（秒）
RATE_MAX_PER_MIN = 10       # 单会话每分钟最多 API 调用次数
RATE_SESSION_CAP = 200      # 单会话累计调用上限

st.set_page_config(page_title="AI 游戏乐园", page_icon="🎮", layout="wide")

# ---------------------------------------------------------------------------
# 会话状态初始化
# ---------------------------------------------------------------------------
if "tokens" not in st.session_state:
    st.session_state.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

if "adv" not in st.session_state:
    st.session_state.adv = {"history": new_history(), "story": None,
                            "options": [], "game_over": False, "log": []}

if "quiz" not in st.session_state:
    st.session_state.quiz = {"question": None, "answer": None, "hint": None,
                             "score": 0, "round": 0, "hint_used": False,
                             "answered": False}

if "call_times" not in st.session_state:
    st.session_state.call_times = []


def add_usage(usage):
    """累计 token 用量。"""
    st.session_state.tokens["prompt"] += usage["prompt_tokens"]
    st.session_state.tokens["completion"] += usage["completion_tokens"]
    st.session_state.tokens["total"] += usage["total_tokens"]
    st.session_state.tokens["calls"] += 1


def rate_limit_ok() -> bool:
    """会话级限流：间隔 / 每分钟次数 / 累计上限，防止公开部署后被恶意刷量。"""
    now = time.time()
    times = st.session_state.call_times
    if len(times) >= RATE_SESSION_CAP:
        st.error(f"已达单会话调用上限（{RATE_SESSION_CAP} 次），请点击「重置全部状态」后继续。")
        return False
    if len([t for t in times if now - t < 60]) >= RATE_MAX_PER_MIN:
        st.warning(f"调用太频繁（每分钟限 {RATE_MAX_PER_MIN} 次），请休息几秒再试。")
        return False
    if times and now - times[-1] < RATE_MIN_INTERVAL:
        st.warning("操作太快啦，请间隔约 2 秒再试。")
        return False
    st.session_state.call_times.append(now)
    return True


def estimated_cost():
    t = st.session_state.tokens
    return (t["prompt"] / 1_000_000 * COST_PER_M_INPUT
            + t["completion"] / 1_000_000 * COST_PER_M_OUTPUT)


# ---------------------------------------------------------------------------
# 侧边栏：游戏选择 + 成本面板
# ---------------------------------------------------------------------------
st.sidebar.title("🎮 AI 游戏乐园")
mode = st.sidebar.radio("选择游戏", ["🏰 AI 文字冒险", "🧩 AI 猜谜闯关"])

st.sidebar.markdown("---")
st.sidebar.subheader("📊 用量与成本")
t = st.session_state.tokens
st.sidebar.metric("API 调用次数", f"{t['calls']} 次")
st.sidebar.metric("输入 Token", f"{t['prompt']:,}")
st.sidebar.metric("输出 Token", f"{t['completion']:,}")
st.sidebar.metric("总 Token", f"{t['total']:,}")
st.sidebar.caption(f"预估成本：¥{estimated_cost():.6f}（glm-4-flash 免费模型）")
st.sidebar.caption(f"🔒 限流：间隔 {RATE_MIN_INTERVAL:.0f}s / 每分钟 {RATE_MAX_PER_MIN} 次 / 每会话 {RATE_SESSION_CAP} 次")

if st.sidebar.button("🔄 重置全部状态"):
    for key in ("adv", "quiz"):
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}
    st.rerun()


# ===========================================================================
# 游戏一：AI 文字冒险
# ===========================================================================
def render_adventure():
    st.title("🏰 AI 文字冒险")
    st.caption("由大模型实时生成剧情的文字冒险游戏，输入行动或点击选项推进剧情。")

    adv = st.session_state.adv

    # 展示剧情历史（GM 与玩家的对话）
    for role, text in adv["log"]:
        if role == "GM":
            with st.chat_message("assistant", avatar="🧙"):
                st.markdown(text)
        else:
            with st.chat_message("user", avatar="🧑"):
                st.markdown(text)

    # 游戏进行中：显示 3 个选项按钮 + 自由输入
    if not adv["game_over"]:
        if adv["options"]:
            st.markdown("**可选行动：**")
            cols = st.columns(3)
            for i, opt in enumerate(adv["options"]):
                if cols[i].button(opt, key=f"opt_{adv['history'].__len__()}_{i}"):
                    _do_adventure_turn(opt)

        with st.form("action_form", clear_on_submit=True):
            action = st.text_input("输入你的行动（或直接点击上方选项）：", placeholder="例如：走进森林深处")
            submitted = st.form_submit_button("🚀 行动")
            if submitted and action.strip():
                _do_adventure_turn(action.strip())

        if st.button("🎲 开始新游戏"):
            st.session_state.adv = {"history": new_history(), "story": None,
                                    "options": [], "game_over": False, "log": []}
            _do_adventure_turn("开始冒险")
    else:
        st.success("🎉 本局游戏结束！")
        if st.button("🎲 再来一局"):
            st.session_state.adv = {"history": new_history(), "story": None,
                                    "options": [], "game_over": False, "log": []}
            _do_adventure_turn("开始冒险")


def _do_adventure_turn(action: str):
    """执行一轮冒险并更新状态（带一次状态校验失败重试）。"""
    if not rate_limit_ok():
        return
    adv = st.session_state.adv
    for attempt in range(2):
        try:
            state, usage = adventure_turn(adv["history"], action, temperature=0.9)
            break
        except Exception as exc:
            if attempt == 0:
                # 清理上一次失败尝试遗留的 user 消息，避免历史里重复记录同一行动
                while adv["history"] and adv["history"][-1]["role"] == "user":
                    adv["history"].pop()
                st.warning(f"模型返回异常，正在重试…（{exc}）")
                continue
            st.error(f"游戏出错了：{exc}")
            return
    add_usage(usage)
    adv["story"] = state.get("story", "")
    adv["options"] = state.get("options", [])
    adv["game_over"] = state.get("game_over", False)
    adv["log"].append(("玩家", action))
    adv["log"].append(("GM", adv["story"]))


# ===========================================================================
# 游戏二：AI 猜谜闯关
# ===========================================================================
def render_quiz():
    st.title("🧩 AI 猜谜闯关")
    st.caption("AI 出题，你来作答。答对得分，答不出可用积分兑换提示。")

    q = st.session_state.quiz
    st.markdown(f"**当前积分：{q['score']}**　|　已答题数：{q['round']}")

    col1, col2 = st.columns([3, 1])
    topic = col1.text_input("题目主题", value="动物", placeholder="例如：动物、历史、科技…")
    difficulty = col2.selectbox("难度", ["简单", "中等", "困难"], index=1)

    if st.button("🎲 生成新题目", type="primary"):
        if not rate_limit_ok():
            st.stop()
        with st.spinner("AI 出题中…"):
            try:
                data, usage = ai_quiz(topic, difficulty, temperature=1.0)
            except Exception as exc:
                st.error(f"出题失败：{exc}")
                return
        add_usage(usage)
        q.update({"question": data["question"], "answer": data["answer"],
                  "hint": data["hint"], "hint_used": False, "answered": False})
        q["round"] += 1
        st.rerun()

    if q["question"]:
        st.markdown("### 🎯 题目")
        st.info(q["question"])

        if st.button("💡 消耗 1 积分查看提示", disabled=q["hint_used"] or q["score"] < 1):
            q["hint_used"] = True
            q["score"] -= 1
            st.rerun()
        if q["hint_used"]:
            st.markdown(f"**提示：** {q['hint']}")

        with st.form("answer_form", clear_on_submit=True):
            reply = st.text_input("你的答案：")
            submit = st.form_submit_button("✅ 提交答案")
            if submit and reply.strip():
                if not rate_limit_ok():
                    st.stop()
                with st.spinner("AI 裁判判定中…"):
                    try:
                        result, usage = judge(q["question"], q["answer"], reply.strip())
                    except Exception as exc:
                        st.error(f"判定失败：{exc}")
                        return
                add_usage(usage)
                q["answered"] = True
                if result["correct"]:
                    q["score"] += 5
                    st.success(f"✅ 回答正确！+5 分。{result['comment']}")
                else:
                    st.error(f"❌ 回答错误。{result['comment']}")
                st.caption(f"正确答案：{q['answer']}")
                st.rerun()


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
if mode == "🏰 AI 文字冒险":
    render_adventure()
else:
    render_quiz()
