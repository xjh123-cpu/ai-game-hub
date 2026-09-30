# AI 游戏乐园（AI Game Hub）

> 🌐 **在线体验：** https://ai-game-app-guafojyerp2zxvntcep732.streamlit.app/
> （免费版需先登录 Google / GitHub 账号）

《大模型应用实训》实验五 —— 综合项目实战：端到端大模型应用开发。

基于**智谱 GLM（OpenAI 兼容接口）** 打造的大模型游戏应用，包含两个 AI 互动小游戏。
同一套 `games/` 业务逻辑提供**两种形态**：云端 **Streamlit 网页版**（`app.py`，已公开部署，供同学直接访问试用）与 **Windows 桌面版**（`main.py` + pywebview，可打包 exe 离线运行）。

| 游戏 | 核心能力 | 温度策略 | 升级亮点 |
|------|---------|---------|---------|
| 🏰 AI 文字冒险 | 实时生成剧情、分支选项、结束判定、多轮上下文 | 剧情 0.9（高温） | 存档/读档、回合统计、注入攻击三层防护 |
| 🧩 AI 猜谜闯关 | AI 出题（含事实核查）、AI 裁判、积分、提示 | 出题 1.0 / 判定与核查 0.0 | 谜底防重复防泄露、答对自动连题、初始 3 积分 |

## 项目结构

```
ai-game-hub/
├── app.py                  # 【云端主入口】Streamlit 网页版（公开部署用的就是本文件）
├── main.py                 # 【桌面入口】pywebview 窗口 + js_api 后端
├── desktop/                # 前端（HTML/CSS/JS，现代深色风格）
│   ├── index.html          # 单页应用：大厅 + 冒险 + 猜谜
│   ├── style.css
│   └── app.js
├── llm.py                  # 大模型 API 封装（指数退避重试 + 异常 + 密钥管理）
├── prompts.py              # 提示词模板库
├── storage.py              # 本地持久化（配置/最高分/存档）
├── games/
│   ├── __init__.py         # 输入防护（clamp_text 长度约束）
│   ├── adventure.py        # 文字冒险逻辑（含自我纠错重试）
│   └── quiz.py             # 猜谜逻辑（出题/事实核查/泄露检测/裁判）
├── tests/                  # 14 条测试用例 + LLM-as-Judge 评估（支持多次采样）
├── docs/                   # PRD + 项目报告 + 演示脚本 + 试用反馈记录
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

# 2. 运行网页版（与云端同一份代码，推荐用作开发调试）
streamlit run app.py

# 或运行桌面版（Windows，首次启动会弹出 API Key 设置窗口）
python main.py
```

> API Key 可在应用内「⚙️ API Key 设置」中填写，仅保存在本机 `~/.ai_game_hub/config.json`；
> 也可设置环境变量 `GLM_API_KEY`。

## 公开部署（步骤 2~4：Streamlit Community Cloud，免费）

云端部署使用**网页版** `app.py`（桌面版 `main.py` 依赖本地窗口，无法部署）。

1. **推送代码到 GitHub**：`.env`、`.streamlit/secrets.toml` 均已被 `.gitignore` 排除，不会泄露密钥
2. **创建应用**：打开 [share.streamlit.io](https://share.streamlit.io) → GitHub 登录 → **Create app** → 选择仓库与分支，主文件路径填 `app.py`
3. **配置 Secrets**（步骤 3：密钥走平台管理，不写入代码）：应用页 **Settings → Secrets**，填入：
   ```toml
   GLM_API_KEY = "你的智谱API密钥"
   ```
   保存后应用自动重启生效（`llm.py` 会自动从 `st.secrets` 读取）
4. **公开链接与反馈**（步骤 4）：部署完成后获得 `https://<应用名>.streamlit.app`，发给同学试用收集反馈；录制 3 分钟演示视频（建议结构：30s 介绍 → 60s 文字冒险 → 60s 猜谜 → 30s 亮点与评估迭代）

> 备选平台：Hugging Face Spaces（新建 Space 选 Streamlit 模板，在 Settings → Variables and secrets 里配置 `GLM_API_KEY`）。

### 防刷量限流（注意事项）

公开链接任何人可访问，`app.py` 内置**会话级限流**：相邻调用 ≥2 秒、每分钟 ≤10 次、单会话累计 ≤200 次，超限自动拦截并提示。如需调整，修改 `app.py` 顶部 `RATE_MIN_INTERVAL` / `RATE_MAX_PER_MIN` / `RATE_SESSION_CAP` 三个常量。

## 打包为 Windows 可执行文件（双击即用）

### 方式一：GitHub Actions 自动打包（推荐）

1. 把代码推送到 GitHub 仓库（`.env` 已被 `.gitignore` 排除）
2. 打开仓库 **Actions** 页 → 运行 `Build Windows EXE` 工作流
3. 下载 artifact，解压得到 `AI游戏乐园.exe`，双击运行

### 方式二：本地打包

Windows 电脑安装 Python 3.10+ 后，双击 `build_windows.bat`，自动安装依赖并产出 `dist\AI游戏乐园.exe`。

## 运行测试与评估

```bash
# 默认：每条用例重复采样 3 次，取均值并计算标准差（跑得久但结论更稳）
python tests/evaluate.py

# 快速冒烟：单次采样
python tests/evaluate.py --repeat 1

# 按轮次打标签，便于「基线 vs 改进后」对比
python tests/evaluate.py --tag baseline   # → tests/evaluation_result_baseline.csv
```

其中 **T11 / T13 / T14 为程序级用例**，直接断言代码防护逻辑（空输入拦截、谜面泄露检测、输入截断），不调用大模型、不消耗 token，可离线复现。

## 实验要求对照

| 实验 5.5 任务 | 完成情况 |
|--------------|---------|
| PRD 需求分析（≥1页） | `docs/PRD.md` |
| 核心功能开发（异常处理/API重试/密钥管理） | `llm.py` 指数退避重试 3 次、统一异常处理、密钥双通道读取 |
| ≥10 条测试用例 + 评估迭代 | `tests/`（14 条用例 + LLM-as-Judge，平均分 3.76 → 4.06，全部跑通） |
| 部署与展示（公开链接） | Streamlit Community Cloud 公开部署：<https://ai-game-app-guafojyerp2zxvntcep732.streamlit.app/>（密钥走平台 Secrets + 会话级限流） |
| 部署与展示（桌面形态） | Windows 桌面版，PyInstaller 打包 `AI游戏乐园.exe`（GitHub Actions 自动构建） |
| 演示视频（≤3 分钟） | 脚本见 `docs/演示视频脚本.md` |
| 项目报告 | `docs/项目报告.md` |
