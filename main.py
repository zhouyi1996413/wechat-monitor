#!/usr/bin/env python3
"""
微信全面监听监控面板
- HTTP 控制面板 (localhost:8643)
- 文件监控 + 兜底轮询 wechat-cli new-messages
- LLM 分析对话内容，更新/创建人物档案
- 建议回复 + 对话分析
"""

# ===== 1. Imports =====
import http.server
import json
import os
import random
import re
import secrets
import subprocess
import threading
import time
import urllib.parse
import signal
import traceback
from logging.handlers import RotatingFileHandler
import logging
import requests
import yaml
from datetime import datetime
from pathlib import Path
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    WATCHDOG_AVAILABLE = False

# ===== 2. Constants =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.yaml")
STATE_FILE = os.path.join(SCRIPT_DIR, "state.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "monitor.log")

POLL_INTERVAL_MIN = 15
POLL_INTERVAL_DEFAULT = 30
POLL_INTERVAL_IDLE = 60
FALLBACK_POLL_INTERVAL = 60       # 兜底轮询间隔（秒）
CALIBRATION_INTERVAL = 60         # 校准线程间隔（秒）
CACHE_REFRESH_INTERVAL = 180      # 缓存主动刷新间隔（秒），保证 suggest-reply 即时可用
CONSECUTIVE_FAILURE_BACKOFF = 600 # 连续失败后暂停轮询的时长（秒）
WEBCOMMAND_TIMEOUT = 15           # 单次 wechat-cli 子进程超时（秒）
WEBCOMMAND_LOCK_TIMEOUT = 10      # 单次 wechat-cli 锁超时（秒），耐心等主轮询/缓存刷新
STATE_SAVE_INTERVAL = 300          # 状态持久化间隔（秒）
SSE_HEARTBEAT_INTERVAL = 10        # SSE 心跳间隔（秒）
DB_DEBOUNCE_SECONDS = 1.0          # DB 文件变化防抖（秒）
WARMUP_CONTACTS_LIMIT = 10         # 预热缓存联系人上限
MAX_MESSAGE_CACHE_ENTRIES = 200    # message_cache 最多保留的联系人数
MAX_RECENT_LOGS = 100              # recent_logs 保留条数
MAX_HISTORY_LIMIT = 9999           # history 拉取上限
PROCESS_TIMEOUT = 30               # 子进程超时
LLM_TIMEOUT = 120                  # LLM 调用超时
NEW_MESSAGES_TIMEOUT = 30          # new-messages 超时
HISTORY_TIMEOUT = 30               # history 命令超时
WECHAT_LOCK_TIMEOUT = 60           # wechat-cli 锁超时
IDLE_POLL_THRESHOLD = 5            # 连续空轮询次数阈值，之后退避
LAST_SEEN_DEDUP_WINDOW = 30        # 同联系人去重时间窗口（秒）
AUTH_TOKEN_FILE = ".auth_token"

# ===== 3. Logging (before config loading) =====
_file_logger = logging.getLogger("wechat-monitor")
_file_logger.setLevel(logging.DEBUG)
_file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
_file_logger.addHandler(_file_handler)

recent_logs = []


def log(msg, level="info"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level.upper()}] {msg}"
    print(line)
    try:
        _level_map = {
            "info": logging.INFO,
            "warn": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        _file_logger.log(_level_map.get(level, logging.INFO), msg)
    except Exception:
        pass
    recent_logs.append({"time": ts, "level": level, "msg": msg})
    if len(recent_logs) > MAX_RECENT_LOGS:

        recent_logs[:] = recent_logs[-MAX_RECENT_LOGS:]
    # 推送日志到前端（SSE）
    try:
        _sse_broadcast("log_update", {})
    except Exception:
        pass

if not WATCHDOG_AVAILABLE:
    log("watchdog 未安装，文件监控已禁用（不影响主功能）", "warn")


# ===== 4. Config Loading =====
def load_config():
    """读取 config.yaml，没有则从 config.example.yaml 复制一份"""
    if not os.path.exists(CONFIG_FILE):
        example = os.path.join(SCRIPT_DIR, "config.example.yaml")
        if os.path.exists(example):
            import shutil
            shutil.copy(example, CONFIG_FILE)
            print(f"[INFO] 📋 已从 config.example.yaml 复制默认配置到 {CONFIG_FILE}")
            print(f"[WARN] ⚠️  请打开 config.yaml 填入你的 LLM API 密钥和人物档案目录路径")
        else:
            print(f"[ERROR] ❌ 找不到配置文件: {CONFIG_FILE}")
            print(f"[ERROR] 也找不到 config.example.yaml，请重新 clone 项目")
            raise SystemExit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    llm = cfg.get("llm", {})
    api_key = llm.get("api_key", "") or os.environ.get(
        llm.get("api_key_env", "LLM_API_KEY"), ""
    )

    return {
        "port": int(cfg.get("port", 8643)),
        "poll_interval": int(cfg.get("poll_interval", POLL_INTERVAL_DEFAULT)),
        "profiles_dir": os.path.expanduser(cfg.get("profiles_dir", "")),
        "wechat_cli_path": cfg.get("wechat_cli_path", "").strip(),
        "exclude_chats": cfg.get("exclude_chats", []),
        "llm": {
            "mode": llm.get("mode", "openai"),
            "api_key": api_key,
            "api_key_env": llm.get("api_key_env", "LLM_API_KEY"),
            "api_base": llm.get(
                "api_base", "https://api.openai.com/v1"
            ).rstrip("/"),
            "model": llm.get("model", "gpt-4o-mini"),
        },
    }


CONFIG = load_config()

PORT = CONFIG["port"]
PROFILE_DIR = Path(CONFIG["profiles_dir"])
EXCLUDE_CHATS = CONFIG["exclude_chats"]
LLM_CONFIG = CONFIG["llm"]
poll_interval = CONFIG["poll_interval"]


def save_config():
    """将当前 CONFIG 写回 config.yaml"""
    data = {
        "port": CONFIG["port"],
        "poll_interval": CONFIG["poll_interval"],
        "profiles_dir": CONFIG["profiles_dir"],
        "llm": {
            "mode": CONFIG["llm"]["mode"],
            "api_key": CONFIG["llm"]["api_key"],
            "api_key_env": CONFIG["llm"]["api_key_env"],
            "api_base": CONFIG["llm"]["api_base"],
            "model": CONFIG["llm"]["model"],
        },
        "exclude_chats": CONFIG["exclude_chats"],
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ===== 5. Auth =====
def _load_or_create_token():
    """加载或创建 API Token（启动阶段用 print 而非 log）"""
    state_path = os.path.join(SCRIPT_DIR, AUTH_TOKEN_FILE)
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                token = f.read().strip()
            if token:
                return token
        except Exception:
            pass
    token = secrets.token_urlsafe(32)
    with open(state_path, "w") as f:
        f.write(token)
    os.chmod(state_path, 0o600)
    print(f"[INFO] 🔑 首次启动，API Token 已生成: {token}")
    print("[INFO] 🔑 请在浏览器 Authorization Header 中携带此 Token，或在 URL 中加 ?token=xxx")
    return token


API_TOKEN = _load_or_create_token()


def _check_auth(handler):
    """校验请求鉴权，返回 True 表示通过"""
    auth_header = handler.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == API_TOKEN:
        return True
    parsed = urllib.parse.urlparse(handler.path)
    qs = urllib.parse.parse_qs(parsed.query)
    if qs.get("token", [""])[0] == API_TOKEN:
        return True
    path = urllib.parse.urlparse(handler.path).path
    if path in ("/", "/index.html", "/favicon.ico", "/api/public-token"):
        return True
    return False


# ===== 6. Global State and Locks =====
monitor_running = False
monitor_thread = None
profile_contacts = {}          # {identifier: profile_path}
profile_identifiers = {}       # {profile_path: set_of_identifiers}
identifier_to_profile = {}     # {identifier: profile_path}
profile_names = []             # 仅人名列表（前端显示）
profile_name_to_chat_names = {}  # {profile_name: {chat_name1, ...}} 多账号别名映射
monitored_contacts = set()     # 所有监控中的联系人
all_contacts_cache = []        # 所有微信联系人缓存
message_cache = {}             # 最近消息缓存 {chat_name: [messages]}
message_counts = {}            # 消息计数 {chat_name: count}
last_seen = {}                 # 去重时间戳 {username_chat: timestamp}
today_updates = 0              # 今日更新计数
today_updates_date = ""        # 记录计数对应的日期

_state_lock = threading.Lock()      # 共享状态读写锁
_wechat_lock = threading.Lock()     # wechat-cli 互斥锁
_file_lock = threading.Lock()       # 档案文件写锁
_sse_clients = []                   # SSE 连接列表
_sse_lock = threading.Lock()
_contacts_lock = threading.Lock()   # 联系人缓存刷新锁
_contacts_last_refresh = 0.0        # 上次联系人刷新时间

# 监控内部状态
_fallback_poll_ts = 0.0              # 上次兜底轮询时间
_calibration_pending = set()        # 待校准联系人
_calibration_ts = 0.0               # 上次校准时间
_consecutive_empty = 0              # 连续空轮询次数
_file_changed_flag = threading.Event()  # watchdog -> 主循环信号：有 db 文件变化


def _trim_message_cache():
    """清理 message_cache，只保留最近活跃的联系人"""
    if len(message_cache) > MAX_MESSAGE_CACHE_ENTRIES:
        keys = sorted(message_cache.keys(), key=lambda k: len(message_cache[k]))
        to_remove = keys[: len(keys) - MAX_MESSAGE_CACHE_ENTRIES]
        for k in to_remove:
            del message_cache[k]


# ===== 7. wechat-cli Tool =====
# 优先级: 环境变量 > 原生二进制(绕过node wrapper) > node wrapper > PATH
WECHAT_CLI = (CONFIG.get("wechat_cli_path") or os.environ.get("WECHAT_CLI_PATH") or "").strip()
if not WECHAT_CLI:
    _native = os.path.expanduser(
        "~/.npm-global/lib/node_modules/@canghe_ai/wechat-cli/"
        "node_modules/@canghe_ai/wechat-cli-darwin-arm64/bin/wechat-cli"
    )
    if os.path.isfile(_native):
        WECHAT_CLI = _native
    else:
        WECHAT_CLI = os.path.expanduser("~/.npm-global/bin/wechat-cli")
if not os.path.isfile(WECHAT_CLI):
    WECHAT_CLI = "wechat-cli"  # fallback 到 PATH 查找


def run_cmd(cmd_list, timeout=PROCESS_TIMEOUT, lock_timeout=WECHAT_LOCK_TIMEOUT):
    """运行 shell 命令，带 wechat-cli 互斥锁"""
    if isinstance(cmd_list, list) and len(cmd_list) > 0 and cmd_list[0] == "wechat-cli":
        cmd_list = [WECHAT_CLI] + cmd_list[1:]
    cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else str(cmd_list)
    lock_needed = "wechat-cli" in cmd_str or WECHAT_CLI in cmd_str
    acquired = False
    try:
        if lock_needed:
            if not _wechat_lock.acquire(timeout=lock_timeout):
                log(f"获取 wechat-cli 锁超时: {' '.join(cmd_list)}", "error")
                return ""
            acquired = True
        proc = subprocess.Popen(
            cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return stdout + stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log(f"命令超时已杀掉: {' '.join(cmd_list)}", "warn")
            return ""
    except Exception as e:
        log(f"命令异常: {' '.join(cmd_list)}: {e}", "error")
        return ""
    finally:
        if lock_needed and acquired:
            try:
                _wechat_lock.release()
            except RuntimeError:
                pass


# ===== 8. State Persistence =====
def load_state():
    """从 state.json 加载持久化状态"""
    global poll_interval, last_seen
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            poll_interval = data.get("poll_interval", POLL_INTERVAL_DEFAULT)
            if poll_interval < POLL_INTERVAL_MIN:
                poll_interval = POLL_INTERVAL_MIN
            last_seen = data.get("last_seen", {})
            message_counts.update(data.get("message_counts", {}))
            return data
        except Exception:
            pass
    return {
        "running": False,
        "last_seen": {},
        "manual_contacts": [],
        "poll_interval": POLL_INTERVAL_DEFAULT,
    }


def save_state(state=None):
    """持久化 state.json"""
    with _state_lock:
        data = state or {}
        data.setdefault("running", monitor_running)
        data["last_seen"] = last_seen
        data["poll_interval"] = poll_interval
        data["manual_contacts"] = list(
            monitored_contacts - set(profile_names)
        )
        data["last_poll_time"] = time.time()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _persist_state_loop():
    """后台线程：定期持久化状态"""
    while monitor_running:
        time.sleep(STATE_SAVE_INTERVAL)
        if not monitor_running:
            break
        try:
            save_state()
        except Exception as e:
            log(f"状态持久化异常: {e}", "error")


# ===== 9. Profile / Contact Management =====
def init_profiles():
    """扫描 profiles_dir 初始化档案映射"""
    global profile_contacts, profile_identifiers, identifier_to_profile
    global profile_names, monitored_contacts, profile_name_to_chat_names

    with _state_lock:
        profile_contacts = {}
        profile_identifiers = {}
        identifier_to_profile = {}
        profile_names = []
        profile_name_to_chat_names = {}
        monitored_contacts = set()

    if not PROFILE_DIR.exists():
        return

    for md_file in sorted(PROFILE_DIR.glob("*.md"), key=lambda f: f.stem):
        name = md_file.stem
        if name == "Self-Profile":
            continue

        with _state_lock:
            profile_names.append(name)
            monitored_contacts.add(name)

        try:
            content = md_file.read_text()
        except (OSError, IOError) as e:
            log(f"无法读取档案 {name}: {e}", "warn")
            continue

        identifiers = set()
        alias_chat_names = set()

        # 匹配 wxid_xxx 格式
        for wxid_match in re.finditer(r"wxid_[a-zA-Z0-9]{8,}", content):
            identifiers.add(wxid_match.group(0))

        # 从"微信号"字段解析所有账号标识符
        wxid_pattern = re.compile(
            r'微信号\s*[|:]?\s*(.+?)(?=\n\|[^微信号]|$)',
            re.IGNORECASE | re.DOTALL,
        )
        for match in wxid_pattern.finditer(content):
            field_content = match.group(1).strip()
            # 提取括号内的别名
            for alias_match in re.finditer(
                r'[（(][^）)]*?["\u201c](.+?)["\u201d][）)]',
                field_content,
            ):
                alias_name = alias_match.group(1).strip()
                if alias_name and alias_name != name and len(alias_name) <= 20:
                    alias_chat_names.add(alias_name)
            for alias_match in re.finditer(
                r'[（(][^）)]*?[\u201c]?(.+?)[\u201d]?[）)]',
                field_content,
            ):
                alias_name = alias_match.group(1).strip()
                skip_words = {
                    "大号",
                    "小号",
                    "微信号",
                    "微信",
                    "账号",
                    "account",
                }
                if (
                    alias_name
                    and alias_name != name
                    and len(alias_name) <= 20
                    and alias_name not in skip_words
                ):
                    alias_chat_names.add(alias_name)
            # 移除括号内的备注
            field_content = re.sub(r'[（(][^）)]*?[）)]', "", field_content)
            for sub_match in re.finditer(r"wxid_[a-zA-Z0-9]{8,}", field_content):
                identifiers.add(sub_match.group(0))
            for sub_match in re.finditer(r"\b([a-zA-Z0-9_]{6,})\b", field_content):
                val = sub_match.group(1)
                if not val.startswith("wxid") and val not in identifiers:
                    identifiers.add(val)

        identifiers.add(name)

        with _state_lock:
            profile_identifiers[md_file] = identifiers
            for ident in identifiers:
                profile_contacts[ident] = md_file
                identifier_to_profile[ident] = md_file
            profile_name_to_chat_names[name] = alias_chat_names

    # 恢复手动添加的联系人
    state = load_state()
    for c in state.get("manual_contacts", []):
        with _state_lock:
            monitored_contacts.add(c)


def refresh_all_contacts():
    """刷新微信联系人缓存（带 60s 缓存 + 全局锁防并发）"""
    global all_contacts_cache, _contacts_last_refresh
    now = time.time()
    if not _contacts_lock.acquire(blocking=False):
        return
    try:
        if now - _contacts_last_refresh < 60 and all_contacts_cache:
            return
        old_cache = list(all_contacts_cache)
        output = run_cmd(
            ["wechat-cli", "sessions", "--limit", "30"], timeout=15, lock_timeout=5
        )
        new_cache = []
        if output:
            try:
                data = json.loads(output)
                for s in data:
                    chat = s.get("chat", "")
                    username = s.get("username", "")
                    is_group = s.get("is_group", False)
                    if is_group:
                        continue
                    if chat in EXCLUDE_CHATS:
                        continue
                    if str(username).startswith("gh_") or username in [
                        "qqmail",
                        "brandservicesessionholder",
                        "brandsessionholder",
                    ]:
                        continue
                    new_cache.append({"chat": chat, "username": username})
            except Exception:
                pass
        if new_cache:
            all_contacts_cache = new_cache
        elif old_cache:
            all_contacts_cache = old_cache
        _contacts_last_refresh = time.time()
    finally:
        _contacts_lock.release()


def auto_create_profile(chat_name, username):
    """为没有档案的联系人自动创建简易档案"""
    filepath = PROFILE_DIR / f"{chat_name}.md"
    if filepath.exists():
        return filepath

    content = (
        f"# {chat_name}\n\n"
        f"## 基本信息\n\n| 项目 | 内容 |\n|------|------|\n"
        f"| 微信号 | {username} |\n| 关系 | 待补充 |\n\n## 关键事件\n\n"
    )
    filepath.write_text(content)
    log(f"已为 {chat_name} 自动创建档案")
    return filepath


def get_profile_for_chat(chat_name, username):
    """查找聊天对应的档案路径"""
    with _state_lock:
        if username in identifier_to_profile:
            return identifier_to_profile[username]
        if chat_name in identifier_to_profile:
            return identifier_to_profile[chat_name]
        for key, path in profile_contacts.items():
            if (
                chat_name
                and key
                and len(chat_name) >= 2
                and len(key) >= 2
                and (chat_name in key or key in chat_name)
            ):
                return path
    if chat_name in monitored_contacts and chat_name not in identifier_to_profile:
        return auto_create_profile(chat_name, username)
    return None


def is_monitoring_this(chat_name, username):
    """检查是否正在监控此联系人，支持多账号匹配"""
    if chat_name in monitored_contacts:
        return True
    if username in identifier_to_profile:
        return True
    return False


def get_alias_names(chat_name):
    """获取联系人对应的主名称和别名列表"""
    with _state_lock:
        for profile_name, aliases in profile_name_to_chat_names.items():
            if chat_name == profile_name or chat_name in aliases:
                other_aliases = [
                    a for a in aliases if a != chat_name
                ]
                return profile_name, other_aliases
        return chat_name, []


# ===== 10. Message Loading and Processing =====
def load_today_messages(username, since_ts=0):
    """拉取今天的消息（增量），since_ts>0 时只返回比它新的消息"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    output = run_cmd(
        [
            "wechat-cli",
            "history",
            username,
            "--start-time",
            today_str,
            "--limit",
            str(MAX_HISTORY_LIMIT),
        ],
        timeout=HISTORY_TIMEOUT,
    )
    try:
        data = json.loads(output)
        messages = data.get("messages", [])
        now = datetime.now()
        today_start = int(datetime(now.year, now.month, now.day).timestamp())
        tomorrow_start = today_start + 86400
        today_msgs = []
        for m in messages:
            if isinstance(m, str) and m.strip():
                if today_str in m:
                    today_msgs.append(m.strip())
            elif isinstance(m, dict):
                ts = m.get("time", m.get("timestamp", 0))
                if isinstance(ts, (int, float)) and ts > 0:
                    if today_start <= ts < tomorrow_start:
                        if ts <= since_ts:
                            continue
                        sender = m.get("sender", m.get("from_user", ""))
                        content = m.get("content", m.get("text", ""))
                        ts_str = datetime.fromtimestamp(ts).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        today_msgs.append(f"[{ts_str}] {sender}: {content}")
                elif isinstance(ts, str) and ts:
                    if today_str in ts:
                        sender = m.get("sender", m.get("from_user", ""))
                        content = m.get("content", m.get("text", ""))
                        today_msgs.append(f"[{ts}] {sender}: {content}")
        return today_msgs
    except Exception:
        return []


def load_last_n_messages(username, limit=10, lock_timeout=5):
    """加载最近N条消息"""
    output = run_cmd(
        ["wechat-cli", "history", username, "--limit", str(limit)],
        timeout=HISTORY_TIMEOUT,
        lock_timeout=lock_timeout,
    )
    try:
        data = json.loads(output)
        return data.get("messages", [])
    except Exception:
        return []


def append_chat_log(profile_path, messages, chat_name):
    """将当日聊天记录整章节覆盖写入档案的「当日聊天记录」章节"""
    if not profile_path or not profile_path.exists():
        return
    if not messages:
        return

    today = datetime.now().strftime("%Y-%m-%d")

    all_lines = []
    for m in messages:
        if isinstance(m, str) and m.strip():
            all_lines.append(m.strip())
        elif isinstance(m, dict):
            ts = m.get("time", m.get("timestamp", ""))
            sender = m.get("sender", m.get("from_user", ""))
            text = m.get("content", m.get("text", ""))
            line = f"[{ts}] {sender}: {text}"
            if line.strip():
                all_lines.append(line.strip())
    if not all_lines:
        return

    with _file_lock:
        content = profile_path.read_text()

        section_header = "## 当日聊天记录"
        alt_header = "### 当日聊天记录"
        today_block = f"**{today}**\n" + "\n".join(all_lines) + "\n"

        header_match = re.search(
            rf"(?<=\n)({re.escape(section_header)}|{re.escape(alt_header)})\n",
            content,
        )
        if not header_match:
            content = content.rstrip() + "\n\n" + section_header + "\n" + today_block
            profile_path.write_text(content)
            log(f"📝 写入 {len(all_lines)} 条聊天记录到 {profile_path.stem}")
            _increment_today_updates()
            return

        header_pos = header_match.start()
        next_header_match = re.search(r"\n## ", content[header_pos + 1 :])
        if next_header_match:
            end_pos = header_pos + 1 + next_header_match.start()
        else:
            end_pos = len(content)

        section_content = content[header_pos:end_pos]

        today_pattern = re.compile(
            r"^\*\*" + re.escape(today) + r"\*\*\n", re.MULTILINE
        )
        today_match = today_pattern.search(section_content)
        if today_match:
            block_start = header_pos + today_match.start()
            rest = section_content[today_match.end() :]
            next_day = re.search(r"^\*\*\d{4}-\d{2}-\d{2}\*\*", rest, re.MULTILINE)
            if next_day:
                block_end = header_pos + today_match.end() + next_day.start()
            else:
                block_end = end_pos
            new_content = content[:block_start] + today_block + content[block_end:]
        else:
            new_content = content[:end_pos] + today_block + content[end_pos:]

        profile_path.write_text(new_content)
        _increment_today_updates()
        log(
            f"📝 {'更新' if today_match else '追加'} {len(all_lines)} 条聊天记录"
            f"到 {profile_path.stem}"
        )


def _increment_today_updates():
    """增加今日更新计数"""
    global today_updates, today_updates_date
    today = datetime.now().strftime("%Y-%m-%d")
    if today_updates_date != today:
        today_updates = 0
        today_updates_date = today
    today_updates += 1


def _parse_message_time(msg_str):
    """从消息字符串 '[2026-06-04 18:00] sender: content' 提取时间戳排序"""
    m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]", msg_str)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
            return dt.timestamp()
        except ValueError:
            pass
    return 0


def process_new_messages(username, chat_name, new_msg_count):
    """处理新消息——全量拉取 + 去重合并到档案"""
    if chat_name in EXCLUDE_CHATS:
        return

    profile_path = get_profile_for_chat(chat_name, username)
    if not profile_path:
        return

    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 读档案已有今日聊天记录，建立去重索引
    existing_lines = []
    existing_set = set()
    if profile_path.exists():
        content = profile_path.read_text()
        section_match = re.search(
            r"## 当日聊天记录\n(.+?)(?=\n## |\Z)", content, re.DOTALL
        )
        if section_match:
            section = section_match.group(1)
            today_block = re.search(
                rf"^\*\*{re.escape(today)}\*\*\n(.+?)(?=\n\*\*\d{{4}}-\d{{2}}-\d{{2}}\*\*|\Z)",
                section,
                re.MULTILINE | re.DOTALL,
            )
            if today_block:
                raw = today_block.group(1).strip()
                existing_lines = [l.strip() for l in raw.split("\n") if l.strip()]
                for line in existing_lines:
                    existing_set.add(line)

    # 2. 全量拉取今天的消息
    messages = load_today_messages(username)

    # 3. 只取真正的新消息
    new_lines = [m for m in messages if m not in existing_set]
    if not new_lines:
        return

    # 4. 合并 + 去重 + 按时间戳排序（修复版）
    all_lines = existing_lines + new_lines
    seen = set()
    deduped = []
    for line in all_lines:
        key = line.strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)
    deduped.sort(key=_parse_message_time)

    # 5. 更新缓存 + 计数
    with _state_lock:
        message_cache[chat_name] = deduped[-10:]
        message_counts[chat_name] = message_counts.get(chat_name, 0) + len(new_lines)
        _trim_message_cache()

    # 6. 整章节重写
    append_chat_log(profile_path, deduped, chat_name)


# ===== 11. LLM Client =====
def _call_llm(prompt, system_prompt="", max_tokens=800, temperature=0.3):
    """调用 LLM，支持 openai 和 anthropic 两种接口格式"""
    api_key = LLM_CONFIG["api_key"]
    if not api_key:
        return None

    mode = LLM_CONFIG["mode"]
    base = LLM_CONFIG["api_base"]
    model = LLM_CONFIG["model"]

    try:
        if mode == "anthropic":
            resp = requests.post(
                f"{base}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=LLM_TIMEOUT,
            )
            result = resp.json()
            for block in result.get("content", []):
                if block.get("type") == "text":
                    return block.get("text", "")
        else:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = requests.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=LLM_TIMEOUT,
            )
            result = resp.json()
            return (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
    except Exception as e:
        log(f"LLM 调用失败 ({mode}): {e}", "warn")
        return None


def _extract_json_from_llm_reply(reply):
    """从 LLM 回复中提取并解析 JSON"""
    if not reply:
        return None

    # 尝试直接解析
    for strategy in [
        lambda: json.loads(reply.strip()),
        lambda: json.loads(
            re.search(
                r"```(?:json)?\s*\n?(.*?)\n?```", reply, re.DOTALL
            ).group(1)
        ),
    ]:
        try:
            data = strategy()
            if isinstance(data, (dict, list)):
                return data
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return None


# ===== 12. Suggestions + Analysis =====
def _get_suggestions_and_analysis(chat_name, chat_text):
    """生成建议回复 + 对话分析（一次 LLM 调用）"""
    if not LLM_CONFIG["api_key"]:
        return {
            "suggestions": [{"reply": "（未配置 API key）", "reason": ""}],
            "analysis": None,
        }

    lines = [l for l in chat_text.split("\n") if l.strip()]
    last_line = lines[-1] if lines else ""

    # 判断最后一条消息是谁发的
    sender_match = re.match(r"\[.*?\]\s*(.+?):\s", last_line)
    is_user = False
    if sender_match:
        sender = sender_match.group(1).strip()
        is_user = sender.lower() != chat_name.lower()
    direction = (
        "你刚发了消息（等对方回复/或继续主动聊）"
        if is_user
        else "对方发来消息（等你回复）"
    )

    prompt = f"""和「{chat_name}」的最近聊天记录：
{chat_text}

每行格式为 [时间] 发送者: 内容。
「{chat_name}」发的消息是对方说的，其他名字（如me、我、你的微信号等）是你自己说的。
{direction}

请以你的角度（你=用户自己），做两件事：

1. 对话分析：概括主题、对方的语气/情绪、关键信息点
2. 建议回复：生成3条贴合当下语境的建议回复
   - 如果最后一条是你发的 → 帮你想接下来聊什么延续话题
   - 如果最后一条是对方发的 → 帮你想怎么回复对方

JSON格式，建议回复每句20字以内，语气自然日常：
{{"analysis":{{"summary":"对话主题概括（一句话）","tone":"对方情绪/语气（如：积极、着急、疑惑等）","key_points":["关键信息1","关键信息2","关键信息3"]}},"suggestions":[{{"reply":"内容","reason":"理由"}}]}}"""

    for attempt in range(3):
        try:
            reply = _call_llm(
                prompt=prompt,
                system_prompt="你是一个聊天助手。只输出JSON，不要任何思考和解释。",
                max_tokens=1000,
                temperature=0.3,
            )
            if not reply:
                continue

            # 修复残缺JSON
            reply = re.sub(r'}\s*,"reply"', r'},\n{"reply"', reply)

            data = _extract_json_from_llm_reply(reply)
            if not data:
                continue

            result = {"suggestions": [], "analysis": None}

            # 解析 suggestions
            suggestions_raw = data.get("suggestions", data.get("replies", []))
            if isinstance(suggestions_raw, list):
                for item in suggestions_raw[:3]:
                    if isinstance(item, dict):
                        result["suggestions"].append(
                            {
                                "reply": item.get("reply", str(item)),
                                "reason": item.get("reason", ""),
                            }
                        )
                    elif isinstance(item, str):
                        result["suggestions"].append(
                            {"reply": item, "reason": ""}
                        )
            if not result["suggestions"]:
                result["suggestions"].append(
                    {"reply": "（生成失败，请稍后重试）", "reason": ""}
                )

            # 解析 analysis
            analysis = data.get("analysis")
            if isinstance(analysis, dict):
                result["analysis"] = {
                    "summary": analysis.get("summary", ""),
                    "tone": analysis.get("tone", ""),
                    "key_points": analysis.get("key_points", []),
                }

            return result

        except Exception as e:
            log(f"建议/分析第 {attempt+1} 次失败: {e}", "warn")
            time.sleep(1)

    return {
        "suggestions": [{"reply": "（生成失败，请稍后重试）", "reason": "LLM调用超时"}],
        "analysis": None,
    }


# ===== 13. Monitoring =====
def _get_wechat_db_dir():
    """读取 wechat-cli 配置中的数据库目录"""
    config_path = os.path.expanduser("~/.wechat-cli/config.json")
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("db_dir", "")
    except Exception:
        return ""


class WeChatDBHandler(FileSystemEventHandler):
    """文件系统事件处理器：DB / WAL / SHM 变化后防抖触发 new-messages"""

    # SQLite WAL 模式下，真实写发生在 *.db-wal / *.db-shm
    _DB_SUFFIXES = (".db", ".db-wal", ".db-shm")
    _hit_count = 0  # 类级命中计数，便于面板诊断 watchdog 是否在工作

    def __init__(self):
        self._timer = None
        self._debounce_lock = threading.Lock()

    def _should_handle(self, path: str) -> bool:
        return any(path.endswith(s) for s in self._DB_SUFFIXES)

    def on_modified(self, event):
        if event.is_directory:
            return
        if not self._should_handle(event.src_path):
            return
        self._schedule(event.src_path)

    def on_created(self, event):
        # WAL/SHM 初次创建时只有 created 事件
        if event.is_directory:
            return
        if not self._should_handle(event.src_path):
            return
        self._schedule(event.src_path)

    def _schedule(self, path: str):
        WeChatDBHandler._hit_count += 1
        log(
            f"📂 db 文件变化 #{WeChatDBHandler._hit_count}: "
            f"{os.path.basename(path)}"
        )
        with self._debounce_lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(
                DB_DEBOUNCE_SECONDS, self._on_db_changed
            )
            self._timer.daemon = True
            self._timer.start()

    def _on_db_changed(self):
        # 只通知主循环，由主循环统一调 _do_poll，避免和主轮询抢锁
        if monitor_running:
            _file_changed_flag.set()


def _start_file_watch(db_dir):
    """启动文件监控（watchdog）"""
    if not WATCHDOG_AVAILABLE:
        log("watchdog 不可用，跳过文件监控", "warn")
        return None
    if not db_dir or not os.path.isdir(db_dir):
        log(f"⚠️ 微信数据库目录不存在: {db_dir}，仅使用兜底轮询", "warn")
        return None

    try:
        handler = WeChatDBHandler()
        observer = Observer()
        # 微信 db_storage 下有 session_db/ 等子目录，必须 recursive
        observer.schedule(handler, db_dir, recursive=True)
        observer.daemon = True
        observer.start()
        log(f"📁 文件监控已启动: {db_dir} (recursive, watch: .db/.db-wal/.db-shm)")
        return observer
    except Exception as e:
        log(f"文件监控启动失败: {e}，仅使用兜底轮询", "warn")
        return None


def _do_poll():
    """执行一次 wechat-cli new-messages 轮询"""
    global _consecutive_empty

    # 连续失败时跳过，避免反复超时
    if _consecutive_empty >= 3:
        # 静默跳过，每 10 次记录一次
        if _consecutive_empty % 10 == 0:
            log(f"wechat-cli 持续失败 {_consecutive_empty} 次，暂停轮询 {CONSECUTIVE_FAILURE_BACKOFF}s", "warn")
        _consecutive_empty += 1
        if _consecutive_empty >= 10:
            _consecutive_empty = 3  # 重置退避计数
        return

    output = run_cmd(
        ["wechat-cli", "new-messages"], timeout=WEBCOMMAND_TIMEOUT, lock_timeout=WEBCOMMAND_LOCK_TIMEOUT
    )
    if not output:
        _consecutive_empty += 1
        return

    _consecutive_empty = 0
    try:
        data = json.loads(output)
        if data.get("first_call"):
            log("首次调用 new-messages，建立基线")
            return

        messages = data.get("messages", [])
        for msg in messages:
            chat_name = msg.get("chat", "")
            username = msg.get("username", "")
            if chat_name in EXCLUDE_CHATS:
                continue
            if not username or not chat_name:
                continue

            # 同联系人去重
            last_key = f"{username}_{chat_name}"
            now = int(time.time())
            with _state_lock:
                last_time = last_seen.get(last_key, 0)
                if now - last_time < LAST_SEEN_DEDUP_WINDOW:
                    continue
                last_seen[last_key] = now

            if is_monitoring_this(chat_name, username):
                log(f"📩 {chat_name} 发来新消息（记录中）")
                process_new_messages(username, chat_name, 0)
                _sse_broadcast(
                    "new_message",
                    {"chat": chat_name, "username": username, "time": time.time()},
                )
            else:
                log(f"💬 {chat_name} 发来新消息（仅提示，未监控）")
                _sse_broadcast(
                    "new_message",
                    {"chat": chat_name, "username": username, "time": time.time()},
                )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log(f"new-messages 解析异常: {e}", "warn")


def _do_calibration():
    """校准：对有新消息的联系人做全量对账"""
    with _state_lock:
        pending = list(_calibration_pending)
        _calibration_pending.clear()

    if not pending:
        return

    log(f"🔍 校准 {len(pending)} 个联系人的聊天记录")
    for username, chat_name in pending:
        if not monitor_running:
            break
        try:
            process_new_messages(username, chat_name, 0)
        except Exception as e:
            log(f"校准失败 {chat_name}: {e}", "warn")




def monitor_loop():
    """主监控循环：文件监控 + 兜底轮询 + 后台校准"""
    global monitor_running, _fallback_poll_ts, _calibration_ts

    load_state()
    log("🚀 监控线程启动")
    init_profiles()
    refresh_all_contacts()
    log(
        f"📋 监控 {len(monitored_contacts)} 个联系人，"
        f"共 {len(all_contacts_cache)} 个微信会话"
    )

    # 后台重试（OneDrive 未挂载等情况）
    def _retry_init():
        for _ in range(10):
            with _state_lock:
                if profile_names:
                    return
            time.sleep(30)
            init_profiles()
            with _state_lock:
                if profile_names:
                    refresh_all_contacts()
                    log(f"📋 重试后加载到 {len(profile_names)} 个档案")
                    return

    if not profile_names:
        threading.Thread(target=_retry_init, daemon=True).start()

    # 预热消息缓存
    def _warmup_cache():
        # 等待主轮询先建立基线，避免抢锁
        time.sleep(5)
        with _state_lock:
            contacts = list(monitored_contacts)[:WARMUP_CONTACTS_LIMIT]
        for name in contacts:
            try:
                # 极短超时：拿不到就跳过
                msgs = load_last_n_messages(name, limit=10, lock_timeout=2)
                if msgs:
                    with _state_lock:
                        message_cache[name] = msgs[-10:]
            except Exception:
                pass
        log(f"📦 消息缓存预热完成 ({len(message_cache)} 个联系人)")

    threading.Thread(target=_warmup_cache, daemon=True).start()

    # 主动刷新缓存：保证 suggest-reply 永远有可用数据
    # 锁策略：缓存刷新耐心等（30s），主轮询短超时（10s）放弃，绝不死磕
    # 抖动策略：每轮加 0-30s 随机偏移，避免和 60s 兜底轮询系统撞点
    def _cache_refresh_loop():
        # 先等 30s 让监控主轮询建立基线，再加 0-30s 抖动错开首轮
        time.sleep(30 + random.uniform(0, 30))
        while monitor_running:
            time.sleep(CACHE_REFRESH_INTERVAL + random.uniform(0, 30))
            if not monitor_running:
                break
            with _state_lock:
                contacts = list(monitored_contacts)[:WARMUP_CONTACTS_LIMIT]
            for name in contacts:
                if not monitor_running:
                    break
                # 长超时（30s）等主轮询释放锁；主轮询通常 5-10s 完成
                try:
                    msgs = load_last_n_messages(name, limit=10, lock_timeout=30)
                    if msgs:
                        with _state_lock:
                            message_cache[name] = msgs[-10:]
                except Exception:
                    pass
            log(f"♻️ 缓存主动刷新完成 ({len(message_cache)} 个联系人)")

    threading.Thread(target=_cache_refresh_loop, daemon=True).start()

    # 启动文件监控
    db_dir = _get_wechat_db_dir()
    observer = _start_file_watch(db_dir)

    # 启动状态持久化后台线程
    threading.Thread(target=_persist_state_loop, daemon=True).start()

    _fallback_poll_ts = time.time()
    _calibration_ts = time.time()

    # 首次快速轮询建立基线
    _do_poll()

    while monitor_running:
        now = time.time()

        # 文件变化即时响应（watchdog 设的 flag，1s 内响应）
        file_triggered = _file_changed_flag.is_set()
        if file_triggered:
            _file_changed_flag.clear()
            _fallback_poll_ts = now  # 文件变化触发后重置兜底计时器
            _do_poll()
        # 兜底轮询（60s 周期，兜底 watchdog 不工作时）
        elif now - _fallback_poll_ts >= FALLBACK_POLL_INTERVAL:
            _fallback_poll_ts = now
            if _consecutive_empty >= IDLE_POLL_THRESHOLD:
                log(
                    f"连续 {_consecutive_empty} 次 new-messages 无响应，"
                    f"等待 {FALLBACK_POLL_INTERVAL} 秒后重试",
                    "warn",
                )
            _do_poll()

        # 后台校准
        if now - _calibration_ts >= CALIBRATION_INTERVAL:
            _calibration_ts = now
            _do_calibration()

        time.sleep(1)

    # 清理
    if observer:
        observer.stop()
        observer.join()

    log("监控线程已停止")


def start_monitor():
    """启动监控"""
    global monitor_running, monitor_thread
    if monitor_running and monitor_thread and monitor_thread.is_alive():
        return
    monitor_running = True
    start_file = os.path.join(SCRIPT_DIR, "start.txt")
    os.makedirs(os.path.dirname(start_file), exist_ok=True)
    with open(start_file, "w") as f:
        f.write(str(time.time()))
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    log("▶️ 监控已启动")


def stop_monitor():
    """停止监控"""
    global monitor_running
    monitor_running = False
    log("⏹ 监控已停止")
    state = {"running": False}
    save_state(state)


def _get_running_time():
    """获取运行时长"""
    if not monitor_running:
        return "已停止"
    start_file = os.path.join(SCRIPT_DIR, "start.txt")
    if os.path.exists(start_file):
        try:
            with open(start_file) as _f:
                start_ts = float(_f.read().strip())
            elapsed = int(time.time() - start_ts)
            if elapsed < 60:
                return f"{elapsed}s"
            elif elapsed < 3600:
                return f"{elapsed // 60}m"
            else:
                return f"{elapsed // 3600}h{(elapsed % 3600) // 60}m"
        except Exception:
            pass
    return "-"


def clear_chat_log(chat, date):
    """删除档案中指定日期的聊天记录"""
    profile_path = PROFILE_DIR / f"{chat}.md"
    if not profile_path.exists():
        return False
    try:
        with _file_lock:
            content = profile_path.read_text()
            section_match = re.search(
                r"(## 当日聊天记录\n)(.+?)(?=\n## |\Z)", content, re.DOTALL
            )
            if not section_match:
                return False
            header_start = section_match.start(1)
            section_start = section_match.start(2)
            section_end = section_match.end(2)
            section_content = section_match.group(2)

            date_pattern = re.compile(
                rf"^\*\*{re.escape(date)}\*\*\n.+?(?=\n\*\*\d{{4}}-\d{{2}}-\d{{2}}\*\*|\Z)",
                re.MULTILINE | re.DOTALL,
            )
            match = date_pattern.search(section_content)
            if not match:
                return False

            new_section = (
                section_content[: match.start()].rstrip()
                + "\n"
                + section_content[match.end() :].lstrip()
            )
            new_section = new_section.strip()

            if not new_section:
                new_content = (
                    content[:header_start].rstrip() + "\n" + content[section_end:]
                )
            else:
                new_content = (
                    content[:section_start]
                    + new_section
                    + "\n"
                    + content[section_end:]
                )

            profile_path.write_text(new_content)
            log(f"🗑️ 已清除 {chat} 的 {date} 聊天记录")
        return True
    except Exception as e:
        log(f"清除聊天记录失败 {chat}/{date}: {e}", "error")
        return False


# ===== 14. SSE Broadcast =====
def _sse_broadcast(event_type, data):
    """向所有 SSE 客户端推送事件"""
    with _sse_lock:
        dead = []
        for client in _sse_clients:
            try:
                client.write(
                    f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n".encode("utf-8")
                )
                client.flush()
            except Exception:
                dead.append(client)
        for d in dead:
            _sse_clients.remove(d)


# ===== 15. HTTP Server =====
class MonitorHandler(http.server.BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    # ---------- GET ----------
    def do_GET(self):
        if not _check_auth(self):
            self._json({"error": "unauthorized"}, 401)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._html(HTML_PAGE)

        elif path == "/api/public-token":
            self._json({"token": API_TOKEN})

        elif path == "/api/status":
            self._json({
                "running": monitor_running,
                "monitored_count": len(monitored_contacts),
                "monitored_contacts": sorted(monitored_contacts),
                "profile_list": sorted(profile_names),
                "poll_interval": poll_interval,
                "today_updates": today_updates,
                "running_time": _get_running_time(),
                "logs": recent_logs[-30:],
                "alias_map": {str(k): list(v) for k, v in profile_identifiers.items()},
            })

        elif path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with _sse_lock:
                _sse_clients.append(self.wfile)
            try:
                self.wfile.write(
                    f"data: {json.dumps({'type': 'connected', 'time': time.time()}, ensure_ascii=False)}\n\n".encode("utf-8")
                )
                self.wfile.flush()
            except Exception:
                pass
            while monitor_running:
                try:
                    time.sleep(SSE_HEARTBEAT_INTERVAL)
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                except Exception:
                    break
            return

        elif path == "/api/config":
            self._json({
                "profiles_dir": CONFIG["profiles_dir"],
                "llm": {
                    "mode": CONFIG["llm"]["mode"],
                    "api_key": "***" if CONFIG["llm"]["api_key"] else "",
                    "api_key_env": CONFIG["llm"]["api_key_env"],
                    "api_base": CONFIG["llm"]["api_base"],
                    "model": CONFIG["llm"]["model"],
                },
            })

        elif path == "/api/exclude-chats":
            self._json({"exclude_chats": CONFIG.get("exclude_chats", [])})

        elif path == "/api/profile":
            pname = qs.get("name", [""])[0]
            if pname:
                # 直接在档案目录查找，不走 get_profile_for_chat 避免锁竞争
                md_file = PROFILE_DIR / (pname + ".md")
                if md_file.exists():
                    self._json({"name": pname, "content": md_file.read_text(encoding="utf-8"), "exists": True})
                else:
                    # 尝试模糊匹配
                    found = None
                    if PROFILE_DIR.is_dir():
                        for f in PROFILE_DIR.glob("*.md"):
                            if pname in f.stem:
                                found = f
                                break
                    if found:
                        self._json({"name": pname, "content": found.read_text(encoding="utf-8"), "exists": True})
                    else:
                        self._json({"name": pname, "content": "", "exists": False})
            else:
                self._json({"error": "name required"}, 400)


        elif path == "/api/contacts":
            global all_contacts_cache
            if not all_contacts_cache:
                refresh_all_contacts()
            monitored = set(monitored_contacts)
            available = [c for c in all_contacts_cache if c["chat"] not in monitored]
            self._json({"contacts": available})

        elif path == "/api/suggest-reply":
            qs = urllib.parse.parse_qs(parsed.query)
            chat = qs.get("chat", [""])[0]
            username = qs.get("username", [""])[0]
            if not chat:
                self._json({"error": "missing chat"}, 400)
                return
            if not username:
                for c in all_contacts_cache:
                    if c["chat"] == chat:
                        username = c["username"]
                        break
            if not username:
                username = chat

            # 优先用缓存
            raw = []
            with _state_lock:
                if chat in message_cache:
                    raw = list(message_cache[chat])

            # 多账号合并
            profile_path_for_chat = get_profile_for_chat(chat, username)
            if profile_path_for_chat:
                profile_name = os.path.splitext(os.path.basename(profile_path_for_chat))[0]
                with _state_lock:
                    alias_names = profile_name_to_chat_names.get(profile_name, set())
                for alias in alias_names:
                    if alias != chat:
                        with _state_lock:
                            cached = message_cache.get(alias, [])
                        if cached:
                            raw.extend(cached)

            # 缓存没有 → 从 wechat-cli 实时拉取（非阻塞拿锁，不卡界面）
            if not raw:
                raw = load_last_n_messages(username, limit=15)
                if not raw:
                    self._json({"chat": chat, "error": "暂无聊天记录", "suggestions": [], "analysis": None})
                    return

            formatted = []
            for m in raw[-15:]:
                if isinstance(m, str):
                    formatted.append(m.strip())
                elif isinstance(m, dict):
                    ts = m.get("time", m.get("timestamp", ""))
                    sender = m.get("sender", m.get("from_user", ""))
                    text = m.get("content", m.get("text", ""))
                    formatted.append(f"[{ts}] {sender}: {text}")
            chat_text = "\n".join(formatted)

            result = _get_suggestions_and_analysis(chat, chat_text)
            self._json({"chat": chat, **result})

        else:
            self._json({"error": "not found"}, 404)

    # ---------- POST ----------
    def do_POST(self):
        if not _check_auth(self):
            self._json({"error": "unauthorized"}, 401)
            return
        path = urllib.parse.urlparse(self.path).path

        def _read_body():
            length = int(self.headers.get("Content-Length", 0))
            if length > 1048576:
                self._json({"error": "request too large"}, 413)
                return None
            return json.loads(self.rfile.read(length))


        if path == "/api/models":
            body = _read_body()
            if body is None:
                return
            llm = body.get("llm") or {}
            mode = llm.get("mode", "openai")
            api_key = (llm.get("api_key") or "").strip()
            api_base = (llm.get("api_base") or "").strip().rstrip("/")
            if not api_key:
                self._json({"error": "请先填写 API 密钥"}, 400)
                return
            if not api_base:
                self._json({"error": "请先填写 API 地址"}, 400)
                return
            headers = {}
            if mode == "anthropic":
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            else:
                headers = {"Authorization": f"Bearer {api_key}"}
            candidates = [f"{api_base}/models", f"{api_base}/v1/models"]
            last_err = None
            for url in candidates:
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code != 200:
                        last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                        continue
                    data = r.json()
                    if isinstance(data, dict) and "data" in data:
                        models = [m.get("id") for m in data["data"] if isinstance(m, dict) and m.get("id")]
                    elif isinstance(data, dict) and "models" in data:
                        models = [m.get("id") if isinstance(m, dict) else m for m in data["models"]]
                    elif isinstance(data, list):
                        models = [m.get("id") if isinstance(m, dict) else m for m in data]
                    else:
                        last_err = "返回格式无法解析"
                        continue
                    if models:
                        log(f"📋 模型列表拉取成功: {url} -> {len(models)} 个")
                        self._json({"models": models, "source": url})
                        return
                    last_err = "返回列表为空"
                except Exception as e:
                    last_err = str(e)
            self._json({"error": f"无法获取模型列表: {last_err or '未知错误'}"}, 400)

        elif path == "/api/start":
            start_monitor()
            self._json({"success": True, "running": monitor_running})

        elif path == "/api/stop":
            stop_monitor()
            self._json({"success": True, "running": monitor_running})

        elif path == "/api/set-interval":
            body = _read_body()
            if body is None:
                return
            val = int(body.get("interval", POLL_INTERVAL_DEFAULT))
            if val < POLL_INTERVAL_MIN:
                val = POLL_INTERVAL_MIN
            global poll_interval
            poll_interval = val
            log(f"⏱ 轮询间隔已改为 {val} 秒")
            self._json({"success": True, "interval": val})

        elif path == "/api/add-contact":
            body = _read_body()
            if body is None:
                return
            chat = body.get("chat", "")
            if not chat:
                self._json({"error": "missing chat"}, 400)
                return
            username = body.get("username", "")
            if not username:
                for c in all_contacts_cache:
                    if c["chat"] == chat:
                        username = c.get("username", "")
                        break
            with _state_lock:
                monitored_contacts.add(chat)
            log(f"➕ 手动添加监控联系人: {chat}")
            self._json({"success": True})

        elif path == "/api/remove-contact":
            body = _read_body()
            if body is None:
                return
            chat = body.get("chat", "")
            with _state_lock:
                if chat and chat in monitored_contacts:
                    monitored_contacts.discard(chat)
                    log(f"➖ 取消监控联系人: {chat}")
                    self._json({"success": True})
                else:
                    self._json({"error": "not found"}, 404)

        elif path == "/api/exclude-chats":
            body = _read_body()
            if body is None:
                return
            CONFIG["exclude_chats"] = body.get("exclude_chats", [])
            save_config()
            log(f"📝 排除会话已更新: {CONFIG['exclude_chats']}")
            self._json({"success": True})

        elif path == "/api/config":
            body = _read_body()
            if body is None:
                return
            changed = False
            if "profiles_dir" in body:
                new_dir = os.path.expanduser(body["profiles_dir"])
                if new_dir != CONFIG["profiles_dir"]:
                    CONFIG["profiles_dir"] = new_dir
                    global PROFILE_DIR
                    PROFILE_DIR = Path(new_dir)
                    changed = True
            if "llm" in body and isinstance(body["llm"], dict):
                llm = body["llm"]
                for key in ("mode", "api_key_env", "api_base", "model"):
                    if key in llm and llm[key] != CONFIG["llm"].get(key):
                        CONFIG["llm"][key] = llm[key]
                        changed = True
                if "api_key" in llm and llm["api_key"] and llm["api_key"] != "***":
                    if llm["api_key"] != CONFIG["llm"].get("api_key"):
                        CONFIG["llm"]["api_key"] = llm["api_key"]
                        changed = True
            if changed:
                save_config()
                threading.Thread(target=init_profiles, daemon=True).start()
                log("⚙️ 配置已更新，档案已重载", "info")
            self._json({"success": True})

        elif path == "/api/set-llm-mode":
            body = _read_body()
            if body is None:
                return
            mode = body.get("mode", "")
            if mode in ("anthropic", "openai"):
                LLM_CONFIG["mode"] = mode
                log(f"🔁 LLM 接口切换到 {mode} 模式")
                self._json({"success": True, "mode": mode})
            else:
                self._json({"error": f"未知模式: {mode}，支持: anthropic, openai"}, 400)

        elif path == "/api/clear-chat-log":
            body = _read_body()
            if body is None:
                return
            chat = body.get("chat", "")
            date = body.get("date", "")
            if not chat or not date:
                self._json({"error": "missing chat or date"}, 400)
                return
            ok = clear_chat_log(chat, date)
            self._json({"success": ok})

        else:
            self._json({"error": "not found"}, 404)

    # ---------- OPTIONS ----------
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ---------- Helpers ----------
    def _html(self, content, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", f"http://localhost:{PORT}")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass


# ===== 16. HTML Template =====
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>微信监控面板</title>
<script>
(function(){var t=localStorage.getItem("theme")||(window.matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light");document.documentElement.setAttribute("data-theme",t)})();
</script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
:root{--bg:#f4f7fc;--card:rgba(255,255,255,.78);--line:#e8edf5;--p1:#7b61ff;--p2:#5d86ff;--txt:#1f2937;--muted:#94a3b8;--input-bg:#f7f9fd;--glass-border:rgba(255,255,255,.9);--glass-shadow:rgba(30,41,59,.08);--modal-bg:#fff;--cancel-bg:#f5f5f8;--tag-bg:rgba(123,97,255,.08);--suggest-bg:rgba(123,97,255,.04);--suggest-border:rgba(123,97,255,.1)}
[data-theme="dark"]{--bg:#0f172a;--card:rgba(30,41,59,.85);--line:rgba(255,255,255,.07);--txt:#e2e8f0;--muted:#64748b;--input-bg:rgba(255,255,255,.05);--glass-border:rgba(255,255,255,.08);--glass-shadow:rgba(0,0,0,.35);--modal-bg:#1e293b;--cancel-bg:rgba(255,255,255,.06);--tag-bg:rgba(123,97,255,.15);--suggest-bg:rgba(123,97,255,.08);--suggest-border:rgba(123,97,255,.15)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,PingFang SC,sans-serif;color:var(--txt);background:var(--bg);min-height:100vh}
body{transition:background .3s}
body:before,body:after{content:"";position:fixed;border-radius:50%;filter:blur(100px);pointer-events:none;z-index:-1;transition:background .3s}
body:before{width:420px;height:420px;left:-120px;top:-120px;background:rgba(123,97,255,.12)}
body:after{width:320px;height:320px;right:-80px;top:60px;background:rgba(93,134,255,.1)}
.wrap{max-width:1600px;margin:auto;padding:24px}
.glass{background:var(--card);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid var(--glass-border);box-shadow:0 20px 60px var(--glass-shadow);border-radius:30px;transition:background .3s,border-color .3s,box-shadow .3s}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.brand{display:flex;gap:18px;align-items:center}
.logo{width:64px;height:64px;border-radius:20px;background:linear-gradient(135deg,var(--p1),var(--p2));position:relative;flex-shrink:0}
.logo:before,.logo:after{content:"";position:absolute;background:#fff;border-radius:50%}
.logo:before{width:24px;height:24px;left:14px;top:20px}
.logo:after{width:18px;height:18px;right:12px;top:12px}
.top-title{font-size:34px;font-weight:700}
.top-sub{color:var(--muted);font-size:14px;margin-top:2px}
.gear{width:56px;height:56px;display:flex;align-items:center;justify-content:center;font-size:22px;cursor:pointer;transition:transform .2s}
.gear:hover{transform:rotate(30deg)}
.status-bar{padding:18px 28px;display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}
.status-left{display:flex;gap:12px;align-items:center}
.dot{width:12px;height:12px;border-radius:50%;flex-shrink:0}
.dot.on{background:#3ccf6e;box-shadow:0 0 10px rgba(60,207,110,.45)}
.dot.off{background:#f87171;box-shadow:0 0 10px rgba(248,113,113,.35)}
.status-text{font-size:15px;font-weight:600}
.status-sub{color:var(--muted);font-size:13px}
.btn{padding:10px 24px;border-radius:14px;border:none;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;transition:all .2s}
.btn:disabled{opacity:.35;cursor:not-allowed}
.btn-start{background:linear-gradient(135deg,#3ccf6e,#28b855);color:#fff}
.btn-start:hover:not(:disabled){box-shadow:0 6px 20px rgba(60,207,110,.3)}
.btn-stop{background:linear-gradient(135deg,#ff6b6b,#ee5a24);color:#fff}
.btn-stop:hover:not(:disabled){box-shadow:0 6px 20px rgba(255,107,107,.3)}
:root{--settings-w:320px}
.layout{display:grid;grid-template-columns:var(--contacts-w) 1fr var(--settings-w);gap:22px;min-height:860px;transition:grid-template-columns .35s cubic-bezier(.4,0,.2,1)}
:root{--contacts-w:370px}
.panel{padding:24px;display:flex;flex-direction:column}
.panel h2{font-size:17px;font-weight:700;margin-bottom:14px}
.search{width:100%;height:48px;border:none;background:var(--input-bg);border-radius:14px;padding:0 16px;font-size:13px;font-family:inherit;outline:none;transition:box-shadow .2s;margin-bottom:10px}
.search:focus{box-shadow:0 0 0 2px rgba(123,97,255,.25)}
.search::placeholder{color:#B0B8C9}
.contact-list{flex:1;overflow-y:auto;min-height:0}
.contact-list::-webkit-scrollbar{width:3px}
.contact-list::-webkit-scrollbar-thumb{background:rgba(123,97,255,.15);border-radius:2px}
.contact{display:flex;justify-content:space-between;align-items:center;padding:14px 0;border-bottom:1px solid var(--line)}
.contact:last-child{border-bottom:none}
.contact-info{display:flex;gap:12px;align-items:center;min-width:0;flex:1}
.avatar{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px;flex-shrink:0}
.contact-name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.contact-meta{display:flex;gap:5px;margin-top:3px;flex-wrap:wrap}
.badge{font-size:11px;padding:3px 8px;border-radius:999px;font-weight:500}
.badge-profile{background:#eef3ff;color:#5a67ff}
.badge-manual{background:#f3f4f8;color:#6b7280}
.badge-alias{background:#f1e8ff;color:#7b61ff}
.contact-acts{display:flex;gap:6px;flex-shrink:0}
.btn-sm{padding:6px 12px;border-radius:8px;border:none;cursor:pointer;font-size:12px;font-weight:500;font-family:inherit;transition:all .15s;display:flex;align-items:center;gap:4px}
.btn-analyze{background:transparent;color:var(--p1);border:1px solid rgba(123,97,255,.2)}
.btn-analyze:hover{background:rgba(123,97,255,.06);border-color:rgba(123,97,255,.35)}
.btn-rm{background:none;border:none;cursor:pointer;color:#B0B8C9;padding:6px;border-radius:6px;font-size:14px;transition:all .15s}
.btn-rm:hover{color:#ff6b6b;background:rgba(255,107,107,.06)}
.btn-add{margin-top:12px;height:44px;border:1.5px dashed #d4d7e0;background:transparent;border-radius:12px;cursor:pointer;font-size:13px;font-weight:500;color:var(--p1);font-family:inherit;transition:all .2s}
.btn-add:hover{border-color:var(--p1);background:rgba(123,97,255,.03)}
.empty{text-align:center;color:#B0B8C9;padding:28px 0;font-size:13px}
.main-col{display:flex;flex-direction:column;gap:18px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.stat{padding:22px;position:relative;overflow:hidden}
.stat-title{font-size:13px;color:var(--muted);font-weight:500;margin-bottom:8px}
.stat-big{font-size:42px;font-weight:700;color:var(--p1);line-height:1}
.poll,.logs-card{padding:22px}
.poll h3,.logs-card h3{font-size:15px;font-weight:700;margin-bottom:10px}
.poll-sub{font-size:13px;color:var(--muted);margin-bottom:12px}
.interval-row{display:flex;align-items:center;gap:12px}
.interval-input{height:46px;background:var(--input-bg);border:1px solid var(--line);border-radius:12px;color:var(--txt);padding:0 14px;font-size:16px;font-weight:600;width:72px;text-align:center;outline:none;font-family:inherit;transition:border-color .2s}
.interval-input:focus{border-color:var(--p1)}
.interval-unit{color:var(--muted);font-size:13px}
.logs-card{flex:1;display:flex;flex-direction:column}
.log-scroll{flex:1;overflow-y:auto;max-height:380px}
.log-scroll::-webkit-scrollbar{width:3px}
.log-scroll::-webkit-scrollbar-thumb{background:rgba(123,97,255,.15);border-radius:2px}
.log{display:grid;grid-template-columns:72px 56px 1fr;gap:8px;padding:8px 0;border-bottom:1px solid var(--line);font-size:12px;align-items:baseline}
.log:last-child{border-bottom:none}
.log-time{color:#B0B8C9;font-family:'SF Mono','Fira Code',monospace;font-size:11px}
.log-level{padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;text-align:center}
.log-level.INFO{background:rgba(123,97,255,.1);color:var(--p1)}
.log-level.WARN{background:rgba(251,191,36,.12);color:#d97706}
.log-level.ERROR{background:rgba(248,113,113,.1);color:#ef4444}
.log-msg{color:#6b7280;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Settings collapsible */
.settings-col{position:relative;transition:all .35s cubic-bezier(.4,0,.2,1)}
.settings-col .settings-panel{transition:opacity .25s,transform .25s}
.settings-col.collapsed .settings-panel{opacity:0;pointer-events:none;transform:translateX(16px);position:absolute;inset:0;padding:24px}
.settings-toggle{position:absolute;left:0;top:0;bottom:0;width:48px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;cursor:pointer;background:var(--card);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid var(--glass-border);border-radius:30px 0 0 30px;z-index:5;transition:background .2s}
.settings-toggle:hover{background:rgba(123,97,255,.08)}
.settings-toggle svg{width:18px;height:18px;color:var(--muted);transition:color .2s}
.settings-toggle:hover svg{color:var(--p1)}
.settings-toggle span{writing-mode:vertical-rl;text-orientation:mixed;font-size:12px;color:var(--muted);letter-spacing:1px}
.settings-col.collapsed{width:48px;min-width:48px}
.contacts-col{position:relative;display:flex;flex-direction:column;transition:all .35s cubic-bezier(.4,0,.2,1)}
.contacts-col .panel{flex:1;min-height:0;transition:opacity .25s,transform .25s}
.contacts-col.collapsed .panel{opacity:0;pointer-events:none;transform:translateX(-16px)}
.contacts-toggle{position:absolute;right:0;top:0;bottom:0;width:48px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;cursor:pointer;background:var(--card);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid var(--glass-border);border-radius:0 30px 30px 0;z-index:5;transition:background .2s}
.contacts-toggle:hover{background:rgba(123,97,255,.08)}
.contacts-toggle svg{width:18px;height:18px;color:var(--muted);transition:color .2s}
.contacts-toggle:hover svg{color:var(--p1)}
.contacts-toggle span{writing-mode:vertical-rl;text-orientation:mixed;font-size:12px;color:var(--muted);letter-spacing:1px}
.contacts-col.collapsed{width:48px;min-width:48px}
.contacts-col:not(.collapsed) .contacts-toggle{opacity:0;pointer-events:none;width:0}
.settings-col:not(.collapsed) .settings-toggle{opacity:0;pointer-events:none;width:0}
.collapse-btn{width:32px;height:32px;border:none;background:transparent;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;color:var(--muted);transition:background .2s,color .2s}
.collapse-btn:hover{background:rgba(123,97,255,.1);color:var(--p1)}
/* Zoom slider */
.zoom-row{display:flex;align-items:center;gap:10px;margin:8px 0 16px}
.zoom-row input[type=range]{flex:1;-webkit-appearance:none;height:6px;border-radius:3px;background:var(--line);outline:none}
.zoom-row input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:linear-gradient(135deg,var(--p1),var(--p2));cursor:pointer;box-shadow:0 2px 6px rgba(123,97,255,.3)}
.zoom-val{font-size:13px;font-weight:600;color:var(--p1);min-width:36px;text-align:right}
/* Notification toggle */
.toggle-row{display:flex;align-items:center;gap:10px;margin:8px 0 16px}
.toggle-switch{position:relative;width:44px;height:24px;flex-shrink:0}
.toggle-switch input{opacity:0;width:0;height:0}
.toggle-track{position:absolute;inset:0;background:var(--line);border-radius:12px;cursor:pointer;transition:background .2s}
.toggle-track::after{content:"";position:absolute;left:2px;top:2px;width:20px;height:20px;background:#fff;border-radius:50%;transition:transform .2s;box-shadow:0 1px 3px rgba(0,0,0,.15)}
.toggle-switch input:checked+.toggle-track{background:var(--p1)}
.toggle-switch input:checked+.toggle-track::after{transform:translateX(20px)}
.toggle-label{font-size:13px;color:var(--txt)}
/* Exclude chips */
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:8px;background:rgba(248,113,113,.08);color:#ef4444;font-size:12px;font-weight:500}
.chip-x{cursor:pointer;opacity:.6;font-size:14px;line-height:1}.chip-x:hover{opacity:1}
.chip-input{display:flex;gap:6px;margin-bottom:16px}
.chip-input input{flex:1;height:38px;border:1px solid var(--line);background:var(--input-bg);border-radius:10px;padding:0 12px;font-size:13px;font-family:inherit;color:var(--txt);outline:none}
.chip-input button{height:38px;padding:0 14px;border:none;border-radius:10px;background:var(--p1);color:#fff;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit}
/* Profile modal */
.prof-md{font-size:14px;line-height:1.7;color:var(--txt);white-space:pre-wrap;word-break:break-word}
.prof-md b{color:var(--p1)}
.prof-md hr{border:none;border-top:1px solid var(--line);margin:12px 0}
.settings-panel{padding:24px}
.settings-panel h2{font-size:17px;font-weight:700;margin-bottom:18px}
.settings-panel label{display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.3px}
.settings-panel input,.settings-panel select{width:100%;height:42px;border:1px solid var(--line);background:var(--input-bg);border-radius:12px;padding:0 12px;font-size:13px;font-family:inherit;color:var(--txt);outline:none;transition:border-color .2s;margin-bottom:12px}
.settings-panel input:focus,.settings-panel select:focus{border-color:var(--p1)}
.settings-panel select{cursor:pointer}
.btn-fetch-models{display:flex;align-items:center;gap:6px;height:42px;padding:0 14px;border:1px solid var(--line);background:var(--input-bg);border-radius:12px;font-size:12px;font-weight:500;color:var(--muted);cursor:pointer;font-family:inherit;transition:all .2s;flex-shrink:0;white-space:nowrap}
.btn-fetch-models:hover:not(:disabled){border-color:var(--p1);color:var(--p1);background:rgba(123,97,255,.06)}
.btn-fetch-models:disabled{opacity:.5;cursor:not-allowed}
.btn-fetch-models.loading svg{animation:spin 1s linear infinite}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.btn-save{height:46px;border:none;border-radius:14px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font-size:14px;font-weight:600;font-family:inherit;cursor:pointer;transition:all .2s;margin-top:6px;width:100%;box-shadow:0 4px 14px rgba(123,97,255,.2)}
.btn-save:hover{box-shadow:0 6px 20px rgba(123,97,255,.3);transform:translateY(-1px)}
.btn-save:active{transform:translateY(0)}
.save-fb{font-size:12px;color:#3ccf6e;margin-top:8px;text-align:center;min-height:18px}
.modal-mask{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:100;justify-content:center;align-items:center;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.modal-mask.open{display:flex}
.modal-box{background:var(--modal-bg);border-radius:22px;padding:28px;width:500px;max-width:92vw;box-shadow:0 24px 64px rgba(0,0,0,.18)}
.modal-box h3{font-size:18px;font-weight:700;margin-bottom:16px}
.modal-box label{color:var(--muted);font-size:12px;display:block;margin-bottom:5px;font-weight:500}
.modal-box input{width:100%;padding:10px 14px;border-radius:10px;background:var(--input-bg);color:var(--txt);border:1px solid var(--line);font-size:13px;font-family:inherit;outline:none;transition:border-color .2s}
.modal-box input:focus{border-color:var(--p1)}
.modal-foot{display:flex;gap:8px;justify-content:flex-end;margin-top:20px}
.btn-cancel{background:var(--cancel-bg);color:#6b7280;padding:10px 20px;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:500;font-family:inherit}
.btn-cancel:hover{background:#ebebef}
.btn-ok{background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;padding:10px 20px;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit}
.btn-ok:hover{box-shadow:0 4px 14px rgba(123,97,255,.25)}
.suggest-card{background:var(--suggest-bg);border:1px solid var(--suggest-border);border-radius:14px;padding:16px;margin-bottom:10px}
.suggest-card h4{font-size:12px;font-weight:600;color:var(--p1);margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}
.analysis-row{font-size:13px;color:#374151;margin-bottom:6px;line-height:1.6}
.analysis-row b{color:var(--p1)}
.analysis-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:4px}
.analysis-tag{background:var(--tag-bg);color:var(--p1);font-size:11px;padding:3px 10px;border-radius:6px}
.suggest-item{background:var(--suggest-bg);border:1px solid var(--suggest-border);border-radius:12px;padding:16px;margin-bottom:8px}
.suggest-label{color:var(--p1);font-size:11px;font-weight:600;margin-bottom:5px}
.suggest-text{color:var(--txt);font-size:14px;margin-bottom:4px}
.suggest-reason{color:var(--muted);font-size:12px}
.spin{display:inline-block;width:18px;height:18px;border:2px solid rgba(123,97,255,.2);border-top-color:var(--p1);border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}
.footer{text-align:center;color:#B0B8C9;font-size:11px;margin-top:32px}
@media(max-width:1100px){.layout{grid-template-columns:1fr!important}.settings-col,.contacts-col{display:none}}
@media(max-width:768px){.stats{grid-template-columns:1fr;}.top-title{font-size:24px}}
</style>
</head>
<body>
<div class="wrap">

<div class="top">
  <div class="brand">
    <div class="logo"></div>
    <div><div class="top-title">微信监控面板</div><div class="top-sub">智能分析 · 档案管理</div></div>
  </div>
  <div style="display:flex;gap:10px;align-items:center">
    <div class="gear glass" title="刷新面板" onclick="refresh()" style="width:52px;height:52px"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></div>
    <div class="gear glass" id="themeToggle" title="切换主题" onclick="toggleTheme()" style="font-size:16px">
      <svg id="iconMoon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      <svg id="iconSun" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
    </div>
  </div>
</div>

<div class="glass status-bar">
  <div class="status-left">
    <div class="dot" id="statusDot"></div>
    <span class="status-text" id="statusText">加载中...</span>
    <span class="status-sub" id="statusSub"></span>
  </div>
  <button class="btn" id="toggleBtn" onclick="toggleMonitor()">加载中...</button>
</div>

<div class="layout">

<div class="contacts-col" id="contactsCol">
  <div class="contacts-toggle" onclick="toggleContacts()" title="展开/收起联系人">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
    <span>联系人</span>
  </div>
  <div class="glass panel">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px"><h2 style="margin:0">监控联系人</h2><button class="collapse-btn" onclick="toggleContacts()" title="收起联系人"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg></button></div>
  <input class="search" id="contactSearch" type="text" placeholder="搜索联系人..." oninput="renderProfilesWithFilter()">
  <div class="contact-list" id="profileList"><div class="empty">加载中...</div></div>
  <button class="btn-add" onclick="showAddModal()">+ 添加联系人</button>
  </div>
</div>

<div class="main-col">
  <div class="stats">
    <div class="glass stat">
      <div class="stat-title">监控人数</div>
      <div class="stat-big" id="totalProfiles">-</div>
    </div>
    <div class="glass stat">
      <div class="stat-title">今日更新</div>
      <div class="stat-big" id="totalUpdates">-</div>
    </div>
    <div class="glass stat">
      <div class="stat-title">运行时长</div>
      <div class="stat-big" id="runningTime">-</div>
    </div>
  </div>

  <div class="glass poll">
    <h3>轮询间隔设置</h3>
    <div class="poll-sub">AI 自动分析消息并更新档案</div>
    <div class="interval-row">
      <input class="interval-input" id="intervalInput" type="number" min="15" value="30" onchange="setIntervalVal()" onkeydown="if(event.key==='Enter')setIntervalVal()">
      <span class="interval-unit">秒（最小 15）</span>
    </div>
  </div>

  <div class="glass logs-card">
    <h3>最近动态</h3>
    <div class="log-scroll" id="logArea"><div class="empty">暂无动态</div></div>
  </div>
</div>

<div class="settings-col" id="settingsCol">
  <div class="settings-toggle" onclick="toggleSettings()" title="展开/收起设置">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
    <span>设置</span>
  </div>
  <div class="glass settings-panel">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px"><h2 style="margin:0">设置中心</h2><button class="collapse-btn" onclick="toggleSettings()" title="收起设置"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button></div>
    <label>页面缩放</label>
    <div class="zoom-row">
      <input type="range" min="50" max="150" value="100" id="zoomSlider" oninput='document.getElementById("zoomVal").textContent=this.value+"%"' onmouseup="setZoom(this.value)" ontouchend="setZoom(this.value)">
      <span class="zoom-val" id="zoomVal">100%</span>
    </div>
    <label>人物档案目录</label>
    <input id="cfgProfilesDir" type="text" placeholder="从 Finder 拖拽文件夹" ondragover="event.preventDefault()" ondrop="event.preventDefault();const f=event.dataTransfer.files[0];if(f)this.value=f.path||f.name;">
    <label>LLM 接口模式</label>
    <select id="cfgLlmMode"><option value="openai">OpenAI 兼容</option><option value="anthropic">Anthropic 格式</option></select>
    <label>API 密钥</label>
    <input id="cfgApiKey" type="password" placeholder="直接填写密钥">
    <label>API 地址</label>
    <input id="cfgApiBase" type="text">
    <label>模型名</label>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <select id="cfgModel" style="flex:1"><option value="">— 请选择 —</option></select>
      <button type="button" class="btn-fetch-models" id="fetchModelsBtn" onclick="fetchModels()" title="从当前 API 地址拉取模型列表">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        <span>获取列表</span>
      </button>
    </div>
    <button class="btn-save" id="saveBtn" onclick="saveSettings()">保存配置</button>
    <div class="save-fb" id="saveFeedback"></div>
    <hr style="border:none;border-top:1px solid var(--line);margin:18px 0">
    <label>桌面通知</label>
    <div class="toggle-row">
      <label class="toggle-switch"><input type="checkbox" id="notifToggle" onchange="toggleNotif()"><span class="toggle-track"></span></label>
      <span class="toggle-label">新消息时推送系统通知</span>
    </div>
    <label>排除会话</label>
    <div class="chips" id="excludeChips"></div>
    <div class="chip-input">
      <input id="excludeInput" placeholder="输入会话名..." onkeydown="if(event.key==='Enter')addExclude()">
      <button onclick="addExclude()">添加</button>
    </div>
  </div>
</div>

</div>

<div class="footer">微信监控守护 · 智能分析 · 档案更新</div>
</div>

<div class="modal-mask" id="addModal">
  <div class="modal-box">
    <h3>添加监控联系人</h3>
    <p style="color:var(--muted);font-size:13px;margin-bottom:14px;">输入对方的微信备注名即可</p>
    <input id="contactInput" type="text" placeholder="输入微信备注名..." onkeydown="if(event.key==='Enter')addContact()" oninput="document.getElementById('confirmAddBtn').disabled=!this.value.trim()">
    <div class="modal-foot">
      <button class="btn-cancel" onclick="hideAddModal()">取消</button>
      <button class="btn-ok" id="confirmAddBtn" onclick="addContact()" disabled>添加</button>
    </div>
  </div>
</div>

<div class="modal-mask" id="profileModal"><div class="modal-box" style="width:580px;max-width:92vw;max-height:80vh;display:flex;flex-direction:column"><h3 id="profileTitle">档案</h3><div id="profileContent" style="flex:1;overflow-y:auto;max-height:60vh;"><div class="empty">加载中...</div></div><div class="modal-foot" style="margin-top:12px;"><button class="btn-cancel" onclick="document.getElementById('profileModal').classList.remove('open')">关闭</button></div></div></div>

<div class="modal-mask" id="suggestModal">
  <div class="modal-box" style="width:540px;max-width:92vw;">
    <h3 id="suggestTitle">建议回复</h3>
    <div id="suggestContent" style="max-height:500px;overflow-y:auto;"><div class="empty">加载中...</div></div>
    <div class="modal-foot" style="margin-top:12px;">
      <button class="btn-cancel" onclick="hideSuggestModal()">关闭</button>
    </div>
  </div>
</div>

<script>
const API = "";
let AUTH_TOKEN = "";
let contactsData = {};
let _ready = false;
const _readyWaiters = [];

(async function() {
  try {
    const resp = await fetch(API + "/api/public-token");
    const data = await resp.json();
    AUTH_TOKEN = data.token || "";
  } catch(e) {}
  _ready = true;
  _readyWaiters.splice(0).forEach(function(fn){ try { fn(); } catch(e) {} });
  if (typeof refresh === "function") refresh();
})();

function whenReady(fn) {
  if (_ready) fn();
  else _readyWaiters.push(fn);
}

function authHeaders() {
  return AUTH_TOKEN ? {"Authorization": "Bearer " + AUTH_TOKEN} : {};
}

async function fetchStatus() {
  const resp = await fetch(API + "/api/status", { headers: authHeaders() });
  return await resp.json();
}

async function toggleMonitor() {
  const btn = document.getElementById("toggleBtn");
  btn.disabled = true;
  const isRunning = btn.dataset.running === "true";
  await fetch(API + "/api/" + (isRunning ? "stop" : "start"), { method: "POST", headers: authHeaders() });
  btn.disabled = false;
  refresh();
}

function showAddModal() {
  document.getElementById("addModal").classList.add("open");
  document.getElementById("contactInput").value = "";
  document.getElementById("contactInput").focus();
  document.getElementById("confirmAddBtn").disabled = true;
}
function hideAddModal() { document.getElementById("addModal").classList.remove("open"); }

async function addContact() {
  const chat = document.getElementById("contactInput").value.trim();
  if (!chat) return;
  const btn = document.getElementById("confirmAddBtn");
  btn.disabled = true; btn.textContent = "添加中...";
  try {
    await fetch(API + "/api/add-contact", {
      method: "POST",
      headers: {"Content-Type": "application/json", ...authHeaders()},
      body: JSON.stringify({chat})
    });
    contactsData[chat] = "";
    hideAddModal(); refresh();
  } catch(e) { alert("添加失败"); }
  btn.textContent = "添加";
}

async function removeContact(chat) {
  if (!confirm("取消监控「" + chat + "」？")) return;
  try {
    await fetch(API + "/api/remove-contact", {
      method: "POST",
      headers: {"Content-Type": "application/json", ...authHeaders()},
      body: JSON.stringify({chat})
    });
    delete contactsData[chat]; refresh();
  } catch(e) { alert("取消失败"); }
}

function renderLogs(logs) {
  const area = document.getElementById("logArea");
  if (!logs || !logs.length) { area.innerHTML = '<div class="empty">暂无动态</div>'; return; }
  const atBot = area.scrollTop + area.clientHeight >= area.scrollHeight - 30;
  area.innerHTML = logs.map(function(l) {
    return '<div class="log"><span class="log-time">' + l.time + '</span><span class="log-level ' + l.level + '">' + l.level + '</span><span class="log-msg">' + escapeHtml(l.msg) + '</span></div>';
  }).join("");
  if (atBot) area.scrollTop = area.scrollHeight;
}

function _profColor(name) {
  var h = 0;
  for (var i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  var hue = Math.abs(h) % 360;
  return "linear-gradient(135deg,hsl(" + hue + ",65%,62%),hsl(" + ((hue + 30) % 360) + ",55%,55%))";
}

function renderProfilesWithFilter() {
  var q = (document.getElementById("contactSearch").value || "").toLowerCase();
  var el = document.getElementById("profileList");
  var contacts = window._lastProfileData && window._lastProfileData.monitored_contacts || [];
  var profiles = window._lastProfileData && window._lastProfileData.profile_list || [];
  var aliasMap = window._lastProfileData && window._lastProfileData.alias_map || {};
  var filtered = q ? contacts.filter(function(c) { return c.toLowerCase().indexOf(q) !== -1; }) : contacts;
  if (!filtered.length) { el.innerHTML = '<div class="empty">' + (q ? '未找到匹配的联系人' : '暂无监控联系人') + '</div>'; return; }
  el.innerHTML = filtered.map(function(c) {
    var has = profiles.indexOf(c) !== -1;
    var aliases = aliasMap[c] || [];
    var col = _profColor(c);
    var aliasHtml = aliases.length ? '<span class="badge badge-alias">' + escapeHtml(aliases[0] + (aliases.length > 1 ? " +" + (aliases.length - 1) : "")) + '</span>' : "";
    return '<div class="contact"><div class="contact-info">'
      + '<div class="avatar" style="background:' + col + '">' + escapeHtml(c.charAt(0)) + '</div>'
      + '<div><div class="contact-name" style="cursor:pointer" onclick="showProfile(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')">' + escapeHtml(c) + '</div>'
      + '<div class="contact-meta">'
      + (has ? '<span class="badge badge-profile">有档案</span>' : '<span class="badge badge-manual">手动</span>')
      + aliasHtml + '</div></div></div>'
      + '<div class="contact-acts">'
      + '<button class="btn-sm btn-analyze" onclick="suggestReply(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\',\'' + escapeHtml(contactsData[c] || "").replace(/'/g, "\\'") + '\')">💬 分析</button>'
      + '<button class="btn-rm" onclick="removeContact(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')" title="取消监控">✕</button>'
      + '</div></div>';
  }).join("");
}

function escapeHtml(t) { var d = document.createElement("div"); d.textContent = t; return d.innerHTML; }

async function suggestReply(chat, username) {
  document.getElementById("suggestTitle").textContent = chat + " — 对话分析";
  var sc = document.getElementById("suggestContent");
  sc.innerHTML = '<div class="empty" style="padding:40px 0;"><div class="spin"></div>分析中<span id="sgElapsed"></span>...</div>';
  var t0 = Date.now();
  var timer = setInterval(function(){
    var el = document.getElementById("sgElapsed");
    if (el) el.textContent = "（" + Math.floor((Date.now()-t0)/1000) + "s）";
  }, 500);
  document.getElementById("suggestModal").classList.add("open");
  try {
    var controller = new AbortController();
    var tmo = setTimeout(function(){ controller.abort(); }, 60000);
    var resp = await fetch(API + "/api/suggest-reply?chat=" + encodeURIComponent(chat) + "&username=" + encodeURIComponent(username), { headers: authHeaders(), signal: controller.signal });
    clearTimeout(tmo); clearInterval(timer);
    var data = await resp.json();
    var html = "";
    if (data.analysis && data.analysis.summary) {
      html += '<div class="suggest-card"><h4>对话分析</h4>';
      html += '<div class="analysis-row"><b>主题：</b>' + escapeHtml(data.analysis.summary) + '</div>';
      if (data.analysis.tone) html += '<div class="analysis-row"><b>语气：</b>' + escapeHtml(data.analysis.tone) + '</div>';
      if (data.analysis.key_points && data.analysis.key_points.length) {
        html += '<div class="analysis-row"><b>关键信息：</b></div><div class="analysis-tags">';
        data.analysis.key_points.forEach(function(p) { html += '<span class="analysis-tag">' + escapeHtml(p) + '</span>'; });
        html += '</div>';
      }
      html += '</div>';
    }
    if (!data.suggestions || !data.suggestions.length) {
      if (!html) html = '<div class="empty">暂无聊天记录</div>';
    } else {
      html += data.suggestions.map(function(s, i) {
        return '<div class="suggest-item"><div class="suggest-label">建议 ' + (i+1) + '</div>'
          + '<div class="suggest-text">' + escapeHtml(s.reply) + '</div>'
          + '<div class="suggest-reason">' + escapeHtml(s.reason || "") + '</div></div>';
      }).join("");
    }
    document.getElementById("suggestContent").innerHTML = html;
  } catch(e) {
    clearInterval(timer);
    var msg = e.name === "AbortError" ? "分析超时（60s），请稍后重试" : "加载失败";
    document.getElementById("suggestContent").innerHTML = '<div class="empty" style="color:#ef4444;">' + msg + '</div>';
  }
}
function hideSuggestModal() { document.getElementById("suggestModal").classList.remove("open"); }

async function setIntervalVal() {
  var el = document.getElementById("intervalInput");
  var v = parseInt(el.value) || 30; if (v < 15) { v = 15; el.value = 15; }
  await fetch(API + "/api/set-interval", { method: "POST", headers: {"Content-Type":"application/json", ...authHeaders()}, body: JSON.stringify({interval:v}) });
}

async function loadConfig() {
  try {
    var r = await fetch(API+"/api/config",{headers:authHeaders()});
    var c = await r.json();
    document.getElementById("cfgProfilesDir").value = c.profiles_dir||"";
    document.getElementById("cfgLlmMode").value = c.llm&&c.llm.mode||"openai";
    document.getElementById("cfgApiKey").value = c.llm&&c.llm.api_key||"";
    document.getElementById("cfgApiBase").value = c.llm&&c.llm.api_base||"";
    var mname=(c.llm&&c.llm.model)||"";
  var msel=document.getElementById("cfgModel");
  if(mname&&!Array.from(msel.options).some(function(o){return o.value===mname})){
    var opt=document.createElement("option");opt.value=mname;opt.textContent=mname;msel.insertBefore(opt,msel.firstChild.nextSibling);
  }
  msel.value=mname;
  } catch(e) {}
}

async function saveSettings() {
  var btn = document.getElementById("saveBtn");
  var fb = document.getElementById("saveFeedback");
  btn.disabled = true; btn.textContent = "保存中...";
  try {
    await fetch(API+"/api/config",{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},
      body:JSON.stringify({profiles_dir:document.getElementById("cfgProfilesDir").value.trim(),llm:{
        mode:document.getElementById("cfgLlmMode").value,api_key:document.getElementById("cfgApiKey").value,
        api_base:document.getElementById("cfgApiBase").value.trim(),model:document.getElementById("cfgModel").value.trim()}})});
    fb.textContent = "✓ 已保存";
    setTimeout(function(){ fb.textContent = ""; }, 3000);
    refresh();
  } catch(e) { fb.textContent = "保存失败"; setTimeout(function(){ fb.textContent = ""; }, 3000); }
  btn.disabled = false; btn.textContent = "保存配置";
}

async function refresh() {
  try {
    var d = await fetchStatus();
    var dot = document.getElementById("statusDot");
    var txt = document.getElementById("statusText");
    var btn = document.getElementById("toggleBtn");
    var sub = document.getElementById("statusSub");
    if (d.running) {
      dot.className="dot on"; txt.textContent="运行中"; sub.textContent="监控服务正常运行";
      btn.textContent="停止监控"; btn.className="btn btn-stop"; btn.dataset.running="true";
    } else {
      dot.className="dot off"; txt.textContent="已停止"; sub.textContent="点击启动监控";
      btn.textContent="启动监控"; btn.className="btn btn-start"; btn.dataset.running="false";
    }
    document.getElementById("totalProfiles").textContent = d.monitored_count || 0;
    document.getElementById("totalUpdates").textContent = d.today_updates || 0;
    document.getElementById("runningTime").textContent = d.running_time || "0m";
    document.getElementById("intervalInput").value = d.poll_interval || 30;
    renderLogs(d.logs);
    window._lastProfileData = d;
    renderProfilesWithFilter();
  } catch(e) {
    document.getElementById("statusDot").className="dot off";
    document.getElementById("statusText").textContent="连接失败";
    document.getElementById("statusSub").textContent="请检查服务是否运行";
  }
}

var _evtSrc=null,_refTmr=null,_logRefreshTmr=null;
function connectSSE() {
  if(_evtSrc){try{_evtSrc.close();}catch(e){}}
  _evtSrc=new EventSource(API+"/api/events");
  _evtSrc.onmessage=function(e){try{var v=JSON.parse(e.data);
    if(v.type==="new_message"){
      refresh();
      if(localStorage.getItem("notif")==="1" && "Notification" in window && Notification.permission==="granted"){
        new Notification("微信新消息",{body:(v.chat||"")+" 发来新消息"});
      }
    } else if(v.type==="connected") refresh();
    else if(v.type==="log_update"){if(_logRefreshTmr)clearTimeout(_logRefreshTmr);_logRefreshTmr=setTimeout(refresh,1500);}
  }catch(err){}};
  _evtSrc.onerror=function(){if(_evtSrc){try{_evtSrc.close();}catch(e){}}_evtSrc=null;if(_refTmr)clearTimeout(_refTmr);_refTmr=setTimeout(connectSSE,5000);};
}

whenReady(function(){ refresh(); loadConfig(); loadExclude(); });
whenReady(function(){ connectSSE(); });
whenReady(function(){ setInterval(refresh, 15000); });

/* Settings toggle */
function toggleSettings(){
  var col=document.getElementById("settingsCol");
  var collapsed=col.classList.toggle("collapsed");
  document.documentElement.style.setProperty("--settings-w",collapsed?"48px":"320px");
  localStorage.setItem("settingsCollapsed",collapsed?"1":"0");
}

/* === Fetch model list === */
async function fetchModels(){
  var btn=document.getElementById("fetchModelsBtn");
  var sel=document.getElementById("cfgModel");
  var currentVal=sel.value;
  btn.classList.add("loading");
  btn.disabled=true;
  try{
    var llm={
      mode:document.getElementById("cfgLlmMode").value,
      api_key:document.getElementById("cfgApiKey").value.trim(),
      api_base:document.getElementById("cfgApiBase").value.trim()
    };
    var r=await fetch(API+"/api/models",{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify({llm:llm})});
    var d=await r.json();
    if(!r.ok||d.error){alert("获取失败："+(d.error||r.statusText));return;}
    var models=d.models||[];
    if(!models.length){alert("接口返回的模型列表为空");return;}
    sel.innerHTML='<option value="">— 请选择 —</option>'+models.map(function(m){return '<option value="'+escapeHtml(m)+'">'+escapeHtml(m)+'</option>'}).join("");
    if(currentVal&&models.indexOf(currentVal)>=0) sel.value=currentVal;
    btn.querySelector("span").textContent="已获取 "+models.length;
    setTimeout(function(){btn.querySelector("span").textContent="获取列表"},3000);
  }catch(e){
    alert("请求出错："+e.message);
  }finally{
    btn.classList.remove("loading");
    btn.disabled=false;
  }
}
function toggleContacts(){
  var col=document.getElementById("contactsCol");
  var collapsed=col.classList.toggle("collapsed");
  document.documentElement.style.setProperty("--contacts-w",collapsed?"48px":"370px");
  localStorage.setItem("contactsCollapsed",collapsed?"1":"0");
}
(function(){
  if(localStorage.getItem("settingsCollapsed")==="1"){
    document.getElementById("settingsCol").classList.add("collapsed");
    document.documentElement.style.setProperty("--settings-w","48px");
  }
  if(localStorage.getItem("contactsCollapsed")==="1"){
    document.getElementById("contactsCol").classList.add("collapsed");
    document.documentElement.style.setProperty("--contacts-w","48px");
  }
})();

/* Page zoom */
function setZoom(v){
  document.body.style.zoom=v/100;
  document.getElementById("zoomVal").textContent=v+"%";
  localStorage.setItem("zoom",v);
}
(function(){
  var z=localStorage.getItem("zoom")||"100";
  document.body.style.zoom=Number(z)/100;
  var sl=document.getElementById("zoomSlider");
  var vl=document.getElementById("zoomVal");
  if(sl){sl.value=z;vl.textContent=z+"%";}
})();


/* === Notifications === */
function toggleNotif(){
  var on=document.getElementById("notifToggle").checked;
  localStorage.setItem("notif",on?"1":"0");
  if(on && "Notification" in window && Notification.permission==="default") Notification.requestPermission();
}
(function(){if(localStorage.getItem("notif")==="1"){var t=document.getElementById("notifToggle");if(t)t.checked=true;}})();

/* === Exclude Chats === */
var _excludeList=[];
async function loadExclude(){
  try{var r=await fetch(API+"/api/exclude-chats",{headers:authHeaders()});var d=await r.json();_excludeList=d.exclude_chats||[];renderExclude();}catch(e){}
}
function renderExclude(){
  var el=document.getElementById("excludeChips");
  if(!_excludeList.length){el.innerHTML="<span style='font-size:12px;color:var(--muted)'>无</span>";return;}
  el.innerHTML=_excludeList.map(function(c){return '<span class="chip">'+escapeHtml(c)+' <span class="chip-x" onclick="removeExclude(\''+escapeHtml(c).replace(/'/g,"\\'")+'\')">✕</span></span>';}).join("");
}
async function addExclude(){
  var inp=document.getElementById("excludeInput");var v=inp.value.trim();if(!v)return;
  if(_excludeList.indexOf(v)===-1)_excludeList.push(v);
  inp.value="";
  await fetch(API+"/api/exclude-chats",{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify({exclude_chats:_excludeList})});
  renderExclude();
}
async function removeExclude(c){
  _excludeList=_excludeList.filter(function(x){return x!==c;});
  await fetch(API+"/api/exclude-chats",{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify({exclude_chats:_excludeList})});
  renderExclude();
}

/* === Profile Preview === */
async function showProfile(name){
  console.log("showProfile called:", name);
  document.getElementById("profileTitle").textContent=name+" — 人物档案";
  var el=document.getElementById("profileContent");
  el.innerHTML='<div class="empty">加载中...</div>';
  document.getElementById("profileModal").classList.add("open");
  try{
    var r=await fetch(API+"/api/profile?name="+encodeURIComponent(name),{headers:authHeaders()});
    console.log("profile response:", r.status);
    var d=await r.json();
    if(!d.exists){el.innerHTML='<div class="empty">未找到「'+escapeHtml(name)+'」的档案</div>';return;}
    var md=d.content||"";
    md=md.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    md=md.replace(/^### (.+)$/gm,"<h3>$1</h3>").replace(/^## (.+)$/gm,"<h3>$1</h3>").replace(/^# (.+)$/gm,"<h1>$1</h1>");
    md=md.replace(/\*\*(.+?)\*\*/g,"<b>$1</b>");
    md=md.replace(/^---$/gm,"<hr>");
    el.innerHTML='<div class="prof-md">'+md+'</div>';
  }catch(e){el.innerHTML='<div class="empty">加载失败</div>';}
}


function toggleTheme() {
  var isDark = document.documentElement.getAttribute("data-theme") === "dark";
  document.documentElement.setAttribute("data-theme", isDark ? "light" : "dark");
  localStorage.setItem("theme", isDark ? "light" : "dark");
  document.getElementById("iconMoon").style.display = isDark ? "" : "none";
  document.getElementById("iconSun").style.display = isDark ? "none" : "";
}
(function(){
  var saved = localStorage.getItem("theme");
  var prefer = window.matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light";
  var theme = saved || prefer;
  document.documentElement.setAttribute("data-theme", theme);
  if (theme === "dark") {
    document.getElementById("iconMoon").style.display = "none";
    document.getElementById("iconSun").style.display = "";
  }
})();
</script>
</body>
</html>"""


# ===== 17. Entry Points =====
def main():
    init_profiles()
    refresh_all_contacts()
    log(f"📡 监控面板启动，{len(profile_names)} 个档案，{len(all_contacts_cache)} 个微信会话")
    log(f"🔗 控制面板: http://localhost:{PORT}")
    log(f"🔑 API Token: {API_TOKEN}")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), MonitorHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    log("⏸ 面板已就绪，5秒后自动启动监控")

    def _shutdown(signum, frame):
        log(f"收到信号 {signum}，正在关闭...")
        if monitor_running:
            stop_monitor()
        server.shutdown()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    def _auto_start():
        time.sleep(1)
        if not monitor_running:
            start_monitor()
    threading.Thread(target=_auto_start, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("退出")
        if monitor_running:
            stop_monitor()

if __name__ == "__main__":
    main()
