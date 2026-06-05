# 微信智能监控面板

一个运行在 macOS 上的微信消息监控工具：自动抓取指定联系人的聊天记录，调用大模型分析语义并更新 Markdown 人物档案，同时支持智能建议回复。

![状态](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![平台](https://img.shields.io/badge/platform-macOS-lightgrey)

## 功能

- 📁 **文件监控 + 兜底轮询** — 通过 `inotify`/FSEvents 监听微信数据库变化，掉链子时自动 fallback
- 🤖 **LLM 智能分析** — 定时分析新消息，自动追加到对应联系人的人物档案
- 💬 **建议回复** — 选中会话后，AI 根据上下文生成回复建议
- 🖥 **Web 控制面板** — 浏览器访问 `http://localhost:8643`，实时查看动态 / 调整设置
- 🔔 **桌面通知** — 新消息来时弹 macOS 系统通知
- 🎨 **暗色模式 / 页面缩放** — 面板自带

## 快速开始

### 1. 安装前置依赖

```bash
# macOS 自带 Python 3，如果没有就装一个
brew install python3

# 安装 wechat-cli（这是从微信客户端读取数据用的 CLI）
npm install -g @canghe_ai/wechat-cli

# 启动 macOS 微信客户端并登录
```

> ⚠️ **注意**：`@canghe_ai/wechat-cli` 已被 npm 官方标记为 **DEPRECATED**（弃用状态）。它目前仍能工作，但作者可能停止维护。如果将来这个包失效了，你可能需要自己 fork 一份或者改用其他方案。

### 2. 克隆并启动

```bash
git clone https://github.com/zhouyi1996413/wechat-monitor.git
cd wechat-monitor
python3 main.py
```

**首次启动会自动**：
- 把 `config.example.yaml` 复制成 `config.yaml`（你不用手动 copy）
- 在终端打印一行警告提醒你编辑 `config.yaml` 填入 LLM API 密钥和人物档案目录

填好之后再次 `python3 main.py` 就能正常工作了。

打开浏览器访问 **http://localhost:8643** 即可。

### 3. macOS 启动器（可选）

想要双击图标启动？打开 macOS 自带的"自动操作"App：

1. 新建 → 类型选**应用程序**
2. 左侧找到"运行 Shell 脚本"，拖到右边
3. 填入：`cd /你的项目路径 && python3 main.py`
4. 存为 `微信监控.app` 即可（放到桌面或"应用程序"文件夹）

停止脚本：`lsof -ti :8643 | xargs kill`

## 配置说明

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

## 进阶

- **面板折叠** — 左右两栏都可以折叠，让中间主区全屏
- **拉取模型列表** — 设置中心点"获取列表"按钮，自动从 API 地址拉所有可用模型
- **桌面通知** — 开关在设置中心底部

## 常见问题

**Q: 启动后报 "获取 wechat-cli 锁超时"？**
A: 多个进程同时调用 wechat-cli 会互斥。等几秒重试，或关掉多余的监控进程。

**Q: LLM 分析一直失败？**
A: 检查 `api_key` / `api_base` / `model` 是否正确；点面板"获取列表"按钮测试连通性。

**Q: 人物档案没生成？**
A: 确认 `profiles_dir` 指向的目录存在且有写权限；检查 `monitor.log` 看 LLM 调用详情。

## 许可

Apache-2.0
