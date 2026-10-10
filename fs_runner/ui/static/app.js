// FS.TestRunner 前端控制台主脚本 (Vanilla JS, 零外部依赖)
let gState = {
  activeTab: "cases",
  caseView: "closed_loop", // closed_loop | excel
  env: "real",
  showBrowser: false,
  slowmo: 0,
  statusFilter: "ALL",
  searchKeyword: "",
  selectedCases: new Set(),
  casesData: [],
  excelData: [],
  rulesData: [],
  running: false,
  currentViewingLog: null,
};

let ws = null;
let pollTimer = null;

// =========================================================================
// 初始化入口
// =========================================================================
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  loadCases();
  loadRules();
  loadHealth();
  loadLogsList();
  loadUiVerify();

  // 绑定控件事件
  document.getElementById("showBrowserCheck").addEventListener("change", (e) => {
    gState.showBrowser = e.target.checked;
  });
  document.getElementById("slowmoSelect").addEventListener("change", (e) => {
    gState.slowmo = parseInt(e.target.value, 10);
  });
});

// =========================================================================
// 标签页切换
// =========================================================================
function switchTab(tabId) {
  gState.activeTab = tabId;
  const tabs = ["cases", "logs", "rules", "health", "ui"];
  tabs.forEach((t) => {
    const elSec = document.getElementById(`tab-${t}`);
    const elBtn = document.getElementById(`menu-${t}`);
    if (elSec) elSec.style.display = t === tabId ? "block" : "none";
    if (elBtn) {
      if (t === tabId) elBtn.classList.add("active");
      else elBtn.classList.remove("active");
    }
  });

  if (tabId === "logs") loadLogsList();
  if (tabId === "rules") loadRules();
  if (tabId === "health") loadHealth();
  if (tabId === "ui") loadUiVerify();
}

// =========================================================================
// 环境切换与视觉分离
// =========================================================================
function onEnvChange() {
  const sel = document.getElementById("envSelect");
  gState.env = sel.value;
  const banner = document.getElementById("sandboxBanner");
  if (gState.env === "sandbox") {
    banner.style.display = "flex";
  } else {
    banner.style.display = "none";
  }
  renderCaseTable();
}

// =========================================================================
// 用例列表与视图切换
// =========================================================================
function switchCaseView(view) {
  gState.caseView = view;
  const btnClosed = document.getElementById("viewClosedLoopBtn");
  const btnExcel = document.getElementById("viewExcelBtn");
  const viewClosed = document.getElementById("closedLoopView");
  const viewExcel = document.getElementById("excelView");

  if (view === "closed_loop") {
    btnClosed.classList.add("active");
    btnExcel.classList.remove("active");
    viewClosed.style.display = "block";
    viewExcel.style.display = "none";
  } else {
    btnClosed.classList.remove("active");
    btnExcel.classList.add("active");
    viewClosed.style.display = "none";
    viewExcel.style.display = "block";
    if (gState.excelData.length === 0) {
      loadExcelCases();
    }
  }
}

async function loadCases() {
  try {
    const res = await fetch("/api/cases");
    const data = await res.json();
    gState.casesData = data.cases || [];
    updateSummaryCounts(data.summary || {});
    renderCaseTable();
  } catch (err) {
    console.error("加载用例失败:", err);
  }
}

function updateSummaryCounts(summary) {
  document.getElementById("countAll").innerText = summary["总计"] || gState.casesData.length;
  document.getElementById("countPass").innerText = summary["通过"] || 0;
  document.getElementById("countFail").innerText = summary["失败"] || 0;
  document.getElementById("countBlock").innerText = summary["阻塞"] || 0;
  document.getElementById("countSkip").innerText = summary["跳过"] || 0;
  document.getElementById("countUnexec").innerText = summary["未执行"] || 0;
}

function filterByStatus(status) {
  gState.statusFilter = status;
  const pills = document.querySelectorAll("#statusFilterPills .stat-filter-btn");
  pills.forEach((p) => p.classList.remove("active"));
  event.target.classList.add("active");
  renderCaseTable();
}

function onSearchCases() {
  gState.searchKeyword = document.getElementById("caseSearchInput").value.trim().toLowerCase();
  renderCaseTable();
}

function renderCaseTable() {
  const tbody = document.getElementById("caseTableBody");
  tbody.innerHTML = "";

  const isSandbox = gState.env === "sandbox";

  const filtered = gState.casesData.filter((c) => {
    if (gState.statusFilter !== "ALL" && c.status !== gState.statusFilter) {
      return false;
    }
    if (gState.searchKeyword) {
      const target = (c.case_id + " " + c.title).toLowerCase();
      if (!target.includes(gState.searchKeyword)) return false;
    }
    return true;
  });

  filtered.forEach((c) => {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid var(--g-border-subtle)";
    if (isSandbox) {
      tr.style.backgroundColor = "#f8fafc";
      tr.style.border = "1.5px dashed #94a3b8";
    }

    const badgeColor = {
      "通过": "background:#e6f4ea; color:#137333;",
      "失败": "background:#fce8e6; color:#c5221f;",
      "阻塞": "background:#fef7e0; color:#b06000;",
      "跳过": "background:#f1f3f4; color:#5f6368;",
      "未执行": "background:#f1f3f4; color:#80868b;",
    }[c.status] || "background:#eee;";

    const isChecked = gState.selectedCases.has(c.case_id) ? "checked" : "";

    tr.innerHTML = `
      <td style="padding:10px 12px;"><input type="checkbox" value="${c.case_id}" ${isChecked} onchange="toggleSelectCase('${c.case_id}', this.checked)"></td>
      <td style="padding:10px 12px; font-weight:600; font-family:var(--g-mono); color:var(--g-blue);">${c.case_id}</td>
      <td style="padding:10px 12px;">
        <div style="font-weight:500;">${c.title}</div>
        ${c.note ? `<div style="font-size:11px; color:var(--g-text-secondary); margin-top:2px;">${c.note}</div>` : ""}
        ${isSandbox ? `<div style="font-size:11px; color:#64748b; font-style:italic; margin-top:2px;">⚠️ 不判通过模式 (未验证业务)</div>` : ""}
      </td>
      <td style="padding:10px 12px;">
        <span style="display:inline-block; padding:3px 8px; border-radius:10px; font-size:11px; font-weight:600; ${badgeColor}">
          ${c.status}
        </span>
      </td>
      <td style="padding:10px 12px; font-size:12px; color:var(--g-text-secondary);">${c.duration_ms ? c.duration_ms + 'ms' : '-'}</td>
      <td style="padding:10px 12px; text-align:center;">
        <button class="btn-icon-run" onclick="runSingleCase('${c.case_id}')" title="单独执行该用例">▶ 执行</button>
        <button class="btn-secondary" style="font-size:11px; padding:2px 6px; margin-left:4px;" onclick="toggleEvidence('${c.case_id}')">证据</button>
      </td>
    `;
    tbody.appendChild(tr);

    // 详情证据抽屉行
    const trEv = document.createElement("tr");
    trEv.id = `ev-row-${c.case_id}`;
    trEv.style.display = "none";
    trEv.style.background = "var(--g-surface-variant)";
    trEv.innerHTML = `
      <td colspan="6" style="padding:10px 16px;">
        <div style="font-size:12px; font-weight:600; margin-bottom:4px;">实测比对证据 (Evidence):</div>
        <pre style="margin:0; font-family:var(--g-mono); font-size:11px; background:#fff; padding:8px 12px; border-radius:4px; border:1px solid var(--g-border); max-height:200px; overflow:auto;">${JSON.stringify(c.evidence || {}, null, 2)}</pre>
      </td>
    `;
    tbody.appendChild(trEv);
  });
}

function toggleEvidence(caseId) {
  const row = document.getElementById(`ev-row-${caseId}`);
  if (row) {
    row.style.display = row.style.display === "none" ? "table-row" : "none";
  }
}

function toggleSelectCase(caseId, isChecked) {
  if (isChecked) gState.selectedCases.add(caseId);
  else gState.selectedCases.delete(caseId);
}

function toggleSelectAll(masterCheckbox) {
  const checked = masterCheckbox.checked;
  const checkboxes = document.querySelectorAll("#caseTableBody input[type='checkbox']");
  checkboxes.forEach((cb) => {
    cb.checked = checked;
    if (checked) gState.selectedCases.add(cb.value);
    else gState.selectedCases.delete(cb.value);
  });
}

// =========================================================================
// 台账 353 行加载
// =========================================================================
async function loadExcelCases() {
  try {
    const res = await fetch("/api/excel-cases");
    const data = await res.json();
    gState.excelData = data || [];
    renderExcelTable();
  } catch (err) {
    console.error("加载台账失败:", err);
  }
}

function renderExcelTable() {
  const tbody = document.getElementById("excelTableBody");
  tbody.innerHTML = "";
  gState.excelData.forEach((row) => {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid var(--g-border-subtle)";
    tr.innerHTML = `
      <td style="padding:8px 10px; font-weight:600; font-family:var(--g-mono);">${row["用例ID"] || ""}</td>
      <td style="padding:8px 10px; color:var(--g-text-secondary);">${row["所属域"] || ""}</td>
      <td style="padding:8px 10px;">${row["子系统"] || ""}</td>
      <td style="padding:8px 10px;">
        <div style="font-weight:500;">${row["测试点"] || ""}</div>
        <div style="font-size:11px; color:var(--g-text-secondary);">${row["预期结果"] || ""}</div>
      </td>
      <td style="padding:8px 10px;">${row["执行方式"] || "手工"}</td>
      <td style="padding:8px 10px;"><span style="display:inline-block; padding:2px 6px; border-radius:4px; font-size:11px; background:#e6f4ea; color:#137333;">${row["执行状态"] || "未测试"}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// =========================================================================
// 测试执行与进程控制
// =========================================================================
async function runSingleCase(caseId) {
  await executeCases([caseId]);
}

async function runSelectedCases() {
  const cases = Array.from(gState.selectedCases);
  if (cases.length === 0) {
    alert("请先勾选用例！");
    return;
  }
  await executeCases(cases);
}

async function runAllCases() {
  await executeCases(null); // null 表示跑全量
}

async function executeCases(casesArray) {
  const payload = {
    cases: casesArray,
    env: gState.env,
    show_browser: gState.showBrowser,
    slowmo: gState.slowmo,
    is_ui_verify: false,
  };

  appendTerminal(`\n🚀 [下发执行指令] 目标用例: ${casesArray ? casesArray.join(", ") : "全量66条"} (环境: ${gState.env}, 显示浏览器: ${gState.showBrowser})\n`);

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const resData = await res.json();
    if (!resData.ok) {
      alert("启动失败: " + resData.msg);
    } else {
      setRunningState(true);
    }
  } catch (err) {
    alert("请求异常: " + err);
  }
}

async function stopRun() {
  if (!confirm("确定要终止正在运行的测试进程吗？")) return;
  try {
    const res = await fetch("/api/stop", { method: "POST" });
    const data = await res.json();
    appendTerminal(`\n⏹️ [停止指令] ${data.msg}\n`);
    setRunningState(false);
  } catch (err) {
    alert("停止失败: " + err);
  }
}

function setRunningState(isRunning) {
  gState.running = isRunning;
  const pill = document.getElementById("statusPill");
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  const stopBtn = document.getElementById("stopBtn");

  if (isRunning) {
    pill.className = "status-pill running";
    dot.innerText = "🟢";
    text.innerText = "执行中";
    stopBtn.disabled = false;
  } else {
    pill.className = "status-pill idle";
    dot.innerText = "●";
    text.innerText = "就绪空闲";
    stopBtn.disabled = true;
  }
}

// =========================================================================
// 实时终端与 WebSocket
// =========================================================================
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/run`;

  try {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      appendTerminal("🔗 [通信通道] 实时 WebSocket 已连接。\n");
    };
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleWsEvent(payload);
      } catch (e) {
        appendTerminal(event.data + "\n");
      }
    };
    ws.onclose = () => {
      startPollingFallback();
    };
    ws.onerror = () => {
      startPollingFallback();
    };
  } catch (e) {
    startPollingFallback();
  }
}

function handleWsEvent(payload) {
  if (payload.type === "log") {
    appendTerminal(payload.data + "\n");
  } else if (payload.type === "step") {
    document.getElementById("stepText").innerText = `[${payload.data.case_id}] ${payload.data.step}`;
  } else if (payload.type === "case_result") {
    const d = payload.data;
    document.getElementById("progressText").innerText = `进度: ${d.current_index}/${d.total_cases}`;
    const pct = Math.floor((d.current_index / d.total_cases) * 100);
    document.getElementById("progressFill").style.width = pct + "%";

    // 局部更新该行状态
    const cObj = gState.casesData.find((x) => x.case_id === d.case_id || (d.case_id && d.case_id.includes(x.case_id)));
    if (cObj) {
      cObj.status = d.status;
      renderCaseTable();
    }
  } else if (payload.type === "finished") {
    setRunningState(false);
    document.getElementById("stepText").innerText = "执行完成";
    loadCases(); // 重新拉取落盘最新数据
  }
}

function startPollingFallback() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch("/api/status");
      const st = await res.json();
      setRunningState(st.running);
      if (st.current_step) document.getElementById("stepText").innerText = st.current_step;
      if (st.total_cases > 0) {
        document.getElementById("progressText").innerText = `进度: ${st.current_index}/${st.total_cases}`;
        document.getElementById("progressFill").style.width = st.percent + "%";
      }
    } catch (e) {}
  }, 1000);
}

function appendTerminal(text) {
  const term = document.getElementById("terminal");
  term.innerText += text;
  term.scrollTop = term.scrollHeight;
}

function clearTerminal() {
  document.getElementById("terminal").innerText = "";
}

function toggleTerminal() {
  const term = document.getElementById("terminal");
  term.style.display = term.style.display === "none" ? "block" : "none";
}

// =========================================================================
// 运行日志模块
// =========================================================================
async function loadLogsList() {
  try {
    const res = await fetch("/api/log-files");
    const list = await res.json();
    const box = document.getElementById("logFileList");
    box.innerHTML = "";

    list.forEach((f) => {
      const item = document.createElement("div");
      item.className = "btn-secondary";
      item.style.padding = "8px 10px";
      item.style.display = "flex";
      item.style.justifyContent = "space-between";
      item.style.alignItems = "center";
      item.style.cursor = "pointer";

      const badgeType = f.type === "audit" ? "🛡️ 审计" : "📊 报告";

      item.innerHTML = `
        <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:210px;">
          <div style="font-weight:500; font-size:12px;">${f.name}</div>
          <div style="font-size:11px; color:var(--g-text-secondary);">${badgeType} · ${f.size_kb} KB</div>
        </div>
      `;
      item.onclick = () => viewLogFile(f.path, f.name);
      box.appendChild(item);
    });
  } catch (err) {
    console.error("加载日志文件列表失败:", err);
  }
}

async function viewLogFile(relPath, fileName) {
  gState.currentViewingLog = relPath;
  document.getElementById("logViewerTitle").innerText = fileName;
  document.getElementById("downloadLogBtn").disabled = false;
  const viewer = document.getElementById("logViewerContent");
  viewer.innerText = "正在载入...";

  try {
    const res = await fetch(`/api/log-files/content?path=${encodeURIComponent(relPath)}`);
    const data = await res.json();
    viewer.innerText = data.content || "（空文件）";
  } catch (err) {
    viewer.innerText = "读取文件失败: " + err;
  }
}

function downloadCurrentLog() {
  if (!gState.currentViewingLog) return;
  window.open(`/api/log-files/content?path=${encodeURIComponent(gState.currentViewingLog)}&download=1`);
}

// =========================================================================
// 业务规则库（只读）
// =========================================================================
async function loadRules() {
  try {
    const res = await fetch("/api/rules");
    const data = await res.json();
    gState.rulesData = data.rules || [];
    renderRulesCards();
  } catch (err) {
    console.error("加载业务规则失败:", err);
  }
}

function onSearchRules() {
  const kw = document.getElementById("ruleSearchInput").value.trim().toLowerCase();
  renderRulesCards(kw);
}

function renderRulesCards(kw = "") {
  const box = document.getElementById("rulesList");
  box.innerHTML = "";

  const filtered = gState.rulesData.filter((r) => {
    if (!kw) return true;
    return (r.id + " " + r.title + " " + r.statement).toLowerCase().includes(kw);
  });

  filtered.forEach((r) => {
    const card = document.createElement("div");
    card.style.background = "var(--g-surface)";
    card.style.border = "1px solid var(--g-border)";
    card.style.borderRadius = "var(--g-radius-md)";
    card.style.padding = "14px 16px";

    const badgeStatus = r.status === "confirmed"
      ? '<span style="background:#e6f4ea; color:#137333; font-size:11px; padding:2px 6px; border-radius:4px; font-weight:600;">Confirmed</span>'
      : '<span style="background:#fef7e0; color:#b06000; font-size:11px; padding:2px 6px; border-radius:4px; font-weight:600;">Suspected</span>';

    const affected = (r.affected_cases || []).map((c) => `<span style="background:#e8f0fe; color:#1a73e8; font-size:11px; padding:2px 6px; border-radius:4px; margin-right:4px;">${c}</span>`).join("");

    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
        <div>
          <span style="font-family:var(--g-mono); font-weight:bold; color:var(--g-blue); font-size:13px;">${r.id}</span>
          <span style="font-size:11px; color:var(--g-text-secondary); margin-left:6px;">[${r.kind}]</span>
        </div>
        ${badgeStatus}
      </div>
      <div style="font-weight:600; font-size:13px; margin-bottom:6px;">${r.title}</div>
      <div style="font-size:12px; color:var(--g-text-primary); line-height:1.5; margin-bottom:8px;">${r.statement}</div>
      ${r.evidence ? `<div style="font-size:11px; color:var(--g-text-secondary); background:var(--g-surface-variant); padding:6px 10px; border-radius:4px; margin-bottom:8px;">实测证据: ${r.evidence}</div>` : ""}
      <div style="font-size:11px; color:var(--g-text-secondary);">受影响用例: ${affected || "无"}</div>
    `;
    box.appendChild(card);
  });
}

// =========================================================================
// 体检总览
// =========================================================================
async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();

    const sum = data.closed_loop_summary || {};
    document.getElementById("healthPassRate").innerText = `${sum["通过"] || 0} / ${sum["总计"] || 66} 通过`;
    document.getElementById("healthRuleCount").innerText = `${data.rule_stats?.total || 57} 条`;
    document.getElementById("healthCreatedText").innerText = data.created_text || "门诊患者净增 0 · 测试挂号净增 0";
  } catch (err) {
    console.error("加载体检大盘失败:", err);
  }
}

// =========================================================================
// 界面巡检 (UI Verify)
// =========================================================================
async function loadUiVerify() {
  try {
    const res = await fetch("/api/ui-verify/latest");
    const data = await res.json();
    renderUiResults(data);
  } catch (err) {
    console.error("加载界面巡检数据失败:", err);
  }
}

function renderUiResults(data) {
  const grid = document.getElementById("uiResultsGrid");
  grid.innerHTML = "";

  const results = data.results || [];
  if (results.length === 0) {
    grid.innerHTML = '<div style="color:var(--g-text-secondary); font-size:13px;">暂无巡检记录，请点击上方「立即执行界面巡检」</div>';
    return;
  }

  results.forEach((r) => {
    const card = document.createElement("div");
    card.style.background = "var(--g-surface)";
    card.style.border = "1px solid var(--g-border)";
    card.style.borderRadius = "var(--g-radius-md)";
    card.style.padding = "14px";

    const badgeColor = r.status === "通过" ? "background:#e6f4ea; color:#137333;" : (r.status === "未执行" ? "background:#f1f3f4; color:#64748b;" : "background:#fce8e6; color:#c5221f;");

    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
        <span style="font-weight:bold; font-family:var(--g-mono); color:var(--g-blue);">${r.case_id}</span>
        <span style="font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600; ${badgeColor}">${r.status}</span>
      </div>
      <div style="font-size:13px; font-weight:500; margin-bottom:6px;">${r.title}</div>
      <div style="font-size:12px; color:var(--g-text-secondary); line-height:1.4;">${r.note || ""}</div>
      <div style="font-size:11px; color:var(--g-text-tertiary); margin-top:8px;">耗时: ${r.duration_ms}ms</div>
    `;
    grid.appendChild(card);
  });
}

async function runUiVerifyNow() {
  const payload = {
    show_browser: gState.showBrowser,
    slowmo: gState.slowmo,
    env: gState.env,
    is_ui_verify: true,
  };

  appendTerminal("\n🖥️ [触发界面巡检] 正在拉起 Chrome 执行真实业务等式对账...\n");
  switchTab("cases"); // 切换到 terminal 查看

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const resData = await res.json();
    if (!resData.ok) {
      alert("启动失败: " + resData.msg);
    } else {
      setRunningState(true);
    }
  } catch (err) {
    alert("请求异常: " + err);
  }
}
