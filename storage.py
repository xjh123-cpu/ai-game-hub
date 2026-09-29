"""本地持久化模块。

统一管理应用数据的读写：API 配置、游戏记录（最高分）、文字冒险存档。
数据存储于用户主目录下的 `.ai_game_hub/` 目录，开发环境与打包后的 exe 行为一致。
"""
import os
import json
import time

# 数据目录：用户主目录下（打包后仍可写，避免写入 PyInstaller 临时目录）
DATA_DIR = os.path.join(os.path.expanduser("~"), ".ai_game_hub")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(name, default):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _write_json(name, data):
    _ensure_dir()
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# API 配置（密钥等）
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """读取应用配置，如 {"api_key": "...", "model": "glm-4-flash"}。"""
    return _read_json("config.json", {})


def save_config(cfg: dict):
    """保存应用配置（密钥仅存本机，已由 .gitignore 排除）。"""
    _write_json("config.json", cfg)


# ---------------------------------------------------------------------------
# 游戏记录（最高分）
# ---------------------------------------------------------------------------
def load_records() -> dict:
    """读取游戏记录，如 {"quiz_high_score": 25, "adventure_max_turns": 12}。"""
    return _read_json("records.json", {})


def save_records(rec: dict):
    """保存游戏记录。"""
    _write_json("records.json", rec)


def update_high_score(key: str, value: int) -> int:
    """更新某项最高分，返回更新后的值（只升不降）。"""
    rec = load_records()
    old = int(rec.get(key, 0))
    new = max(old, int(value))
    rec[key] = new
    save_records(rec)
    return new


# ---------------------------------------------------------------------------
# 文字冒险存档
# ---------------------------------------------------------------------------
def save_game(slot: int, state: dict):
    """保存文字冒险存档。state 应包含 history/story/options/game_over/turns。"""
    saves = _read_json("saves.json", {})
    saves[str(slot)] = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "state": state,
    }
    _write_json("saves.json", saves)


def load_game(slot: int) -> dict:
    """读取指定槽位的存档，不存在时返回 None。"""
    saves = _read_json("saves.json", {})
    entry = saves.get(str(slot))
    return entry["state"] if entry else None


def list_saves() -> list:
    """返回所有存档槽位及其保存时间。"""
    saves = _read_json("saves.json", {})
    return [
        {"slot": int(k), "saved_at": v["saved_at"]}
        for k, v in sorted(saves.items(), key=lambda x: int(x[0]))
    ]
