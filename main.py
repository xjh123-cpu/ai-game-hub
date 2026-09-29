"""AI 游戏乐园 —— 桌面应用入口（pywebview）。

创建一个原生桌面窗口，加载 desktop/index.html，并通过 js_api 把后端能力
（文字冒险、猜谜、配置、存档）暴露给前端 JavaScript 调用。

运行方式：python main.py
打包方式：见 build.spec / build_windows.bat / .github/workflows/build-windows.yml
"""
import os
import sys

import webview

from llm import has_api_key, save_api_key
from storage import (
    load_records,
    update_high_score,
    save_game,
    load_game,
    list_saves,
)
from games.adventure import new_history, adventure_turn
from games.quiz import ai_quiz, judge


def resource_path(rel: str) -> str:
    """解析资源路径：打包后从 PyInstaller 的临时目录读取，开发时从项目目录读取。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class Api:
    """暴露给前端 JS 的后端接口（window.pywebview.api.*）。"""

    def __init__(self):
        # 文字冒险状态
        self.adv_history = None
        self.adv_story = ""
        self.adv_options = []
        self.adv_game_over = False
        self.adv_turns = 0
        # 猜谜状态
        self.quiz_question = ""
        self.quiz_answer = ""
        self.quiz_hint = ""

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def has_key(self):
        return {"ok": True, "has_key": has_api_key()}

    def set_key(self, key: str):
        if not key or not key.strip():
            return {"ok": False, "error": "密钥不能为空"}
        try:
            save_api_key(key.strip())
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 文字冒险
    # ------------------------------------------------------------------
    def adv_new(self):
        self.adv_history = new_history()
        self.adv_story = ""
        self.adv_options = []
        self.adv_game_over = False
        self.adv_turns = 0
        return {"ok": True}

    def adv_start(self):
        """开始新游戏并生成开局剧情。"""
        self.adv_new()
        return self.adv_turn("开始冒险")

    def adv_turn(self, action: str):
        if not action or not action.strip():
            return {"ok": False, "error": "请输入有效行动"}
        if self.adv_history is None:
            self.adv_history = new_history()
        try:
            state, usage = adventure_turn(self.adv_history, action.strip())
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"游戏出错：{exc}"}
        self.adv_story = state["story"]
        self.adv_options = state["options"]
        self.adv_game_over = state["game_over"]
        self.adv_turns += 1
        update_high_score("adventure_max_turns", self.adv_turns)
        return {
            "ok": True,
            "story": self.adv_story,
            "options": self.adv_options,
            "game_over": self.adv_game_over,
            "turns": self.adv_turns,
            "tokens": usage["total_tokens"],
        }

    def adv_state(self):
        return {
            "ok": True,
            "story": self.adv_story,
            "options": self.adv_options,
            "game_over": self.adv_game_over,
            "turns": self.adv_turns,
        }

    def adv_save(self, slot: int):
        if self.adv_history is None:
            return {"ok": False, "error": "尚未开始游戏，无法存档"}
        state = {
            "history": self.adv_history,
            "story": self.adv_story,
            "options": self.adv_options,
            "game_over": self.adv_game_over,
            "turns": self.adv_turns,
        }
        save_game(int(slot), state)
        return {"ok": True}

    def adv_load(self, slot: int):
        state = load_game(int(slot))
        if state is None:
            return {"ok": False, "error": "该存档不存在"}
        self.adv_history = state.get("history") or new_history()
        self.adv_story = state.get("story", "")
        self.adv_options = state.get("options", [])
        self.adv_game_over = state.get("game_over", False)
        self.adv_turns = state.get("turns", 0)
        return {
            "ok": True,
            "story": self.adv_story,
            "options": self.adv_options,
            "game_over": self.adv_game_over,
            "turns": self.adv_turns,
        }

    def adv_list_saves(self):
        return {"ok": True, "saves": list_saves()}

    def adv_max_turns(self):
        return {"ok": True, "max_turns": load_records().get("adventure_max_turns", 0)}

    # ------------------------------------------------------------------
    # 猜谜闯关
    # ------------------------------------------------------------------
    def quiz_new(self, topic: str, difficulty: str):
        try:
            data, usage = ai_quiz(topic, difficulty)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"出题失败：{exc}"}
        self.quiz_question = data["question"]
        self.quiz_answer = data["answer"]
        self.quiz_hint = data["hint"]
        return {
            "ok": True,
            "question": self.quiz_question,
            "hint": self.quiz_hint,
            "tokens": usage["total_tokens"],
        }

    def quiz_hint(self):
        if not self.quiz_hint:
            return {"ok": False, "error": "请先生成题目"}
        return {"ok": True, "hint": self.quiz_hint}

    def quiz_judge(self, reply: str):
        if not self.quiz_answer:
            return {"ok": False, "error": "请先生成题目"}
        if not reply or not reply.strip():
            return {"ok": False, "error": "请输入答案"}
        try:
            result, usage = judge(self.quiz_question, self.quiz_answer, reply.strip())
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"判定失败：{exc}"}
        return {
            "ok": True,
            "correct": result["correct"],
            "comment": result["comment"],
            "answer": self.quiz_answer,
            "tokens": usage["total_tokens"],
        }

    def quiz_high_score(self):
        return {"ok": True, "high_score": load_records().get("quiz_high_score", 0)}

    def quiz_submit_score(self, score: int):
        new = update_high_score("quiz_high_score", int(score))
        return {"ok": True, "high_score": new}


def main():
    api = Api()
    window = webview.create_window(
        "AI 游戏乐园",
        url=resource_path(os.path.join("desktop", "index.html")),
        js_api=api,
        width=940,
        height=720,
        min_size=(720, 560),
        confirm_close=False,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
