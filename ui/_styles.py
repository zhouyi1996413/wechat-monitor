STYLES = r"""
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
.logo{width:64px;height:64px;border-radius:20px;flex-shrink:0;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 24px rgba(123,97,255,.25)}
.logo svg{width:38px;height:38px;fill:#fff}

/* Stat card with icon circle */
.stat{display:flex;flex-direction:column;gap:8px;position:relative;overflow:hidden}
.stat-head{display:flex;align-items:center;gap:12px;margin-bottom:4px}
.stat-icon{width:48px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 4px 12px rgba(0,0,0,.06);color:#fff}
.stat-icon svg{width:24px;height:24px;stroke:currentColor;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.stat-icon.purple{background:linear-gradient(135deg,#a78bff,#7b61ff)}
.stat-icon.green{background:linear-gradient(135deg,#5ed3a8,#22b07d)}
.stat-icon.orange{background:linear-gradient(135deg,#ffb86b,#ff8a3d)}
.stat-title{font-size:13px;color:var(--muted);font-weight:500}
.stat-big{font-size:38px;font-weight:700;color:var(--p1);line-height:1;margin-top:auto}
.stat-big .unit{font-size:14px;color:var(--muted);font-weight:500;margin-left:4px}

/* Polling card with magic wand illustration */
.poll{position:relative;overflow:hidden}
.poll-illust{position:absolute;right:20px;top:50%;transform:translateY(-50%);width:90px;height:90px;opacity:.85;pointer-events:none}
.poll-illust svg{width:100%;height:100%}

/* Analyze button SVG icon */
.btn-analyze svg{width:13px;height:13px;stroke:var(--p1);fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}

/* Close button X icon */
.btn-rm svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}

/* 多账号主子分支 */
.contact-group{position:relative}
.contact-group .group-head{padding:14px 0;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.contact-group .group-head:last-child{border-bottom:none}
.contact-group.has-sub{border-bottom:1px solid var(--line)}
.contact-group .caret{width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;color:var(--muted);transition:transform .2s;cursor:pointer;flex-shrink:0;margin-right:2px}
.contact-group.has-sub.expanded .caret{transform:rotate(90deg)}
.contact-group .caret svg{width:14px;height:14px}
.contact-group .acct-badge{font-size:10px;background:rgba(123,97,255,.1);color:var(--p1);padding:2px 6px;border-radius:999px;margin-left:6px;font-weight:500}
.sub-list{display:none;padding:4px 0 8px 30px;border-bottom:1px solid var(--line)}
.contact-group.has-sub.expanded .sub-list{display:block}
.sub-row{display:flex;align-items:center;justify-content:space-between;padding:7px 6px;gap:8px;border-radius:8px;transition:background .15s}
.sub-row:hover{background:rgba(123,97,255,.04)}
.sub-row .sub-name{font-size:12.5px;color:var(--txt);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.sub-row .sub-acts{display:flex;align-items:center;gap:4px;flex-shrink:0}
.sub-row .btn-sm{padding:4px 9px;font-size:11px}
.sub-row .btn-sm svg{width:11px;height:11px}

/* 展开/折叠按钮（多账号右侧）和分析按钮同样的尺寸风格 */
.btn-toggle{background:rgba(123,97,255,.08);color:var(--p1);border:1px solid rgba(123,97,255,.2);display:inline-flex;align-items:center;gap:4px;cursor:pointer;font-family:inherit;font-weight:500}
.btn-toggle:hover{background:rgba(123,97,255,.14)}
.btn-toggle svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
.sub-row .btn-rm{padding:4px}
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
.logs-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.logs-head h3{margin-bottom:0}
.log-filter-wrap{position:relative}
.log-filter-btn{background:transparent;border:none;cursor:pointer;color:var(--muted);padding:4px;border-radius:6px;display:flex;align-items:center;transition:all .15s}
.log-filter-btn:hover{color:var(--txt);background:var(--input-bg)}
.log-filter-dropdown{display:none;position:absolute;right:0;top:100%;margin-top:4px;background:var(--modal-bg);border:1px solid var(--line);border-radius:10px;padding:6px 10px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:20;min-width:90px}
.log-filter-dropdown.open{display:flex;flex-direction:column;gap:2px}
.log-filter-item{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--txt);cursor:pointer;padding:3px 4px;border-radius:4px;transition:background .1s}
.log-filter-item:hover{background:var(--input-bg)}
.log-filter-item input[type="checkbox"]{accent-color:var(--p1);margin:0;width:14px;height:14px}
.log{display:grid;grid-template-columns:72px 56px 1fr;gap:8px;padding:8px 0;border-bottom:1px solid var(--line);font-size:12px;align-items:baseline}
.log:last-child{border-bottom:none}
.log-time{color:#B0B8C9;font-family:'SF Mono','Fira Code',monospace;font-size:11px}
.log-level{padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;text-align:center}
.log-level.info{background:rgba(123,97,255,.1);color:var(--p1)}
.log-level.warn{background:rgba(251,191,36,.12);color:#d97706}
.log-level.error{background:rgba(248,113,113,.1);color:#ef4444}
.log-msg{color:#6b7280;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.log-icon{display:inline-flex;align-items:center;vertical-align:-2px;margin-right:3px;color:#94a3b8}
.log-icon svg{flex-shrink:0}
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
.prof-divider{height:1px;background:var(--line);margin:16px 0 12px}

/* Account management (in profile modal) */
.acct-mgmt{background:var(--input-bg);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin-bottom:4px}
.acct-mgmt-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.acct-mgmt-title{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--txt)}
.acct-mgmt-title svg{color:var(--p1);flex-shrink:0}
.acct-count{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:18px;padding:0 6px;background:rgba(123,97,255,.12);color:var(--p1);border-radius:999px;font-size:11px;font-weight:600;margin-left:2px}
.acct-hint{font-size:11px;color:var(--muted);font-weight:400;margin-left:6px}
.btn-add-acct{display:flex;align-items:center;gap:4px;height:28px;padding:0 10px;border:1px dashed var(--line);background:transparent;border-radius:8px;font-size:12px;font-weight:500;color:var(--p1);cursor:pointer;font-family:inherit;transition:all .2s}
.btn-add-acct:hover{border-color:var(--p1);border-style:solid;background:rgba(123,97,255,.06)}
.btn-add-acct svg{flex-shrink:0}
.acct-list{display:flex;flex-direction:column;gap:6px}
.acct-item{display:flex;align-items:center;gap:10px;padding:8px 10px;background:var(--card);border:1px solid var(--line);border-radius:10px;transition:all .15s}
.acct-item:hover{border-color:rgba(123,97,255,.3)}
.acct-item.manual{border-left:3px solid var(--p1)}
.acct-item-info{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.acct-item-name{font-size:13px;font-weight:500;color:var(--txt);display:flex;align-items:center;gap:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.acct-item-name .src-tag{font-size:9px;padding:1px 5px;border-radius:4px;font-weight:600;flex-shrink:0}
.acct-item-name .src-auto{background:rgba(34,176,125,.12);color:#22b07d}
.acct-item-name .src-alias{background:rgba(93,134,255,.12);color:#5d86ff}
.acct-item-name .src-manual{background:rgba(123,97,255,.15);color:var(--p1)}
.acct-item-name .primary-star{color:#f5b73d;flex-shrink:0}
.acct-item-meta{font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.acct-item-acts{display:flex;align-items:center;gap:4px;flex-shrink:0}
.acct-act-btn{width:26px;height:26px;border:1px solid transparent;background:transparent;border-radius:7px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--muted);transition:all .15s}
.acct-act-btn:hover{border-color:var(--line);color:var(--txt);background:var(--input-bg)}
.acct-act-btn.del:hover{color:#e35b6a;background:rgba(227,91,106,.08)}
.acct-act-btn svg{width:13px;height:13px}
/* 拖拽手柄 */
.drag-handle{display:flex;align-items:center;justify-content:center;width:20px;height:20px;color:var(--muted);cursor:grab;flex-shrink:0;opacity:.5;transition:opacity .15s;margin-right:2px;border-radius:4px;user-select:none;-webkit-user-select:none}
.drag-handle:hover{opacity:1;background:rgba(123,97,255,.06)}
.drag-handle:active{cursor:grabbing}
.sub-drag-handle{width:16px;height:16px;margin-right:0}
.sub-drag-handle svg{width:12px;height:12px}
/* 拖拽中 */
.contact.dragging,.contact-group.dragging,.sub-row.dragging{opacity:.4}
.drag-placeholder{border:2px dashed var(--p1);border-radius:12px;background:rgba(123,97,255,.04);margin:4px 0;transition:none}
.acct-act-btn.ok{color:#22b07d}
.acct-act-btn.ok:hover{color:#1e9768;background:rgba(34,176,125,.1)}
.acct-act-btn.cancel{color:var(--muted)}
.acct-act-btn.cancel:hover{color:#e35b6a;background:rgba(227,91,106,.06)}
.acct-rename-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.acct-rename-input{flex:1;min-width:120px;height:26px;border:1px solid var(--p1);background:var(--card);border-radius:6px;padding:0 8px;font-size:12px;font-family:inherit;color:var(--txt);outline:none}
.acct-rename-input:focus{border-color:var(--p1);box-shadow:0 0 0 2px rgba(123,97,255,.12)}
.acct-empty{text-align:center;padding:14px;font-size:12px;color:var(--muted)}
.acct-form-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.acct-form-row label{width:54px;font-size:11px;color:var(--muted);font-weight:500;flex-shrink:0;margin:0}
.acct-form-row input{flex:1;height:34px;border:1px solid var(--line);background:var(--card);border-radius:8px;padding:0 10px;font-size:12px;font-family:inherit;color:var(--txt);outline:none;transition:border-color .2s}
.acct-form-row input:focus{border-color:var(--p1)}
.acct-form-foot{display:flex;justify-content:flex-end;gap:6px;margin-top:4px;padding-top:8px;border-top:1px dashed var(--line)}
.btn-cancel-sm,.btn-ok-sm{height:30px;padding:0 12px;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit;border:1px solid var(--line);transition:all .15s}
.btn-cancel-sm{background:transparent;color:var(--muted)}
.btn-cancel-sm:hover{color:var(--txt)}
.btn-ok-sm{background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;border:none;box-shadow:0 2px 8px rgba(123,97,255,.25)}
.btn-ok-sm:disabled{opacity:.4;cursor:not-allowed;box-shadow:none}
.acct-mgmt-head .primary-tip{font-size:11px;color:var(--muted);margin-right:6px}
.profile-modal-grid{position:relative}
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
"""
