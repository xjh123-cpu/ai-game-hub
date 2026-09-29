# AI 游戏乐园（AI Game Hub）

《大模型应用实训》实验五 —— 综合项目实战：端到端大模型应用开发。

基于**智谱 GLM（OpenAI 兼容接口）** 打造的 **Windows 桌面应用**，包含两个 AI 互动小游戏：

| 游戏 | 核心能力 | 温度策略 | 升级亮点 |
|------|---------|---------|---------|
| 🏰 AI 文字冒险 | 实时生成剧情、分支选项、结束判定、多轮上下文 | 剧情 0.9（高温） | 存档/读档、回合统计、丰富世界观 |
| 🧩 AI 猜谜闯关 | AI 出题、AI 裁判、积分、提示 | 出题 1.0 / 判定 0.0 | 连击加分、本地最高分 |

## 项目结构

```
ai-game-hub/
├── main.py                 # 桌面入口（pywebview 窗口 + js_api 后端）
├── desktop/                # 前端（HTML/CSS/JS，现代深色风格）
│   ├── index.html          # 单页应用：大厅 + 冒险 + 猜谜
│   ├── style.css
│   └── app.js
├── llm.py                  # 大模型 API 封装（指数退避重试 + 异常 + 密钥管理）
├── prompts.py              # 提示词模板库
├── storage.py              # 本地持久化（配置/最高分/存档）
├── games/
│   ├── adventure.py        # 文字冒险逻辑（含自我纠错重试）
│   └── quiz.py             # 猜谜逻辑（出题/裁判）
├── tests/                  # 12 条测试用例 + LLM-as-Judge 评估
├── docs/                   # PRD + 项目报告
├── app.py                  # （备用）Streamlit 网页版
├── build.spec              # PyInstaller 打包配置
├── .github/workflows/build-windows.yml  # GitHub Actions 自动打包 exe
├── build_windows.bat       # Windows 本地打包脚本（备选）
├── requirements.txt
└── .gitignore
```

## 快速开始（开发模式）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行桌面应用（首次启动会弹出 API Key 设置窗口）
python main.py
```

> API Key 可在应用内「⚙️ API Key 设置」中填写，仅保存在本机 `~/.ai_game_hub/config.json`；
> 也可设置环境变量 `GLM_API_KEY`。

## 打包为 Windows 可执行文件（双击即用）

### 方式一：GitHub Actions 自动打包（推荐）

1. 把代码推送到 GitHub 仓库（`.env` 已被 `.gitignore` 排除）
2. 打开仓库 **Actions** 页 → 运行 `Build Windows EXE` 工作流
3. 下载 artifact，解压得到 `AI游戏乐园.exe`，双击运行

### 方式二：本地打包

Windows 电脑安装 Python 3.10+ 后，双击 `build_windows.bat`，自动安装依赖并产出 `dist\AI游戏乐园.exe`。

## 运行测试与评估

```bash
python tests/evaluate.py   # 12 条用例 + LLM-as-Judge 三维度评分
```

## 实验要求对照

| 实验 5.5 任务 | 完成情况 |
|--------------|---------|
| PRD 需求分析（≥1页） | `docs/PRD.md` |
| 核心功能开发（异常处理/API重试/密钥管理） | `llm.py` 指数退避重试 3 次、统一异常处理、密钥双通道读取 |
| ≥10 条测试用例 + 评估迭代 | `tests/`（12 条用例，平均分 4.0，全部跑通） |
| 部署与展示 | Windows 桌面应用（PyInstaller 打包 exe）+ 演示视频 |
| 项目报告 | `docs/项目报告.md` |
