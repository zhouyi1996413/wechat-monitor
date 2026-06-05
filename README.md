# 微信监控面板

自动监控微信联系人消息，追加到人物档案，支持智能分析+建议回复。

## 项目结构

```
wechat-monitor/
├── main.py          # 主程序
├── config.yaml      # 配置文件
├── state.json       # 运行状态（自动生成）
├── monitor.log      # 运行日志（自动生成）
├── start.txt        # 启动时间记录（自动生成）
└── README.md        # 本文件
```

## 使用前准备

1. 安装 [wechat-cli](https://github.com/canghe-ai/wechat-cli)
2. 确保微信 Mac 客户端已登录

## 配置

编辑 `config.yaml`，主要改两项：

```yaml
# 人物档案目录（markdown 文件所在文件夹）
profiles_dir: ~/你的路径/25-人物

# 大模型配置（建议回复功能）
llm:
  mode: openai    # openai 或 anthropic
  api_key: sk-xxx # 你的 API 密钥
  api_base: https://api.deepseek.com/v1
  model: deepseek-chat
```

API 密钥也支持从环境变量读取，设置 `api_key_env` 字段名即可。

## 启动

**方法一：双击桌面「微信监控」App**
（没有终端窗口，自动打开浏览器）

**方法二：命令行**
```bash
cd ~/wechat-monitor && python3 main.py
```

打开浏览器访问 http://localhost:8643

## 停止

```bash
lsof -ti :8643 | xargs kill
```

或双击桌面「停止监控」App。
