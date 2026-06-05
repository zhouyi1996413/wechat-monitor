BODY = r"""
</head>
<body>
<div class="wrap">

<div class="top">
  <div class="brand">
    <div class="logo" style="background:linear-gradient(135deg,#a78bff,#5d86ff)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="0"><path d="M5.5 4 A8 8 0 0 1 21 4 v6 a8 8 0 0 1 -8 8 h-4 l-4 4 v-4 a8 8 0 0 1 .5 -14 z" fill="#fff"/><circle cx="9" cy="10" r="1.6" fill="#7b61ff"/><circle cx="15" cy="10" r="1.6" fill="#7b61ff"/><path d="M9 14 q3 2.5 6 0" stroke="#7b61ff" stroke-width="1.4" stroke-linecap="round" fill="none"/></svg></div>
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
      <div class="stat-head">
        <div class="stat-icon purple"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 20 c0 -3 2.5 -5.5 5.5 -5.5 s5.5 2.5 5.5 5.5"/><circle cx="16" cy="6" r="2.4"/><path d="M14.5 13 c1.8 -.5 5.5 .5 5.5 4.5"/></svg></div>
        <div class="stat-title">监控人数</div>
      </div>
      <div class="stat-big" id="totalProfiles">- <span class="unit">人</span></div>
    </div>
    <div class="glass stat">
      <div class="stat-head">
        <div class="stat-icon green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5 a2 2 0 0 1 2 -2 h12 a2 2 0 0 1 2 2 v8 a2 2 0 0 1 -2 2 h-9 l-3 3 v-3 a2 2 0 0 1 -2 -2 z"/><circle cx="8" cy="9" r="1.1" fill="currentColor" stroke="none"/><circle cx="12" cy="9" r="1.1" fill="currentColor" stroke="none"/><circle cx="16" cy="9" r="1.1" fill="currentColor" stroke="none"/></svg></div>
        <div class="stat-title">今日更新</div>
      </div>
      <div class="stat-big" id="totalUpdates">- <span class="unit">次</span></div>
    </div>
    <div class="glass stat">
      <div class="stat-head">
        <div class="stat-icon orange"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7 v5 l3.5 2"/></svg></div>
        <div class="stat-title">运行时长</div>
      </div>
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
    <div class="poll-illust">
      <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="wandG" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#a78bff"/>
            <stop offset="1" stop-color="#5d86ff"/>
          </linearGradient>
        </defs>
        <!-- 主四芒星（中心偏右） -->
        <path d="M62 22 C62 38, 50 50, 34 50 C50 50, 62 62, 62 78 C62 62, 74 50, 90 50 C74 50, 62 38, 62 22 Z" fill="url(#wandG)" opacity=".9"/>
        <!-- 左上小四芒星 -->
        <path d="M20 18 C20 21, 17 24, 14 24 C17 24, 20 27, 20 30 C20 27, 23 24, 26 24 C23 24, 20 21, 20 18 Z" fill="#a78bff" opacity=".55"/>
        <!-- 右下小四芒星 -->
        <path d="M22 76 C22 78, 20 80, 18 80 C20 80, 22 82, 22 84 C22 82, 24 80, 26 80 C24 80, 22 78, 22 76 Z" fill="#ffd66b" opacity=".75"/>
        <!-- 装饰小点 -->
        <circle cx="38" cy="30" r="1.6" fill="#7b61ff" opacity=".5"/>
        <circle cx="78" cy="78" r="1.4" fill="#5d86ff" opacity=".5"/>
        <circle cx="14" cy="55" r="1" fill="#a78bff" opacity=".4"/>
      </svg>
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

<div class="modal-mask" id="profileModal">
  <div class="modal-box" style="width:620px;max-width:92vw;max-height:86vh;display:flex;flex-direction:column;padding:24px;">
    <h3 id="profileTitle" style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
      <span id="profileAvatar" style="width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:14px;flex-shrink:0;"></span>
      <span id="profileTitleText">档案</span>
    </h3>

    <!-- 账号管理区 -->
    <div class="acct-mgmt">
      <div class="acct-mgmt-head">
        <div class="acct-mgmt-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 20 c0 -3 2.5 -5.5 6 -5.5 s6 2.5 6 5.5"/><circle cx="17" cy="6" r="2.4"/><path d="M15 14 c1.5 -.5 6 0 6 4"/></svg>
          <span>多账号 <span class="acct-count" id="acctCount">0</span></span>
          <span class="acct-hint" id="acctHint">自动从档案 + 微信会话中识别</span>
        </div>
        <button class="btn-add-acct" id="acctAddBtn" onclick="toggleAcctAddForm()" title="添加账号">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 5 v14"/><path d="M5 12 h14"/></svg>
          <span>添加</span>
        </button>
      </div>
      <div id="acctAddForm" style="display:none;">
        <div class="acct-form-row">
          <label>账号</label>
          <input id="acctNewUsername" placeholder="wxid_xxx 或 username（必填）" />
        </div>
        <div class="acct-form-row">
          <label>显示名</label>
          <input id="acctNewChat" placeholder="可选，不填则用账号名" />
        </div>
        <div class="acct-form-row">
          <label>备注</label>
          <input id="acctNewLabel" placeholder="可选，比如：工作号 / 小号" />
        </div>
        <div class="acct-form-foot">
          <button class="btn-cancel-sm" onclick="cancelAddAcct()">取消</button>
          <button class="btn-ok-sm" id="acctConfirmBtn" onclick="addManualAccount()" disabled>确认添加</button>
        </div>
      </div>
      <div id="acctList" class="acct-list"></div>
    </div>

    <div class="prof-divider"></div>

    <div id="profileContent" style="flex:1;overflow-y:auto;max-height:42vh;"><div class="empty">加载中...</div></div>
    <div class="modal-foot" style="margin-top:12px;">
      <button class="btn-cancel" onclick="document.getElementById('profileModal').classList.remove('open')">关闭</button>
    </div>
  </div>
</div>

<div class="modal-mask" id="suggestModal">
  <div class="modal-box" style="width:540px;max-width:92vw;">
    <h3 id="suggestTitle">建议回复</h3>
    <div id="suggestContent" style="max-height:500px;overflow-y:auto;"><div class="empty">加载中...</div></div>
    <div class="modal-foot" style="margin-top:12px;">
      <button class="btn-cancel" onclick="hideSuggestModal()">关闭</button>
    </div>
  </div>
</div>

"""
