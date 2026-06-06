# 微信智能监控面板

一个运行在 macOS 上的微信消息监控工具：自动抓取指定联系人的聊天记录，调用大模型分析语义并更新 Markdown 人物档案，同时支持智能建议回复。

![状态](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![平台](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey) ![许可](https://img.shields.io/badge/license-Apache--2.0-blue)

## ✨ 功能

- 📁 **文件监控 + 兜底轮询** — 通过 `inotify`/FSEvents 监听微信数据库变化，掉链子时自动 fallback
- 🤖 **LLM 智能分析** — 定时分析新消息，自动追加到对应联系人的人物档案
- 💬 **建议回复** — 选中会话后，AI 根据上下文生成回复建议
- 👥 **多账号聚合** — 自动识别一个联系人的多个微信账号（主号 / 小号 / 工作号），可手动补全 / 隐藏
- 🖥 **Web 控制面板** — 浏览器访问 `http://localhost:8643`，实时查看动态 / 调整设置
- 🔔 **桌面通知** — 新消息来时弹 macOS 系统通知
- 🎨 **暗色模式 / 页面缩放** — 面板自带

---

## 🤖 用 AI Agent 一键安装（推荐）

如果你用 Codex、Claude Code、Cursor、Windsurf 这类带终端权限的 AI 编程助手，可以直接把下面这段发给它，它会帮你跑完所有命令：

```
帮我安装并启动 https://github.com/zhouyi1996413/wechat-monitor 这个项目：

1. 克隆仓库并进入目录：
   git clone https://github.com/zhouyi1996413/wechat-monitor.git
   cd wechat-monitor

2. 安装 wechat-cli（自动选平台二进制）：
   npm install -g @canghe_ai/wechat-cli

3. 启动面板：
   python3 main.py

4. 启动后打开浏览器访问 http://localhost:8643

5. 在「设置中心」里：
   - 填 LLM API 密钥（或设环境变量 LLM_API_KEY）
   - 填人物档案目录的绝对路径
   - 点「保存配置」

6. 如果微信客户端没启动，提醒我先启动并登录
```

**Agent 会自动帮你**：克隆、安装、生成 `config.yaml`、启动服务——你只需要在最后提供 API 密钥和档案目录。

---

## 🚀 快速开始

### 1. 安装前置依赖

| 平台 | 步骤 |
|---|---|
| **macOS** | `brew install python3`（macOS 自带 Python 3 可跳过）→ 启动 macOS 微信客户端并登录 |
| **Windows** | 装 [Python 3.10+](https://www.python.org/downloads/windows/) → 启动 Windows 微信客户端并登录 |

然后安装 wechat-cli（自动选择你平台的二进制）：

```bash
npm install -g @canghe_ai/wechat-cli
```

> ⚠️ **平台支持**：理论上 macOS / Windows 都能跑（wechat-cli 提供了 darwin-arm64、darwin-x64、win32-x64 三种二进制）。作者主要在 macOS 上开发，Windows 用户可能需要自行测试。Linux 没有官方微信客户端，不在支持范围。
> 
> ⚠️ **依赖包状态**：`@canghe_ai/wechat-cli` 已被 npm 官方标记为 DEPRECATED（弃用）。它目前仍能工作，但作者可能停止维护。如果将来这个包失效了，你可能需要自己 fork 或者改用其他方案。

### 2. 克隆并启动

```bash
git clone https://github.com/zhouyi1996413/wechat-monitor.git
cd wechat-monitor
python3 main.py
```

**首次启动会自动**：
- 把 `config.example.yaml` 复制成 `config.yaml`（你不用手动 copy）
- 在终端打印一行提示，让你打开 `http://localhost:8643` 的「设置中心」填写 LLM API 密钥和人物档案目录

填好后下次启动就是正常工作了。

打开浏览器访问 **http://localhost:8643** 即可。

### 3. macOS 启动器（可选，macOS 专属）

想要双击图标启动？打开 macOS 自带的"自动操作"App：

1. 新建 → 类型选**应用程序**
2. 左侧找到"运行 Shell 脚本"，拖到右边
3. 填入：`cd /你的项目路径 && python3 main.py`
4. 存为 `微信监控.app` 即可（放到桌面或"应用程序"文件夹）

停止脚本：`lsof -ti :8643 | xargs kill`

---

## ⚙️ 配置说明

`config.yaml` 主要字段：

| 字段 | 说明 | 默认值 |
|---|---|---|
| `port` | Web 面板端口 | `8643` |
| `poll_interval` | 监控轮询间隔（秒，最小 15） | `30` |
| `profiles_dir` | 人物档案目录（绝对路径） | `""`（必填） |
| `wechat_cli_path` | wechat-cli 路径（留空自动检测） | `""` |
| `exclude_chats` | 不监控的会话名 | `[]` |
| `llm.api_key` | LLM API 密钥 | `""` |
| `llm.api_key_env` | 从环境变量读密钥时的变量名 | `LLM_API_KEY` |
| `llm.api_base` | API 地址 | `https://api.openai.com/v1` |
| `llm.model` | 模型名 | `gpt-4o-mini` |
| `llm.mode` | 接口格式（`openai` 或 `anthropic`） | `openai` |

API 密钥也支持用环境变量注入：设 `LLM_API_KEY=sk-xxx` 后 `config.yaml` 里 `api_key` 留空即可。

---

## 👥 多账号管理

很多人有"大号 / 小号"或"个人 / 工作号"等多个微信账号。本项目会自动识别同一个联系人在 wechat-cli 里出现的所有账号，并在面板里聚合显示。

### 自动识别规则
- **前缀匹配**：监控"张三"会自动包含"张三(小号)"等（chat 名以监控名为前缀）
- **档案 alias 兜底**：如果档案 `.md` 里写了某个 wxid（即使 wechat-cli 缓存里没拉到），也会显示

### 手动管理
- 点头像或名字 → 弹窗顶部"多账号"区
- **+ 添加**：手动加一个未识别的微信账号（填 username、显示名、备注）
- **重命名（铅笔）**：给 wxid_xxx 这种"机器名"起个"人话名"（比如 `wxid_abcd1234efgh5678` → `zhangsan_2025`），列表里会优先显示人话名
- **⭐ 设为主账号**：标哪个是主联系对象
- **隐藏 / 删除**：auto/alias 账号是"隐藏"（可恢复），manual 账号是"删除"

数据存到 `state.json` 的 `manual_accounts` 和 `account_labels` 字段。

---

## 🖥 面板使用

### 主界面三栏
- **左：监控联系人** — 搜索 / 折叠 / 展开多账号 / 点名字看档案
- **中：动态 + 统计** — 今日更新、运行时长、最近日志、轮询间隔
- **右：设置中心** — 折叠到右侧，留给中间更多空间

### 设置中心
- **页面缩放**：拉条调整 80%-150%，实时预览百分比，松手才生效
- **人物档案目录** + **LLM 配置**（接口模式、API 密钥、地址、模型名）
- **拉取模型列表**：自动从 API 地址拉所有可用模型，下拉选择
- **桌面通知开关** + **排除关键词**

### 暗色模式
- 右上角 🌙 / ☀️ 切换，自动记忆选择

---

## 🛠 进阶

- **多账号聚合** — 见上文，自动 + 手动结合
- **页面缩放** — 设置中心拉条，百分比实时显示
- **拉取模型列表** — 设置中心点"获取列表"按钮
- **桌面通知** — 开关在设置中心底部

---

## ❓ 常见问题

**Q: 启动后报 "获取 wechat-cli 锁超时"？**
A: 多个进程同时调用 wechat-cli 会互斥。等几秒重试，或关掉多余的监控进程。

**Q: LLM 分析一直失败？**
A: 检查 `api_key` / `api_base` / `model` 是否正确；点面板"获取列表"按钮测试连通性。

**Q: 人物档案没生成？**
A: 确认 `profiles_dir` 指向的目录存在且有写权限；检查 `monitor.log` 看 LLM 调用详情。

**Q: 同一个联系人在面板里只显示一个账号，怎么看到全部？**
A: 点头像/名字 → 弹窗顶部"多账号"区会列出全部；或者点右侧"展开"按钮展开子列表。自动没识别到的可以手动"+"添加。

**Q: 微信里看到的微信号是 `zhangsan_2025`，但面板里显示 `wxid_abcd1234efgh5678`？**
A: `wxid_` 是微信系统永久 ID，wechat-cli 只能读到系统 ID。点弹窗里的"重命名"按钮把 wxid 改成人话名即可，列表里会优先显示人话名。

---

## 📂 项目结构

```
wechat-monitor/
├── main.py                # 单文件应用：HTTP server + 监控 + LLM 客户端（约 2100 行）
├── config.example.yaml    # 配置模板（首次启动自动复制成 config.yaml）
├── ui/                    # 前端拆分（源码分层，部署仍是单文件）
│   ├── __init__.py        # 拼装 HEAD + STYLES + BODY + APP_JS 成 HTML_PAGE
│   ├── _head.py           # <!DOCTYPE> + <head> 标签
│   ├── _styles.py         # <style>...</style> CSS
│   ├── _body.py           # <body> 内 HTML
│   └── _app.py            # 主 <script>...</script> JS
├── .gitignore             # 排除 config.yaml / state.json / .auth_token 等隐私文件
├── state.json             # 运行时状态（消息缓存、轮询间隔、手动联系人、手动账号、label）
└── monitor.log            # 运行日志
```

UI 拆到 `ui/` 目录是为了源码清晰（HTML/CSS/JS 分别看），运行时 main.py 通过 `from ui import HTML_PAGE` 拼装，部署仍是单文件。

---

## 🔐 安全 / 隐私

以下文件包含运行时数据或敏感信息，已全部加入 `.gitignore`，不会随代码提交：

- `config.yaml` — LLM API 密钥和档案目录路径
- `state.json` — 手动联系人 / 账号 / 排序等运行状态
- `.auth_token` — 面板 API 鉴权 token（每次启动随机生成）
- `monitor.log` — 消息摘要和 LLM 调用记录
- `start.txt` / `stop.txt` — 监控时间戳
- `*.app/` — macOS 启动器

---

## 🤝 贡献

欢迎 PR！主要的可改进方向：
- 适配其他 LLM 接口（目前支持 OpenAI 兼容 + Anthropic 格式）
- 多语言界面
- 移动端响应式
- 替换 wechat-cli（如果未来这个包失效）

---

## 📜 许可

Apache-2.0
