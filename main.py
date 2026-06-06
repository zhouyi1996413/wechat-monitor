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
WEBCOMMAND_LOCK_TIMEOUT = 30      # 单次 wechat-cli 锁超时（秒），耐心等主轮询/缓存刷新
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

def _safe_path(base, *parts):
    """安全路径拼接：解析后必须仍在 base 下，否则拒绝"""
    base_real = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_real, *parts))
    if target != base_real and not target.startswith(base_real + os.sep):
        raise ValueError(f"路径越界: {target}")
    return target


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
            print(f"[INFO] 📋 已生成默认配置 {CONFIG_FILE}，请在 Web 面板的「设置中心」中填写")
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
manual_accounts = {}           # 用户手动添加的账号 {contact_name: [{username, chat, label}]}
account_labels = {}              # 给自动/alias 账号加的显示名 {contact_name: {username: label}}
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
            with _state_lock:
                ma = data.get("manual_accounts", {})
                manual_accounts.clear()
                manual_accounts.update(ma)
                al = data.get("account_labels", {})
                account_labels.clear()
                account_labels.update(al)
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
        data["manual_accounts"] = {k: list(v) for k, v in manual_accounts.items()}
        data["account_labels"] = {k: dict(v) for k, v in account_labels.items()}
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
            ["wechat-cli", "sessions", "--limit", "500"], timeout=15, lock_timeout=5
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
    try:
        filepath = Path(_safe_path(str(PROFILE_DIR), f"{chat_name}.md"))
    except ValueError as e:
        log(f"拒绝创建档案（路径越界）: {chat_name} -> {e}", "warn")
        return None
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
    # 优先读 start.txt，其次从 state.json 兜底
    start_ts = None
    start_file = os.path.join(SCRIPT_DIR, "start.txt")
    if os.path.exists(start_file):
        try:
            with open(start_file) as _f:
                start_ts = float(_f.read().strip())
        except Exception:
            pass
    if start_ts is None:
        try:
            with open(STATE_FILE) as _f:
                _st = json.load(_f)
                start_ts = _st.get("last_poll_time")
        except Exception:
            pass
    if start_ts is None:
        # 最后兜底：进程存活就显示"运行中"
        return "运行中"
    elapsed = int(time.time() - start_ts)
    h = elapsed // 3600
    m = (elapsed % 3600) // 60
    s = elapsed % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


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
            from collections import defaultdict
            _accts = defaultdict(dict)
            _hidden_by_contact = {}  # chat_name -> {username: {chat, is_primary}}
            _SKIP_USERS = {"qqmail", "brandservicesessionholder", "brandsessionholder"}
            _uname_to_chat = {c.get("username",""): c.get("chat","") for c in all_contacts_cache if c.get("username")}
            for _chat_name in monitored_contacts:
                if len(_chat_name) < 2:
                    continue
                # 1) 缓存里的 chat 前缀/精确匹配
                for _c in all_contacts_cache:
                    _other = _c.get("chat", "")
                    _uname = _c.get("username", "")
                    if not _uname or _c.get("is_group"):
                        continue
                    if str(_uname).startswith("gh_") or _uname in _SKIP_USERS:
                        continue
                    if _other == _chat_name or _other.startswith(_chat_name):
                        if _uname not in _accts[_chat_name]:
                            _accts[_chat_name][_uname] = {"chat": _other, "is_primary": _other == _chat_name}
                # 2) 档案 alias 兜底（解决"档案里写了小号 wxid 但 sessions 缓存里没拉到"的问题）
                _md = identifier_to_profile.get(_chat_name)
                if _md and _md in profile_identifiers:
                    for _alias in profile_identifiers[_md]:
                        if not _alias or _alias == _chat_name:
                            continue
                        # _alias 可能是 username（wxid_xxx / your_username）或小号 chat 名
                        if _alias in _uname_to_chat:
                            _chat = _uname_to_chat[_alias]
                            if _alias not in _accts[_chat_name]:
                                _accts[_chat_name][_alias] = {"chat": _chat, "is_primary": _chat == _chat_name}
                        elif str(_alias).startswith("wxid_") or (re.match(r'^[A-Za-z][A-Za-z0-9_]{5,}$', str(_alias)) and len(str(_alias)) >= 6):
                            # 像 username 但缓存里没找到，依然显示（标记非主号）
                            if _alias not in _accts[_chat_name]:
                                _accts[_chat_name][_alias] = {"chat": _alias, "is_primary": False}
                # 3) 用户手动添加的账号（最高优先级，永远显示）
                for _entry in manual_accounts.get(_chat_name, []):
                    _u = _entry.get("username", "")
                    if not _u:
                        continue
                    if _entry.get("source") == "hidden":
                        _hidden_by_contact.setdefault(_chat_name, set()).add(_u)
                        continue
                    if _u not in _accts[_chat_name]:
                        _accts[_chat_name][_u] = {
                            "chat": _entry.get("chat", _u),
                            "is_primary": _entry.get("is_primary", False),
                        }
            contact_accounts = {k: [{"username": u, "chat": v["chat"], "is_primary": v["is_primary"], "label": account_labels.get(k, {}).get(u, "")} for u, v in vs.items() if u not in _hidden_by_contact.get(k, set())] for k, vs in _accts.items()}
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
                "contact_order": load_state().get("contact_order", []),
                "contact_accounts": contact_accounts,
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
                # 防止路径穿越：规范化后必须仍在 PROFILE_DIR 下
                try:
                    md_file = Path(_safe_path(str(PROFILE_DIR), pname + ".md"))
                except ValueError:
                    self._json({"name": pname, "content": "", "exists": False, "error": "invalid name"})
                    return
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


        elif path == "/api/contact_accounts":
            # GET  ?contact=xxx  -> 列出该联系人的所有账号（自动 + 手动合并）
            # POST {action:"add", contact, username, chat?, label?, is_primary?}
            #      {action:"remove", contact, username}
            #      {action:"set_primary", contact, username}
            #      {action:"rename", contact, username, label}
            if self.command == "GET":
                _name = qs.get("contact", [""])[0]
                if not _name:
                    self._json({"error": "contact required"}, 400)
                    return
                # 复用 /api/status 的聚合逻辑
                from collections import defaultdict
                _accts = defaultdict(dict)
                _SKIP = {"qqmail", "brandservicesessionholder", "brandsessionholder"}
                _uname_to_chat = {c.get("username", ""): c.get("chat", "") for c in all_contacts_cache if c.get("username")}
                for _c in all_contacts_cache:
                    _other = _c.get("chat", "")
                    _uname = _c.get("username", "")
                    if not _uname or _c.get("is_group"):
                        continue
                    if str(_uname).startswith("gh_") or _uname in _SKIP:
                        continue
                    if _other == _name or _other.startswith(_name):
                        _accts[_uname] = {"chat": _other, "source": "auto", "is_primary": _other == _name, "label": ""}
                _md = identifier_to_profile.get(_name)
                if _md and _md in profile_identifiers:
                    for _alias in profile_identifiers[_md]:
                        if not _alias or _alias == _name:
                            continue
                        if _alias in _uname_to_chat:
                            _chat = _uname_to_chat[_alias]
                            if _alias not in _accts:
                                _accts[_alias] = {"chat": _chat, "source": "alias", "is_primary": _chat == _name, "label": ""}
                        elif str(_alias).startswith("wxid_") or (re.match(r"^[A-Za-z][A-Za-z0-9_]{5,}$", str(_alias)) and len(str(_alias)) >= 6):
                            if _alias not in _accts:
                                _accts[_alias] = {"chat": _alias, "source": "alias", "is_primary": False, "label": ""}
                for _e in manual_accounts.get(_name, []):
                    _u = _e.get("username", "")
                    if _u and _u not in _accts:
                        _accts[_u] = {"chat": _e.get("chat", _u), "source": "manual", "is_primary": _e.get("is_primary", False), "label": _e.get("label", "")}
                # 合并独立保存的 label（给自动/alias 账号用的）
                _labels = account_labels.get(_name, {})
                for _u, _lbl in _labels.items():
                    if _u in _accts and _lbl:
                        _accts[_u]["label"] = _lbl
                # 过滤掉被"隐藏"的自动/alias 账号（manual_accounts 里 source="hidden" 的）
                _hidden_usernames = {e.get("username") for e in manual_accounts.get(_name, []) if e.get("source") == "hidden"}
                result = [{"username": u, "chat": v["chat"], "source": v["source"], "is_primary": v["is_primary"], "label": v["label"]} for u, v in _accts.items() if u not in _hidden_usernames]
                result.sort(key=lambda x: (not x["is_primary"], x["source"] == "auto", x["username"]))
                self._json({"contact": _name, "accounts": result})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}
            except Exception:
                self._json({"error": "invalid json"}, 400)
                return
            _contact = (body.get("contact") or "").strip()
            _username = (body.get("username") or "").strip()
            _action = body.get("action", "add")
            if not _contact or not _username:
                self._json({"error": "contact and username required"}, 400)
                return
            with _state_lock:
                _lst = list(manual_accounts.get(_contact, []))
                if _action == "add":
                    # 校验：如果是 username 格式（wxid_ / 纯英文数字下划线 >=6）直接接受
                    # 如果是 chat 名（中文 / 其他），尝试在缓存里查
                    _chat = body.get("chat", "").strip()
                    if not _chat:
                        # 尝试在缓存里通过 username 反查
                        for _c in all_contacts_cache:
                            if _c.get("username") == _username:
                                _chat = _c.get("chat", _username)
                                break
                        if not _chat:
                            _chat = _username
                    _is_primary = bool(body.get("is_primary", False))
                    _label = (body.get("label") or "").strip()
                    # 去重
                    _lst = [e for e in _lst if e.get("username") != _username]
                    _lst.append({"username": _username, "chat": _chat, "is_primary": _is_primary, "label": _label})
                    if _is_primary:
                        for e in _lst:
                            if e.get("username") != _username:
                                e["is_primary"] = False
                    manual_accounts[_contact] = _lst
                elif _action == "remove":
                    _lst = [e for e in _lst if e.get("username") != _username]
                    if _lst:
                        manual_accounts[_contact] = _lst
                    else:
                        manual_accounts.pop(_contact, None)
                elif _action == "set_primary":
                    for e in _lst:
                        e["is_primary"] = (e.get("username") == _username)
                    manual_accounts[_contact] = _lst
                elif _action == "set_label":
                    # 给任意账号设置显示名（独立于 manual_accounts）
                    with _state_lock:
                        if not _label.strip():
                            if _contact in account_labels and _username in account_labels[_contact]:
                                del account_labels[_contact][_username]
                                if not account_labels[_contact]:
                                    del account_labels[_contact]
                        else:
                            account_labels.setdefault(_contact, {})[_username] = _label.strip()
                    save_state()
                    self._json({"ok": True, "contact": _contact, "username": _username, "label": _label.strip()})
                    return
                elif _action == "hide":
                    # 隐藏一个 auto/alias 账号（用 source="hidden" 标记）
                    with _state_lock:
                        _lst = list(manual_accounts.get(_contact, []))
                        _lst = [e for e in _lst if e.get("username") != _username]
                        _lst.append({"username": _username, "source": "hidden", "is_primary": False, "label": ""})
                        manual_accounts[_contact] = _lst
                    save_state()
                    self._json({"ok": True, "contact": _contact, "username": _username, "hidden": True})
                    return
                elif _action == "unhide":
                    # 取消隐藏（移除 hidden 标记）
                    with _state_lock:
                        _lst = list(manual_accounts.get(_contact, []))
                        _lst = [e for e in _lst if not (e.get("username") == _username and e.get("source") == "hidden")]
                        if _lst:
                            manual_accounts[_contact] = _lst
                        else:
                            manual_accounts.pop(_contact, None)
                    save_state()
                    self._json({"ok": True, "contact": _contact, "username": _username, "hidden": False})
                    return
                elif _action == "rename":
                    for e in _lst:
                        if e.get("username") == _username:
                            e["label"] = (body.get("label") or "").strip()
                            break
                    manual_accounts[_contact] = _lst
                else:
                    self._json({"error": "unknown action"}, 400)
                    return
            save_state()
            self._json({"ok": True, "contact": _contact, "accounts": manual_accounts.get(_contact, [])})


        elif path == "/api/contacts":
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

            # 先用 username 解析出实际 chat 名（多账号时 chat 参数是父联系人名，不是子账号名）
            _actual_chat = chat
            if username:
                for _c in all_contacts_cache:
                    if _c.get("username") == username:
                        _actual_chat = _c.get("chat", chat)
                        break
                if _actual_chat == chat and username != chat:
                    with _state_lock:
                        if username in message_cache:
                            _actual_chat = username

            # 优先用缓存（用 _actual_chat 查，不是 URL 上的 chat）
            raw = []
            with _state_lock:
                if _actual_chat in message_cache:
                    raw = list(message_cache[_actual_chat])

            # 多账号合并：只在没有指定 username 时合并（分析整个联系人），
            # 指定了 username 时只拉该账号的消息（分析单个账号）
            if not username or username == chat:
                # 没指定 username：按父联系人合并所有别名账号
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
            else:
                # 指定了具体 username：上面 _actual_chat 已查过子账号缓存，不再合并父联系人
                pass

            # 缓存没有 → 从 wechat-cli 实时拉取（非阻塞拿锁，不卡界面）
            if not raw:
                raw = load_last_n_messages(username, limit=15)
                if not raw:
                    self._json({"chat": _actual_chat, "error": "暂无聊天记录", "suggestions": [], "analysis": None})
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

            # LLM 也用 _actual_chat（告诉 LLM 这是和哪个具体微信号的聊天）
            result = _get_suggestions_and_analysis(_actual_chat, chat_text)
            self._json({"chat": _actual_chat, "username": username, **result})

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

        elif path == "/api/contact_accounts":
            body = _read_body()
            if body is None:
                return
            _contact = (body.get("contact") or "").strip()
            _username = (body.get("username") or "").strip()
            _action = body.get("action", "add")
            if not _contact or not _username:
                self._json({"error": "contact and username required"}, 400)
                return
            if _action == "set_label":
                _label = (body.get("label") or "").strip()
                with _state_lock:
                    if not _label:
                        if _contact in account_labels and _username in account_labels[_contact]:
                            del account_labels[_contact][_username]
                            if not account_labels[_contact]:
                                del account_labels[_contact]
                    else:
                        account_labels.setdefault(_contact, {})[_username] = _label
                save_state()
                self._json({"ok": True, "contact": _contact, "username": _username, "label": _label})
                return
            if _action == "hide":
                with _state_lock:
                    _lst = list(manual_accounts.get(_contact, []))
                    _lst = [e for e in _lst if e.get("username") != _username]
                    _lst.append({"username": _username, "source": "hidden", "is_primary": False, "label": ""})
                    manual_accounts[_contact] = _lst
                save_state()
                self._json({"ok": True, "contact": _contact, "username": _username, "hidden": True})
                return
            if _action == "unhide":
                with _state_lock:
                    _lst = list(manual_accounts.get(_contact, []))
                    _lst = [e for e in _lst if not (e.get("username") == _username and e.get("source") == "hidden")]
                    if _lst:
                        manual_accounts[_contact] = _lst
                    else:
                        manual_accounts.pop(_contact, None)
                save_state()
                self._json({"ok": True, "contact": _contact, "username": _username, "hidden": False})
                return
            with _state_lock:
                _lst = list(manual_accounts.get(_contact, []))
                if _action == "add":
                    _chat = (body.get("chat") or "").strip()
                    if not _chat:
                        for _c in all_contacts_cache:
                            if _c.get("username") == _username:
                                _chat = _c.get("chat", _username)
                                break
                        if not _chat:
                            _chat = _username
                    _is_primary = bool(body.get("is_primary", False))
                    _label = (body.get("label") or "").strip()
                    _lst = [e for e in _lst if e.get("username") != _username]
                    _lst.append({"username": _username, "chat": _chat, "is_primary": _is_primary, "label": _label})
                    if _is_primary:
                        for e in _lst:
                            if e.get("username") != _username:
                                e["is_primary"] = False
                    manual_accounts[_contact] = _lst
                elif _action == "remove":
                    _lst = [e for e in _lst if e.get("username") != _username]
                    if _lst:
                        manual_accounts[_contact] = _lst
                    else:
                        manual_accounts.pop(_contact, None)
                elif _action == "set_primary":
                    for e in _lst:
                        e["is_primary"] = (e.get("username") == _username)
                    manual_accounts[_contact] = _lst
                elif _action == "rename":
                    for e in _lst:
                        if e.get("username") == _username:
                            e["label"] = (body.get("label") or "").strip()
                            break
                    manual_accounts[_contact] = _lst
                else:
                    self._json({"error": "unknown action"}, 400)
                    return
            save_state()
            self._json({"ok": True, "contact": _contact, "accounts": manual_accounts.get(_contact, [])})

        elif path == "/api/sub-order":
            body = _read_body()
            if body is None:
                return
            contact = (body.get("contact") or "").strip()
            order = body.get("order", [])
            if contact and isinstance(order, list):
                state = load_state()
                state.setdefault("sub_orders", {})[contact] = order
                save_state(state)
                self._json({"ok": True})
            else:
                self._json({"error": "contact and order required"}, 400)

        elif path == "/api/contact-order":
            body = _read_body()
            if body is None:
                return
            order = body.get("order", [])
            if isinstance(order, list):
                # 保存联系人顺序到 state.json
                state = load_state()
                state["contact_order"] = order
                save_state(state)
                self._json({"ok": True})
            else:
                self._json({"error": "order must be a list"}, 400)

        elif path == "/api/set-account-label":
            body = _read_body()
            if body is None:
                return
            _contact = (body.get("contact") or "").strip()
            _username = (body.get("username") or "").strip()
            _label = (body.get("label") or "").strip()
            if not _contact or not _username:
                self._json({"error": "contact and username required"}, 400)
                return
            with _state_lock:
                if not _label:
                    if _contact in account_labels and _username in account_labels[_contact]:
                        del account_labels[_contact][_username]
                        if not account_labels[_contact]:
                            del account_labels[_contact]
                else:
                    account_labels.setdefault(_contact, {})[_username] = _label
            save_state()
            self._json({"ok": True, "contact": _contact, "username": _username, "label": _label})

        elif path == "/api/add-contact":
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
# UI 已拆分到 ui/ 目录下的 _head.py / _styles.py / _body.py / _app.py
# 通过 ui/__init__.py 拼装成 HTML_PAGE 字符串。改 UI 不用动这块。
from ui import HTML_PAGE  # noqa: E402


# ===== 17. Entry Points =====
def main():
    init_profiles()
    refresh_all_contacts()
    log(f"📡 监控面板启动，{len(profile_names)} 个档案，{len(all_contacts_cache)} 个微信会话")
    log(f"🔗 控制面板: http://localhost:{PORT}")
    log(f"🔑 API Token: {API_TOKEN[:4]}...{API_TOKEN[-4:]}  (已脱敏，完整 token 仅用于本地鉴权)")
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
