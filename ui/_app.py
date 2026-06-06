APP_JS = r"""
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

// 日志 emoji → SVG 图标映射（统一风格，去掉丑 emoji）
var _logIconMap = [
  ['📡', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="2.5"/><path d="M12 2 a10 10 0 0 1 0 20"/><path d="M12 6 a6 6 0 0 1 0 12"/></svg>'],
  ['🔗', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'],
  ['🔑', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 2 l-5 5"/><circle cx="17.5" cy="6.5" r="4.5"/><path d="M3 9 l7 7"/><path d="M14 14 l-5 5"/></svg>'],
  ['⏸', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>'],
  ['▶️', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/></svg>'],
  ['🚀', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2 L12 14"/><polygon points="12 2 18 8 6 8 12 2"/></svg>'],
  ['📋', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M9 2 v4"/><path d="M15 2 v4"/></svg>'],
  ['📁', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 19 a2 2 0 0 1 -2 2 H4 a2 2 0 0 1 -2 -2 V5 a2 2 0 0 1 2 -2 h5 l2 3 h9 a2 2 0 0 1 2 2 z"/></svg>'],
  ['📦', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 16 V8 a2 2 0 0 0 -1 -1.73 l-7 -4 a2 2 0 0 0 -2 0 l-7 4 A2 2 0 0 0 3 8 v8 a2 2 0 0 0 1 1.73 l7 4 a2 2 0 0 0 2 0 l7 -4 A2 2 0 0 0 21 16 z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>'],
  ['♻️', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="7 2 4 7 7 12"/><polyline points="17 2 20 7 17 12"/><path d="M4 7 h16 a4 4 0 0 1 0 8 h-2"/><path d="M20 17 h-16 a4 4 0 0 1 0 -8 h2"/></svg>'],
  ['⏹', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>'],
  ['✅', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#22b07d" stroke-width="2.5" stroke-linecap="round"><path d="M5 12 l5 5 l10 -10"/></svg>'],
  ['🔄', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9 a9 9 0 0 1 14.85-3.36 L23 10 M1 14 l4.64 4.36 A9 9 0 0 0 20.49 15"/></svg>'],
  ['⚠️', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86 L1.82 18 a2 2 0 0 0 1.71 3 h16.94 a2 2 0 0 0 1.71 -3 L13.71 3.86 a2 2 0 0 0 -3.42 0 z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'],
  ['❗', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="13"/><circle cx="12" cy="17" r="0.5" fill="#ef4444"/></svg>'],
  ['⚙️', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15 a1.65 1.65 0 0 0 .33 1.82 l.06.06 a2 2 0 0 1 0 2.83 2 2 0 0 1 -2.83 0 l-.06-.06 a1.65 1.65 0 0 0 -1.82-.33 1.65 1.65 0 0 0 -1 1.51V21 a2 2 0 0 1 -4 0v-.09 A1.65 1.65 0 0 0 9 19.4 a1.65 1.65 0 0 0 -1.82.33 l-.06.06 a2 2 0 0 1 -2.83 -2.83 l.06-.06 A1.65 1.65 0 0 0 4.68 15 a1.65 1.65 0 0 0 -1.51 -1 H3 a2 2 0 0 1 0 -4 h.09 A1.65 1.65 0 0 0 4.6 9 a1.65 1.65 0 0 0 -.33 -1.82 l-.06-.06 a2 2 0 0 1 2.83 -2.83 l.06.06 A1.65 1.65 0 0 0 9 4.68 a1.65 1.65 0 0 0 1 -1.51 V3 a2 2 0 0 1 4 0 v.09 a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82 -.33 l.06-.06 a2 2 0 0 1 2.83 2.83 l-.06.06 A1.65 1.65 0 0 0 19.4 9 a1.65 1.65 0 0 0 1.51 1 H21 a2 2 0 0 1 0 4 h-.09 a1.65 1.65 0 0 0 -1.51 1z"/></svg>'],
  ['➕', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#22b07d" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8 v8"/><path d="M8 12 h8"/></svg>'],
  ['➖', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M8 12 h8"/></svg>'],
  ['💬', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15 a2 2 0 0 1 -2 2 H7 l-4 4 V5 a2 2 0 0 1 2 -2 h14 a2 2 0 0 1 2 2 z"/></svg>'],
  ['📝', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4 H4 a2 2 0 0 0 -2 2 v14 a2 2 0 0 0 2 2 h14 a2 2 0 0 0 2 -2 v-7"/><path d="M18.5 2.5 a2.121 2.121 0 0 1 3 3 L12 15 l-4 1 1 -4 9.5 -9.5z"/></svg>'],
  ['🔁', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11 V9 a4 4 0 0 1 4 -4 h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13 v2 a4 4 0 0 1 -4 4 H3"/></svg>'],
  ['🔍', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'],
  ['🗑️', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6 v14 a2 2 0 0 1 -2 2 H7 a2 2 0 0 1 -2 -2 V6 m3 0 V4 a2 2 0 0 1 2 -2 h4 a2 2 0 0 1 2 2 v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>'],
  ['📂', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 19 a2 2 0 0 1 -2 2 H4 a2 2 0 0 1 -2 -2 V5 a2 2 0 0 1 2 -2 h5 l2 3 h9 a2 2 0 0 1 2 2 z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>'],
];
var _logIconRe = new RegExp(_logIconMap.map(function(p){return p[0]}).join('|'), 'g');

function _replaceLogIcons(msg) {
  return msg.replace(_logIconRe, function(m) {
    for (var i = 0; i < _logIconMap.length; i++) {
      if (_logIconMap[i][0] === m) return '<span class="log-icon">' + _logIconMap[i][1] + '</span>';
    }
    return m;
  });
}

// 日志消息类型筛选（持久化到 localStorage）
var _logFilterKey = "wechat_monitor_log_filter";
// 每个 checkbox 的 data-kw 是匹配关键词（用 | 分隔多个关键词）
function _getLogFilter() {
  try { return JSON.parse(localStorage.getItem(_logFilterKey)); } catch(e) { return null; }
}
function _getDefaultFilter() {
  var kw = [];
  document.querySelectorAll("#logFilterDropdown input[type='checkbox']").forEach(function(cb) {
    kw.push(cb.dataset.kw);
  });
  return kw;
}
function toggleLogFilter() {
  var dd = document.getElementById("logFilterDropdown");
  if (dd) dd.classList.toggle("open");
}
// 点击外部关闭
document.addEventListener("click", function(e) {
  var dd = document.getElementById("logFilterDropdown");
  var btn = e.target.closest && e.target.closest(".log-filter-btn");
  if (dd && !btn && !dd.contains(e.target)) dd.classList.remove("open");
});
function updateLogFilter() {
  var checkedKw = [];
  document.querySelectorAll("#logFilterDropdown input[type='checkbox']").forEach(function(cb) {
    if (cb.checked) checkedKw.push(cb.dataset.kw);
  });
  localStorage.setItem(_logFilterKey, JSON.stringify(checkedKw));
  if (window._lastLogs) renderLogs(window._lastLogs);
}
// 初始化 checkbox 状态 + 默认全选
(function() {
  var filter = _getLogFilter() || _getDefaultFilter();
  // 如果存储的比当前 checkbox 少（新增了类型），用默认
  var allKw = _getDefaultFilter();
  if (filter.length < allKw.length) filter = allKw;
  document.querySelectorAll("#logFilterDropdown input[type='checkbox']").forEach(function(cb) {
    cb.checked = filter.indexOf(cb.dataset.kw) !== -1;
  });
  localStorage.setItem(_logFilterKey, JSON.stringify(filter));
})();

function renderLogs(logs) {
  window._lastLogs = logs;  // 保存完整数据供筛选用
  var activeKws = _getLogFilter() || _getDefaultFilter();
  // 构建"被排除的关键词"集合：所有 filter 项的关键词
  // 只有当消息匹配某个被取消勾选的 filter 时才隐藏
  var allKws = _getDefaultFilter();
  var excludedKws = [];
  for (var i = 0; i < allKws.length; i++) {
    if (activeKws.indexOf(allKws[i]) === -1) {
      // 这个 filter 被取消了，它的关键词要排除
      excludedKws = excludedKws.concat(allKws[i].split("|"));
    }
  }
  var filtered = (logs || []).filter(function(l) {
    // 如果消息匹配任何被排除的关键词，隐藏
    for (var j = 0; j < excludedKws.length; j++) {
      if (l.msg && l.msg.indexOf(excludedKws[j]) !== -1) return false;
    }
    return true;  // 默认显示（未匹配到任何排除关键词）
  });
  const area = document.getElementById("logArea");
  if (!filtered.length) { area.innerHTML = '<div class="empty">暂无动态</div>'; return; }
  const atBot = area.scrollTop + area.clientHeight >= area.scrollHeight - 30;
  area.innerHTML = filtered.map(function(l) {
    var msg = escapeHtml(l.msg);
    // 用 SVG 图标替换丑 emoji
    msg = _replaceLogIcons(msg);
    return '<div class="log"><span class="log-time">' + l.time + '</span><span class="log-level ' + l.level + '">' + l.level + '</span><span class="log-msg">' + msg + '</span></div>';
  }).join("");
  if (atBot) area.scrollTop = area.scrollHeight;
}

function _profColor(name) {
  var h = 0;
  for (var i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  var hue = Math.abs(h) % 360;
  return "linear-gradient(135deg,hsl(" + hue + ",65%,62%),hsl(" + ((hue + 30) % 360) + ",55%,55%))";
}

var _expandedGroups = new Set();

function _toggleGroup(chat) {
  if (_expandedGroups.has(chat)) _expandedGroups.delete(chat);
  else _expandedGroups.add(chat);
  var node = document.querySelector('[data-group-chat="' + cssEscape(chat) + '"]');
  if (!node) return;
  var isExpanded = node.classList.toggle("expanded");
  // 同步更新按钮的图标和文字
  var btn = node.querySelector(".btn-toggle");
  if (btn) {
    var icon = isExpanded
      ? '<svg viewBox="0 0 24 24"><polyline points="6 15 12 9 18 15" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      : '<svg viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    btn.innerHTML = icon + (isExpanded ? "折叠" : "展开");
    btn.title = (isExpanded ? "折叠" : "展开") + "子账号";
  }
}

function cssEscape(s) {
  return String(s).replace(/["\\]/g, "\\$&");
}

// 联系人拖拽排序（存 localStorage，后端同步到 state.json）
var _dragKey = "wechat_monitor_contact_order";
function _getContactOrder() {
  try { return JSON.parse(localStorage.getItem(_dragKey)) || []; } catch(e) { return []; }
}
function _saveContactOrder(order) {
  localStorage.setItem(_dragKey, JSON.stringify(order));
  // 同步到后端
  fetch(API + "/api/contact-order", {
    method: "POST",
    headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
    body: JSON.stringify({order: order})
  }).catch(function(){});
}
function _sortContacts(contacts) {
  var order = _getContactOrder();
  if (!order.length) return contacts;
  var orderMap = {};
  order.forEach(function(name, i) { orderMap[name] = i; });
  return contacts.slice().sort(function(a, b) {
    var ia = orderMap.hasOwnProperty(a) ? orderMap[a] : 9999;
    var ib = orderMap.hasOwnProperty(b) ? orderMap[b] : 9999;
    return ia - ib;
  });
}
var _draggedContact = null;
var _draggedType = null; // "main" 或 "sub"
function _onDragStart(e, name, type) {
  _draggedContact = name;
  _draggedType = type || "main";
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", name);
  var el = e.target.closest(".contact,.contact-group,.sub-row");
  if (el) el.classList.add("dragging");
}
function _onDragEnd(e) {
  var el = e.target.closest(".contact,.contact-group,.sub-row");
  if (el) el.classList.remove("dragging");
  document.querySelectorAll(".drag-over").forEach(function(x) { x.classList.remove("drag-over"); });
  _draggedContact = null;
}
function _onDragOver(e, name) {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  // 只有同类型才能拖到对方上面
  var target = e.target.closest(".contact,.contact-group");
  if (!target) return;
  document.querySelectorAll(".drag-over").forEach(function(x) { x.classList.remove("drag-over"); });
  target.classList.add("drag-over");
}
function _onDrop(e, targetName) {
  e.preventDefault();
  document.querySelectorAll(".drag-over").forEach(function(x) { x.classList.remove("drag-over"); });
  if (!_draggedContact || _draggedContact === targetName) return;
  // 重排序
  var contacts = window._lastProfileData && window._lastProfileData.monitored_contacts || [];
  var idx1 = contacts.indexOf(_draggedContact);
  var idx2 = contacts.indexOf(targetName);
  if (idx1 === -1 || idx2 === -1) return;
  contacts.splice(idx1, 1);
  contacts.splice(idx2, 0, _draggedContact);
  // 保存并重新渲染
  _saveContactOrder(contacts);
  window._lastProfileData.monitored_contacts = contacts;
  renderProfilesWithFilter();
}


// ===== 拖拽排序（mousedown/mousemove/mouseup，不用 HTML5 drag API）=====
var _dragState = null; // {type, contact, username, startY, startY, placeholder, original}
(function(){
  var list = document.getElementById("profileList");
  if (!list) return;

  list.addEventListener("mousedown", function(e) {
    var handle = e.target.closest(".drag-handle");
    if (!handle) return;
    e.preventDefault();
    var subRow = handle.closest(".sub-row");
    var contactEl = handle.closest(".contact,.contact-group");
    var type = subRow ? "sub" : "main";
    var contact = subRow ? subRow.dataset.dragContact : (handle.dataset.dragContact || "");
    var username = subRow ? subRow.dataset.dragUser : null;

    // 找到要移动的元素
    var movable = subRow || contactEl;
    if (!movable) return;

    // 创建占位符
    var placeholder = document.createElement("div");
    placeholder.className = "drag-placeholder";
    placeholder.style.height = movable.offsetHeight + "px";

    _dragState = {
      type: type, contact: contact, username: username,
      movable: movable, placeholder: placeholder,
      startY: e.clientY, offsetY: 0, started: false
    };

    // 绑定 mousemove/mouseup
    document.addEventListener("mousemove", _onMouseMove);
    document.addEventListener("mouseup", _onMouseUp);
  });

  function _onMouseMove(e) {
    if (!_dragState) return;
    var dy = Math.abs(e.clientY - _dragState.startY);
    // 5px threshold to distinguish click from drag
    if (!_dragState.started && dy < 5) return;
    if (!_dragState.started) {
      _dragState.started = true;
      _dragState.movable.classList.add("dragging");
      // 插入占位符
      _dragState.movable.parentNode.insertBefore(_dragState.placeholder, _dragState.movable);
    }

    // 找到当前鼠标下方的目标
    _dragState.placeholder.style.display = "none";
    var underEl = document.elementFromPoint(e.clientX, e.clientY);
    _dragState.placeholder.style.display = "";
    if (!underEl) return;

    if (_dragState.type === "main") {
      var target = underEl.closest(".contact,.contact-group");
      if (target && target !== _dragState.movable && target !== _dragState.placeholder) {
        // 在目标前面或后面插入占位符
        var rect = target.getBoundingClientRect();
        var mid = rect.top + rect.height / 2;
        if (e.clientY < mid) {
          target.parentNode.insertBefore(_dragState.placeholder, target);
        } else {
          target.parentNode.insertBefore(_dragState.placeholder, target.nextSibling);
        }
      }
    } else {
      var targetRow = underEl.closest(".sub-row");
      if (targetRow && targetRow !== _dragState.movable && targetRow !== _dragState.placeholder) {
        var rect = targetRow.getBoundingClientRect();
        var mid = rect.top + rect.height / 2;
        if (e.clientY < mid) {
          targetRow.parentNode.insertBefore(_dragState.placeholder, targetRow);
        } else {
          targetRow.parentNode.insertBefore(_dragState.placeholder, targetRow.nextSibling);
        }
      }
    }
  }

  function _onMouseUp(e) {
    document.removeEventListener("mousemove", _onMouseMove);
    document.removeEventListener("mouseup", _onMouseUp);
    if (!_dragState) return;

    if (_dragState.started) {
      // 把移动的元素放到占位符的位置
      _dragState.placeholder.parentNode.insertBefore(_dragState.movable, _dragState.placeholder);
      _dragState.placeholder.remove();
      _dragState.movable.classList.remove("dragging");

      // 收集新顺序
      if (_dragState.type === "main") {
        var newOrder = [];
        list.querySelectorAll(".contact,.contact-group").forEach(function(el) {
          var h = el.querySelector(".drag-handle");
          if (h && h.dataset.dragContact) newOrder.push(h.dataset.dragContact);
        });
        if (newOrder.length) {
          _saveContactOrder(newOrder);
          window._lastProfileData.monitored_contacts = newOrder;
          renderProfilesWithFilter();
        }
      } else {
        // 子账号顺序
        var subKey = "wechat_monitor_sub_order_" + _dragState.contact;
        var newOrder = [];
        var container = _dragState.movable.parentNode;
        container.querySelectorAll(".sub-row").forEach(function(row) {
          if (row.dataset.dragUser) newOrder.push(row.dataset.dragUser);
        });
        if (newOrder.length) {
          localStorage.setItem(subKey, JSON.stringify(newOrder));
          fetch(API+"/api/contact_accounts",{method:"POST",headers:Object.assign(authHeaders(),{"Content-Type":"application/json"}),body:JSON.stringify({action:"set_sub_order",contact:_dragState.contact,order:newOrder})}).catch(function(){});
          var contact = _dragState.contact;
          _dragState = null;
          showProfile(contact);
          return;
        }
      }
    }
    _dragState = null;
  }
})();
function renderProfilesWithFilter() {
  var q = (document.getElementById("contactSearch").value || "").toLowerCase();
  var el = document.getElementById("profileList");
  var contacts = window._lastProfileData && window._lastProfileData.monitored_contacts || [];
  var profiles = window._lastProfileData && window._lastProfileData.profile_list || [];
  var aliasMap = window._lastProfileData && window._lastProfileData.alias_map || {};
  var accountMap = window._lastProfileData && window._lastProfileData.contact_accounts || {};
  contacts = _sortContacts(contacts);
  var filtered = q ? contacts.filter(function(c) { return c.toLowerCase().indexOf(q) !== -1; }) : contacts;
  if (!filtered.length) { el.innerHTML = '<div class="empty">' + (q ? '未找到匹配的联系人' : '暂无监控联系人') + '</div>'; return; }
  el.innerHTML = filtered.map(function(c) {
    var has = profiles.indexOf(c) !== -1;
    var aliases = aliasMap[c] || [];
    var col = _profColor(c);
    var aliasHtml = aliases.length ? '<span class="badge badge-alias">' + escapeHtml(aliases[0] + (aliases.length > 1 ? " +" + (aliases.length - 1) : "")) + '</span>' : "";
    var accounts = accountMap[c] || [];
    var multi = accounts.length > 1;
    var expanded = _expandedGroups.has(c);

    if (!multi) {
      // 单账号：原样式
      var _sc = escapeHtml(c).replace(/'/g, "\\'");
      var _dragHandle = '<span class="drag-handle" data-drag-contact="' + escapeHtml(c) + '" title="拖拽排序"><svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><circle cx="9" cy="5" r="1.5"/><circle cx="15" cy="5" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="19" r="1.5"/><circle cx="15" cy="19" r="1.5"/></svg></span>';
      return '<div class="contact"><div class="contact-info">' + _dragHandle
        + '<div class="avatar" style="background:' + col + '">' + escapeHtml(c.charAt(0)) + '</div>'
        + '<div><div class="contact-name" style="cursor:pointer" onclick="showProfile(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')">' + escapeHtml(c) + '</div>'
        + '<div class="contact-meta">'
        + (has ? '<span class="badge badge-profile">有档案</span>' : '<span class="badge badge-manual">手动</span>')
        + aliasHtml + '</div></div></div>'
        + '<div class="contact-acts">'
        + '<button class="btn-sm btn-analyze" onclick="suggestReply(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\',\'' + escapeHtml(accounts[0] ? accounts[0].username : (contactsData[c] || "")) + '\')">'
        + '<svg viewBox="0 0 24 24"><path d="M3 17 l5 -6 l4 4 l8 -9"/><path d="M14 6 h6 v6"/></svg>分析</button>'
        + '<button class="btn-rm" onclick="removeContact(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')" title="取消监控">'
        + '<svg viewBox="0 0 24 24"><path d="M6 6 l12 12"/><path d="M18 6 l-12 12"/></svg></button>'
        + '</div></div>';
    }

    // 多账号：主行 + 子分支。优先显示 label（用户改的"微信号"），回退到 username
    // 应用 localStorage 里的子账号拖拽排序
    var _subKey = "wechat_monitor_sub_order_" + c;
    try {
      var _subOrder = JSON.parse(localStorage.getItem(_subKey));
      if (_subOrder && _subOrder.length) {
        var _subOrderMap = {};
        _subOrder.forEach(function(u, i) { _subOrderMap[u] = i; });
        accounts = accounts.slice().sort(function(a, b) {
          var ia = _subOrderMap.hasOwnProperty(a.username) ? _subOrderMap[a.username] : 9999;
          var ib = _subOrderMap.hasOwnProperty(b.username) ? _subOrderMap[b.username] : 9999;
          return ia - ib;
        });
      }
    } catch(e) {}
    var subRows = accounts.map(function(a) {
      // 优先 label，其次 chat，最后 username
      var displayLabel = a.label || a.chat || a.username;
      // 有 label 时就不强制加 (主账号) 文字（label 已经是用户自己写的）
      // 没 label 且是主账号时才加 (主账号)
      if (a.is_primary && !a.label) displayLabel += " (主账号)";
      var titleText = a.username + (a.label ? "  ·  " + a.label : "");
      var _subU = escapeHtml(a.username).replace(/'/g, "\\'");
      return '<div class="sub-row" data-drag-contact="' + escapeHtml(c) + '" data-drag-user="' + escapeHtml(a.username) + '"><span class="drag-handle sub-drag-handle"><svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><circle cx="6" cy="4" r="1.2"/><circle cx="10" cy="4" r="1.2"/><circle cx="6" cy="8" r="1.2"/><circle cx="10" cy="8" r="1.2"/><circle cx="6" cy="12" r="1.2"/><circle cx="10" cy="12" r="1.2"/></svg></span>'
        + '<div class="sub-name" title="' + escapeHtml(titleText) + '">' + escapeHtml(displayLabel) + '</div>'
        + '<div class="sub-acts">'
        + '<button class="btn-sm btn-analyze" onclick="suggestReply(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\',\'' + escapeHtml(a.username) + '\')">'
        + '<svg viewBox="0 0 24 24"><path d="M3 17 l5 -6 l4 4 l8 -9"/><path d="M14 6 h6 v6"/></svg>分析</button>'
        + '</div></div>';
    }).join("");

    var expandIcon = expanded
      ? '<svg viewBox="0 0 24 24"><polyline points="6 15 12 9 18 15" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      : '<svg viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    var expandLabel = expanded ? "折叠" : "展开";
    var expandBtn = '<button class="btn-sm btn-toggle" onclick="_toggleGroup(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')" title="' + expandLabel + '子账号">'
      + expandIcon + expandLabel + '</button>';

    var _sc2 = escapeHtml(c).replace(/'/g, "\'");
    var _dragHandle2 = '<span class="drag-handle" data-drag-contact="' + escapeHtml(c) + '" title="拖拽排序"><svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><circle cx="9" cy="5" r="1.5"/><circle cx="15" cy="5" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="19" r="1.5"/><circle cx="15" cy="19" r="1.5"/></svg></span>';
    return '<div class="contact-group has-sub ' + (expanded ? "expanded" : "") + '" data-group-chat="' + cssEscape(c) + '">'
      + '<div class="group-head"><div class="contact-info">'
      + _dragHandle2
      + '<div class="avatar" style="background:' + col + '">' + escapeHtml(c.charAt(0)) + '</div>'
      + '<div><div class="contact-name" style="cursor:pointer" onclick="showProfile(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')">' + escapeHtml(c) + '<span class="acct-badge">' + accounts.length + ' 账号</span></div>'
      + '<div class="contact-meta">'
      + (has ? '<span class="badge badge-profile">有档案</span>' : '<span class="badge badge-manual">手动</span>')
      + aliasHtml + '</div></div></div>'
      + '<div class="contact-acts">'
      + expandBtn
      + '<button class="btn-rm" onclick="removeContact(\'' + escapeHtml(c).replace(/'/g, "\\'") + '\')" title="取消监控所有账号">'
      + '<svg viewBox="0 0 24 24"><path d="M6 6 l12 12"/><path d="M18 6 l-12 12"/></svg></button>'
      + '</div></div>'
      + '<div class="sub-list">' + subRows + '</div>'
      + '</div>';
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
    fb.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px"><path d="M5 12 l5 5 l10 -10"/></svg>已保存';
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
    document.getElementById("runningTime").textContent = d.running_time || "00:00:00";
    // 从 running_time 字符串解析秒数，同步本地计时器
    if (d.running_time) {
      var parts = d.running_time.split(":");
      if (parts.length === 3) {
        _runningSec = parseInt(parts[0])*3600 + parseInt(parts[1])*60 + parseInt(parts[2]);
        _startRunningTimer();
      }
    }
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
// 本地 1 秒定时器：运行时长实时更新（不依赖 API）
var _runningSec = 0;
var _runningTimerStarted = false;
function _startRunningTimer() {
  if (_runningTimerStarted) return;
  _runningTimerStarted = true;
  setInterval(function() {
    if (_runningSec > 0) {
      _runningSec++;
      var h = Math.floor(_runningSec / 3600);
      var m = Math.floor((_runningSec % 3600) / 60);
      var s = _runningSec % 60;
      var el = document.getElementById("runningTime");
      if (el) el.textContent = (h<10?"0":"")+h+":"+(m<10?"0":"")+m+":"+(s<10?"0":"")+s;
    }
  }, 1000);
}

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
  el.innerHTML=_excludeList.map(function(c){return '<span class="chip">'+escapeHtml(c)+' <span class="chip-x" onclick="removeExclude(\''+escapeHtml(c).replace(/'/g,"\\'")+'\')"><svg viewBox=\"0 0 24 24\" width=\"10\" height=\"10\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\"><path d=\"M6 6 l12 12\"/><path d=\"M18 6 l-12 12\"/></svg></span></span>';}).join("");
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
let _currentContact = null;

async function showProfile(name){
    _currentContact = name;
  // 标题 + 头像
  document.getElementById("profileTitleText").textContent = name + " — 人物档案";
  var av = document.getElementById("profileAvatar");
  av.textContent = name.charAt(0);
  av.style.background = _profColor(name);
  // 档案内容
  var el = document.getElementById("profileContent");
  el.innerHTML = '<div class="empty">加载中...</div>';
  // 账号管理
  document.getElementById("acctList").innerHTML = '<div class="acct-empty">加载中...</div>';
  document.getElementById("acctCount").textContent = "...";
  document.getElementById("acctAddForm").style.display = "none";
  document.getElementById("acctNewUsername").value = "";
  document.getElementById("acctNewChat").value = "";
  document.getElementById("acctNewLabel").value = "";
  document.getElementById("acctConfirmBtn").disabled = true;
  document.getElementById("profileModal").classList.add("open");
  // 并行加载档案 + 账号
  var p1 = fetch(API+"/api/profile?name="+encodeURIComponent(name),{headers:authHeaders()}).then(function(r){return r.json();});
  var p2 = fetch(API+"/api/contact_accounts?contact="+encodeURIComponent(name),{headers:authHeaders()}).then(function(r){return r.json();});
  try {
    var d = await p1;
    if(!d.exists){
      el.innerHTML='<div class="empty">未找到「'+escapeHtml(name)+'」的档案。\n你仍可以在上方添加该联系人的多账号。</div>';
    } else {
      var md = d.content || "";
      md = md.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      md = md.replace(/^### (.+)$/gm,"<h3>$1</h3>").replace(/^## (.+)$/gm,"<h3>$1</h3>").replace(/^# (.+)$/gm,"<h1>$1</h1>");
      md = md.replace(/\*\*(.+?)\*\*/g,"<b>$1</b>");
      md = md.replace(/^---$/gm,"<hr>");
      el.innerHTML = '<div class="prof-md">' + md + '</div>';
    }
  } catch(e) { el.innerHTML = '<div class="empty">档案加载失败</div>'; }
  try {
    var ad = await p2;
    renderAcctList(ad.accounts || []);
  } catch(e) {
    document.getElementById("acctList").innerHTML = '<div class="acct-empty">账号加载失败</div>';
    document.getElementById("acctCount").textContent = "?";
  }
}

function renderAcctList(accounts) {
  var list = document.getElementById("acctList");
  // 应用子账号拖拽排序（从 localStorage）
  if (_currentContact && accounts.length > 1) {
    var subKey = "wechat_monitor_sub_order_" + _currentContact;
    try {
      var subOrder = JSON.parse(localStorage.getItem(subKey));
      if (subOrder && subOrder.length) {
        var orderMap = {};
        subOrder.forEach(function(u, i) { orderMap[u] = i; });
        accounts = accounts.slice().sort(function(a, b) {
          var ia = orderMap.hasOwnProperty(a.username) ? orderMap[a.username] : 9999;
          var ib = orderMap.hasOwnProperty(b.username) ? orderMap[b.username] : 9999;
          return ia - ib;
        });
      }
    } catch(e) {}
  }
  document.getElementById("acctCount").textContent = accounts.length;
  if (!accounts.length) {
    list.innerHTML = '<div class="acct-empty">还没有账号，点击右上角"添加"</div>';
    return;
  }
  // 存储原始数据供 inline 编辑用
  window._currentAccts = {};
  list.innerHTML = accounts.map(function(a) {
    window._currentAccts[a.username] = a;
    var sourceLabel = a.source === "manual" ? "手动" : (a.source === "alias" ? "档案" : "自动");
    var sourceClass = "src-" + a.source;
    var primaryStar = a.is_primary ? '<svg class="primary-star" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M12 2 l3 7 l7 1 l-5 5 l1 7 l-6 -3 l-6 3 l1 -7 l-5 -5 l7 -1 z"/></svg>' : "";
    var displayName = a.label ? a.label : a.chat;
    var meta = a.username + (a.chat && a.chat !== a.username ? "  ·  chat: " + a.chat : "");
    var setPrimaryBtn = !a.is_primary
      ? '<button class="acct-act-btn" data-action="setPrimaryAcct" data-username="' + a.username + '" title="设为主账号"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 l3 7 l7 1 l-5 5 l1 7 l-6 -3 l-6 3 l1 -7 l-5 -5 l7 -1 z"/></svg></button>'
      : "";
    // 所有账号都能重命名（铅笔图标）
    var renameBtn = '<button class="acct-act-btn" data-action="startRenameAcct" data-username="' + a.username + '" title="重命名 / 改显示名"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4 l6 6 l-10 10 l-6 1 l1 -6 z"/><path d="M13 5 l6 6"/></svg></button>';
    // 删除/隐藏：manual 真删；auto/alias 加 hidden 标记
    var delTitle, delAction, delMsg, isManual = (a.source === "manual");
    if (isManual) {
      delTitle = "删除该账号";
      delAction = "removeManualAcct";
      delMsg = "确认删除账号 \"" + a.username + "\"？";
    } else {
      delTitle = "隐藏该账号（可随时在 state.json 中恢复）";
      delAction = "hideAcct";
      delMsg = "确认隐藏账号 \"" + a.username + "\"？\n隐藏后将不在此联系人的账号列表中显示，但实际微信账号还在。";
    }
    // 用 data 属性 + 事件委托，避免 onclick 字符串转义问题
    delBtn = '<button class="acct-act-btn del" data-action="' + delAction + '" data-username="' + a.username + '" data-msg="' + delMsg.replace(/"/g, "&quot;") + '" title="' + delTitle + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6 l12 12"/><path d="M18 6 l-12 12"/></svg></button>';
    return '<div class="acct-item ' + (a.source === "manual" ? "manual" : "") + '" data-u="' + escapeHtml(a.username) + '">'
      + '<div class="acct-item-info">'
      + '<div class="acct-item-name" data-role="display">' + primaryStar + escapeHtml(displayName) + ' <span class="src-tag ' + sourceClass + '">' + sourceLabel + '</span></div>'
      + '<div class="acct-item-meta" data-role="meta">' + escapeHtml(meta) + '</div>'
      + '</div>'
      + '<div class="acct-item-acts">' + setPrimaryBtn + renameBtn + delBtn + '</div>'
      + '</div>';
  }).join("");
}

// 进入 inline 重命名模式
function startRenameAcct(username) {
  var item = document.querySelector('.acct-item[data-u="' + cssEscape(username) + '"]');
  if (!item) return;
  var displayEl = item.querySelector('[data-role="display"]');
  var metaEl = item.querySelector('[data-role="meta"]');
  var acct = (window._currentAccts || {})[username] || {};
  var currentLabel = acct.label || "";
  // 把显示名替换成输入框，保留 source tag
  var srcTagHtml = displayEl.querySelector(".src-tag") ? displayEl.querySelector(".src-tag").outerHTML : "";
  var starHtml = displayEl.querySelector(".primary-star") ? displayEl.querySelector(".primary-star").outerHTML : "";
  displayEl.innerHTML = '<div class="acct-rename-row">'
    + starHtml
    + '<input class="acct-rename-input" type="text" value="' + escapeHtml(currentLabel) + '" placeholder="留空则用 chat 名" />'
    + '<button class="acct-act-btn ok" data-action="saveRenameAcct" data-username="' + username + '" title="保存"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12 l5 5 l10 -10"/></svg></button>'
    + '<button class="acct-act-btn cancel" data-action="cancelRenameAcct" data-username="' + username + '" title="取消"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6 l12 12"/><path d="M18 6 l-12 12"/></svg></button>'
    + srcTagHtml
    + '</div>';
  var input = displayEl.querySelector(".acct-rename-input");
  input.focus();
  input.select();
  input.addEventListener("keydown", function(e) {
    if (e.key === "Enter") saveRenameAcct(username);
    else if (e.key === "Escape") cancelRenameAcct(username);
  });
}

async function saveRenameAcct(username) {
  var item = document.querySelector('.acct-item[data-u="' + cssEscape(username) + '"]');
  if (!item || !_currentContact) return;
  var input = item.querySelector(".acct-rename-input");
  var newLabel = input ? input.value.trim() : "";
  try {
    var r = await fetch(API + "/api/set-account-label", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({contact: _currentContact, username: username, label: newLabel})
    });
    var d = await r.json();
    if (d.ok) {
      // 重新拉列表
      var r2 = await fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      var ad = await r2.json();
      renderAcctList(ad.accounts || []);
      if (typeof refresh === "function") refresh();
    } else {
      alert("保存失败: " + (d.error || "未知错误"));
    }
  } catch(e) { alert("网络错误"); }
}

function cancelRenameAcct(username) {
  // 重新渲染整个列表回到原状
  if (!_currentContact) return;
  fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()})
    .then(function(r){return r.json();})
    .then(function(ad){ renderAcctList(ad.accounts || []); });
}

async function hideAcct(username, confirmMsg) {
  if (!confirm(confirmMsg)) return;
  if (!_currentContact) return;
  try {
    var r = await fetch(API + "/api/contact_accounts", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({action: "hide", contact: _currentContact, username: username})
    });
    var d = await r.json();
    if (d.ok) {
      var r2 = await fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      var ad = await r2.json();
      renderAcctList(ad.accounts || []);
      if (typeof refresh === "function") refresh();
    }
  } catch(e) { alert("隐藏失败"); }
}

function toggleAcctAddForm() {
  var f = document.getElementById("acctAddForm");
  if (f.style.display === "none") {
    f.style.display = "block";
    document.getElementById("acctNewUsername").focus();
  } else {
    f.style.display = "none";
  }
}

function cancelAddAcct() {
  document.getElementById("acctAddForm").style.display = "none";
  document.getElementById("acctNewUsername").value = "";
  document.getElementById("acctNewChat").value = "";
  document.getElementById("acctNewLabel").value = "";
  document.getElementById("acctConfirmBtn").disabled = true;
}

// 输入实时校验
document.addEventListener("input", function(e) {
  if (e.target && e.target.id === "acctNewUsername") {
    document.getElementById("acctConfirmBtn").disabled = !e.target.value.trim();
  }
});

// 账号列表按钮事件委托（删除/隐藏/重命名/设主号）
document.addEventListener("click", function(e) {
  var btn = e.target.closest && e.target.closest(".acct-act-btn");
  if (!btn || !btn.dataset || !btn.dataset.action) return;
  e.preventDefault();
  e.stopPropagation();
  var action = btn.dataset.action;
  var username = btn.dataset.username;
  if (action === "removeManualAcct" || action === "hideAcct") {
    var msg = btn.dataset.msg || "确认操作？";
    if (typeof msg === "string") {
      // 反转义 &quot; 还原成 "
      msg = msg.replace(/&quot;/g, '"');
    }
    if (!confirm(msg)) return;
    var apiAction = action === "removeManualAcct" ? "remove" : "hide";
    fetch(API + "/api/contact_accounts", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({action: apiAction, contact: _currentContact, username: username})
    })
    .then(function(r){return r.json();})
    .then(function(d){
      if (d.ok) {
        return fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      } else {
        alert("操作失败: " + (d.error || "未知错误"));
        return null;
      }
    })
    .then(function(r){ if (r) return r.json(); })
    .then(function(ad){ if (ad) { renderAcctList(ad.accounts || []); if (typeof refresh === "function") refresh(); } })
    .catch(function(){ alert("网络错误"); });
  } else if (action === "setPrimaryAcct") {
    fetch(API + "/api/contact_accounts", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({action: "set_primary", contact: _currentContact, username: username})
    })
    .then(function(r){return r.json();})
    .then(function(d){
      if (d.ok) {
        return fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      }
    })
    .then(function(r){ if (r) return r.json(); })
    .then(function(ad){ if (ad) { renderAcctList(ad.accounts || []); if (typeof refresh === "function") refresh(); } });
  } else if (action === "startRenameAcct") {
    startRenameAcct(username);
  } else if (action === "saveRenameAcct") {
    saveRenameAcct(username);
  } else if (action === "cancelRenameAcct") {
    cancelRenameAcct(username);
  }
});

async function addManualAccount() {
  if (!_currentContact) return;
  var u = document.getElementById("acctNewUsername").value.trim();
  if (!u) return;
  var c = document.getElementById("acctNewChat").value.trim();
  var l = document.getElementById("acctNewLabel").value.trim();
  var btn = document.getElementById("acctConfirmBtn");
  btn.disabled = true;
  btn.textContent = "添加中...";
  try {
    var r = await fetch(API + "/api/contact_accounts", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({action: "add", contact: _currentContact, username: u, chat: c, label: l})
    });
    var d = await r.json();
    if (d.ok) {
      cancelAddAcct();
      // 重新拉账号列表
      var r2 = await fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      var ad = await r2.json();
      renderAcctList(ad.accounts || []);
      // 同步刷新左侧联系人列表（多账号徽章）
      if (typeof refresh === "function") refresh();
    } else {
      alert("添加失败: " + (d.error || "未知错误"));
    }
  } catch(e) {
    alert("网络错误");
  } finally {
    btn.disabled = false;
    btn.textContent = "确认添加";
  }
}

async function removeManualAcct(username) {
  if (!_currentContact) return;
  if (!confirm("确认删除账号 \"" + username + "\"？")) return;
  try {
    var r = await fetch(API + "/api/contact_accounts", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({action: "remove", contact: _currentContact, username: username})
    });
    var d = await r.json();
    if (d.ok) {
      var r2 = await fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      var ad = await r2.json();
      renderAcctList(ad.accounts || []);
      if (typeof refresh === "function") refresh();
    }
  } catch(e) { alert("删除失败"); }
}

async function setPrimaryAcct(username) {
  if (!_currentContact) return;
  try {
    var r = await fetch(API + "/api/contact_accounts", {
      method: "POST",
      headers: Object.assign(authHeaders(), {"Content-Type":"application/json"}),
      body: JSON.stringify({action: "set_primary", contact: _currentContact, username: username})
    });
    var d = await r.json();
    if (d.ok) {
      var r2 = await fetch(API + "/api/contact_accounts?contact=" + encodeURIComponent(_currentContact), {headers: authHeaders()});
      var ad = await r2.json();
      renderAcctList(ad.accounts || []);
      if (typeof refresh === "function") refresh();
    }
  } catch(e) { alert("设置失败"); }
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
"""
