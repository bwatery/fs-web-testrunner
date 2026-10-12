// FS.TestRunner 前端控制台主脚本 (Vanilla JS, 零外部依赖)
let gState = {
  activeTab: "cases",
  env: "real",
  showBrowser: false,
  slowmo: 0,
  statusFilter: "ALL",
  searchKeyword: "",
  moduleFilter: "ALL",
  collapsedModules: new Set(),
  selectedCases: new Set(),
  casesData: [],
  excelData: [],
  rulesData: [],
  running: false,
  currentViewingLog: null,
  isTermFloating: false,
};

function getCaseModule(caseId) {
  if (!caseId) return "OTHER";
  for (const prefix of ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]) {
    if (caseId.startsWith(prefix)) return prefix;
  }
  if (caseId.startsWith("UI-") || caseId.startsWith("UI")) return "UI";
  return "OTHER";
}

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
  const slowmoEl = document.getElementById("slowmoSelect");
  if (slowmoEl) {
    slowmoEl.addEventListener("change", (e) => {
      gState.slowmo = parseInt(e.target.value, 10);
    });
  }
});

// =========================================================================
// 标签页与领域切换
// =========================================================================
function switchDomain(domainKey) {
  // Activity Rail 项高亮
  const railItems = {
    cases: "railItemCases",
    excel: "railItemExcel",
    rules: "railItemRules",
    health: "railItemHealth",
    screen: "railItemScreen",
    logs: "railItemLogs",
  };
  Object.keys(railItems).forEach((k) => {
    const el = document.getElementById(railItems[k]);
    if (el) {
      if (k === domainKey) el.classList.add("active");
      else el.classList.remove("active");
    }
  });

  switchTab(domainKey);
}

function switchTab(tabKey) {
  gState.activeTab = tabKey;
  const tabs = ["cases", "excel", "rules", "health", "screen", "logs"];

  // 顶栏 TabBar 高亮
  const tabItems = document.querySelectorAll("#tabBar .tab-item");
  tabItems.forEach((item) => {
    if (item.getAttribute("data-tab") === `tab-${tabKey}`) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  // Rail 栏同步高亮
  const railItems = {
    cases: "railItemCases",
    excel: "railItemExcel",
    rules: "railItemRules",
    health: "railItemHealth",
    screen: "railItemScreen",
    logs: "railItemLogs",
  };
  Object.keys(railItems).forEach((k) => {
    const el = document.getElementById(railItems[k]);
    if (el) {
      if (k === tabKey) el.classList.add("active");
      else el.classList.remove("active");
    }
  });

  // 主内容区显示控制
  tabs.forEach((t) => {
    const elSec = document.getElementById(`tab-${t}`);
    if (elSec) {
      if (t === tabKey) elSec.classList.add("active");
      else elSec.classList.remove("active");
    }
  });

  // 侧栏 Drawer 显示控制：在用例页展示，其他页自动折叠
  const drawer = document.getElementById("caseDrawer");
  if (drawer) {
    if (tabKey === "cases") {
      drawer.classList.remove("collapsed");
    } else {
      drawer.classList.add("collapsed");
    }
  }

  // 按需加载数据
  if (tabKey === "excel" && gState.excelData.length === 0) loadExcelCases();
  if (tabKey === "logs") loadLogsList();
  if (tabKey === "rules" && gState.rulesData.length === 0) loadRules();
  if (tabKey === "health") loadHealth();
  if (tabKey === "screen") loadUiVerify();
}

// 侧栏展开/收起切换
function toggleDrawer() {
  const drawer = document.getElementById("caseDrawer");
  if (drawer) {
    drawer.classList.toggle("collapsed");
  }
}

// =========================================================================
// 环境切换与视觉分离
// =========================================================================
function onEnvChange() {
  const sel = document.getElementById("envModeSelect");
  gState.env = sel.value;
  const banner = document.getElementById("sandboxBanner");
  if (banner) {
    if (gState.env === "sandbox") {
      banner.style.display = "flex";
    } else {
      banner.style.display = "none";
    }
  }
  renderCaseTable();
}

// =========================================================================
// 浏览器可见性开关
// =========================================================================
function onBrowserCheckChange(cb) {
  gState.showBrowser = cb.checked;
  const txtMode = document.getElementById("headlessSwitchModeText");
  const txtTip = document.getElementById("headlessSwitchTipText");
  if (gState.showBrowser) {
    if (txtMode) txtMode.innerHTML = `<svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg> 窗口模式`;
    if (txtTip) txtTip.innerText = `(桌面可见实操)`;
    showToast("浏览器显示开启", "执行时将在桌面弹出独立 Chrome 窗口实时展现操作流程", "info");
  } else {
    if (txtMode) txtMode.innerHTML = `<svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg> 后台模式`;
    if (txtTip) txtTip.innerText = `(隐形快速执行)`;
  }
}

// =========================================================================
// 用例列表与分类树加载
// =========================================================================
async function loadCases() {
  try {
    const res = await fetch("/api/cases");
    const data = await res.json();
    gState.casesData = data.cases || [];

    // 默认全选
    gState.selectedCases.clear();
    gState.casesData.forEach((c) => gState.selectedCases.add(c.case_id));

    updateSummaryCounts(data.summary || {});
    renderDrawerCategories();
    renderCaseTable();
  } catch (err) {
    console.error("加载用例失败:", err);
  }
}

function updateSummaryCounts(summary) {
  const total = summary["总计"] || gState.casesData.length || 66;
  const pass = summary["通过"] || 0;
  const fail = summary["失败"] || 0;
  const block = summary["阻塞"] || 0;
  const skip = summary["跳过"] || 0;
  const unexec = summary["未执行"] || 0;

  const setT = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.innerText = v;
  };

  setT("kpiTotal", total);
  setT("totalTestsCount", total);
  setT("totalCountBadge", total);
  setT("countPass", pass);
  setT("countFail", fail);
  setT("countBlock", block);
  setT("countSkip", skip);
  setT("countUnexec", unexec);

  const badgeCases = document.getElementById("railBadgeCases");
  if (badgeCases) badgeCases.innerText = total;
}

// 渲染左侧分类树
function renderDrawerCategories() {
  const container = document.getElementById("drawerNavContainer");
  if (!container) return;
  container.innerHTML = "";

  const moduleMap = {
    "L0": "门诊挂号 (L0)",
    "L1": "门诊收费 (L1)",
    "L2": "门诊医生 (L2)",
    "L3": "药房发药 (L3)",
    "L4": "住院护士 (L4)",
    "L5": "住院医生 (L5)",
    "L6": "住院收费 (L6)",
    "UI": "界面巡检 (UI)",
  };

  // 按模块分组
  const groups = {};
  Object.keys(moduleMap).forEach((k) => (groups[k] = []));
  groups["OTHER"] = [];

  gState.casesData.forEach((c) => {
    const mod = getCaseModule(c.case_id);
    c._module = mod;          // 供 renderCaseTable 按模块筛选
    if (groups[mod]) {
      groups[mod].push(c);
    } else {
      groups["OTHER"].push(c);
    }
  });

  Object.keys(groups).forEach((key) => {
    const list = groups[key];
    if (list.length === 0) return;
    const catName = moduleMap[key] || "其他用例";
    const isModuleActive = gState.moduleFilter === key;
    const isCollapsed = gState.collapsedModules && gState.collapsedModules.has(key);

    const wrap = document.createElement("div");
    wrap.className = "nav-cat-wrap";

    const header = document.createElement("div");
    header.className = "nav-cat-header" + (isModuleActive ? " active" : "") + (isCollapsed ? " collapsed" : "");
    header.style.cursor = "pointer";
    if (isModuleActive) {
      header.style.backgroundColor = "var(--g-blue-surface)";
      header.style.color = "var(--g-blue)";
      header.style.fontWeight = "600";
    }

    header.innerHTML = `
      <div style="display:flex; align-items:center; gap:6px; overflow:hidden;">
        <span class="arrow" style="cursor:pointer; padding:2px 4px;" title="折叠/展开分类">▾</span>
        <input type="checkbox" class="cat-select-chk" checked title="勾选/取消该分类全部用例">
        <span class="cat-name" style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="只看该模块（再点一次回到全部）">${catName}</span>
      </div>
      <span class="nav-pill" style="${isModuleActive ? 'background:var(--g-blue); color:#fff; font-weight:600;' : ''}">${list.length}</span>
    `;

    const subList = document.createElement("div");
    subList.className = "nav-sub-list" + (isCollapsed ? " collapsed" : "");

    list.forEach((c) => {
      const item = document.createElement("div");
      item.className = "nav-sub-item";
      const dotCls = c.status === "通过" ? "pass" : (c.status === "失败" ? "fail" : "");
      item.innerHTML = `
        <span class="nav-status-dot ${dotCls}"></span>
        <span style="font-family:var(--g-mono); font-size:11px; font-weight:500;">${c.case_id}</span>
      `;
      item.onclick = (e) => {
        e.stopPropagation();
        document.querySelectorAll(".nav-sub-item").forEach((el) => el.classList.remove("active"));
        item.classList.add("active");
        gState.moduleFilter = "ALL"; // 清除模块筛选
        gState.searchKeyword = c.case_id;
        const inp = document.getElementById("searchInput");
        if (inp) inp.value = c.case_id;
        renderDrawerCategories();
        renderCaseTable();
      };
      subList.appendChild(item);
    });

    // 1. 箭头点击：仅折叠/展开，不触发筛选，右侧列表不变
    const arrowEl = header.querySelector(".arrow");
    if (arrowEl) {
      arrowEl.onclick = (e) => {
        e.stopPropagation();
        const willCollapse = !header.classList.contains("collapsed");
        header.classList.toggle("collapsed");
        subList.classList.toggle("collapsed");
        if (!gState.collapsedModules) gState.collapsedModules = new Set();
        if (willCollapse) {
          gState.collapsedModules.add(key);
        } else {
          gState.collapsedModules.delete(key);
        }
      };
    }

    // 2. 复选框点击：仅改变勾选，不触发筛选，右侧列表不变
    const chk = header.querySelector(".cat-select-chk");
    if (chk) {
      chk.onclick = (e) => {
        e.stopPropagation();
      };
      chk.onchange = (e) => {
        const checked = e.target.checked;
        list.forEach((c) => {
          if (checked) gState.selectedCases.add(c.case_id);
          else gState.selectedCases.delete(c.case_id);
        });
        const selBadge = document.getElementById("selCountBadge");
        if (selBadge) selBadge.innerText = gState.selectedCases.size;
        // 同步更新表格里已有的勾选框，避免重画整个列表
        const tblChecks = document.querySelectorAll("#caseTableBody input[type='checkbox']");
        tblChecks.forEach((cb) => {
          if (gState.selectedCases.has(cb.value)) cb.checked = true;
          else cb.checked = false;
        });
      };
    }

    // 3. 模块行整体点击（名字、数量药丸、整行空白处）：筛选该模块，再点一次回到全部
    header.onclick = (e) => {
      // 若点击目标是 input 或 arrow，已由各自的 stopPropagation 处理；此防线兜底
      if (e.target.tagName.toLowerCase() === "input" || e.target.classList.contains("arrow")) {
        return;
      }
      gState.moduleFilter = gState.moduleFilter === key ? "ALL" : key;
      gState.searchKeyword = ""; // 模块筛选与搜索关键字互斥，清空搜索
      const inp = document.getElementById("searchInput");
      if (inp) inp.value = "";
      document.querySelectorAll(".nav-sub-item").forEach((el) => el.classList.remove("active"));
      renderDrawerCategories(); // 重画以更新高亮
      renderCaseTable();
    };

    wrap.appendChild(header);
    wrap.appendChild(subList);
    container.appendChild(wrap);
  });
}

function collapseAllCategories() {
  document.querySelectorAll(".nav-cat-header").forEach((h) => h.classList.add("collapsed"));
  document.querySelectorAll(".nav-sub-list").forEach((l) => l.classList.add("collapsed"));
  if (!gState.collapsedModules) gState.collapsedModules = new Set();
  ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "UI", "OTHER"].forEach((k) => gState.collapsedModules.add(k));
}

function expandAllCategories() {
  document.querySelectorAll(".nav-cat-header").forEach((h) => h.classList.remove("collapsed"));
  document.querySelectorAll(".nav-sub-list").forEach((l) => l.classList.remove("collapsed"));
  if (gState.collapsedModules) gState.collapsedModules.clear();
}

// 状态过滤
function filterByStatus(status) {
  gState.statusFilter = status;
  // 「全部」= 回到全量：把模块筛选与搜索关键字一并清掉。
  // 否则点过侧栏用例 / 分类之后再点「全部」仍然被过滤，界面看着就是"切不回全部"（用户实测反馈）。
  if (status === "ALL") {
    gState.moduleFilter = "ALL";
    gState.searchKeyword = "";
    const inp = document.getElementById("searchInput");
    if (inp) inp.value = "";
    document.querySelectorAll(".nav-sub-item").forEach((el) => el.classList.remove("active"));
    renderDrawerCategories();
  }
  const btns = [
    { id: "btnFilterAll", s: "ALL" },
    { id: "btnFilterPass", s: "通过" },
    { id: "btnFilterFail", s: "失败" },
    { id: "btnFilterBlock", s: "阻塞" },
    { id: "btnFilterSkip", s: "跳过" },
    { id: "btnFilterUnexec", s: "未执行" },
  ];
  btns.forEach((b) => {
    const el = document.getElementById(b.id);
    if (el) {
      if (b.s === status) {
        el.className = "g-btn g-btn-tonal active";
      } else {
        el.className = "g-btn g-btn-outlined";
      }
    }
  });
  renderCaseTable();
}

function onSearchCases() {
  const inp = document.getElementById("searchInput");
  gState.searchKeyword = inp ? inp.value.trim().toLowerCase() : "";
  if (gState.searchKeyword) {
    gState.moduleFilter = "ALL"; // 模块筛选与搜索关键字互斥
    renderDrawerCategories();
  }
  renderCaseTable();
}

// =========================================================================
// 核心表格渲染
// =========================================================================
function renderCaseTable() {
  const tbody = document.getElementById("caseTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const isSandbox = gState.env === "sandbox";

  const filtered = gState.casesData.filter((c) => {
    // 按模块筛选（点侧栏分类名/模块行进入，再点一次或点「全部」退出）
    const cModule = c._module || getCaseModule(c.case_id);
    if (gState.moduleFilter !== "ALL" && cModule !== gState.moduleFilter) {
      return false;
    }
    if (gState.statusFilter !== "ALL" && c.status !== gState.statusFilter) {
      return false;
    }
    if (gState.searchKeyword) {
      const target = (c.case_id + " " + (c.title || "")).toLowerCase();
      // 两侧都要转小写：用例ID 是大写（L6-015），只转一侧会恒不匹配 →
      // 侧边栏点用例后右侧表格空白、搜索框输大写搜不到
      if (!target.includes(String(gState.searchKeyword).toLowerCase())) return false;
    }
    return true;
  });

  // 更新计数指示器
  const cntFilterEl = document.getElementById("filteredCasesCount");
  if (cntFilterEl) cntFilterEl.innerText = `(显示 ${filtered.length} 项)`;
  const selBadge = document.getElementById("selCountBadge");
  if (selBadge) selBadge.innerText = gState.selectedCases.size;

  filtered.forEach((c) => {
    const tr = document.createElement("tr");
    if (isSandbox) {
      tr.style.backgroundColor = "#f8fafc";
      tr.style.border = "1.5px dashed #94a3b8";
    }

    let statusHtml = "";
    if (c.status === "通过") {
      statusHtml = '<span class="status-chip passed">通过</span>';
    } else if (c.status === "失败") {
      statusHtml = '<span class="status-chip failed">失败</span>';
    } else if (c.status === "阻塞") {
      statusHtml = '<span class="status-chip running" style="color:var(--g-yellow); background:var(--g-yellow-surface);">阻塞</span>';
    } else if (c.status === "跳过") {
      statusHtml = '<span class="status-chip pending">跳过</span>';
    } else {
      statusHtml = '<span class="status-chip pending">未执行</span>';
    }

    const isChecked = gState.selectedCases.has(c.case_id) ? "checked" : "";

    tr.innerHTML = `
      <td style="text-align:center;">
        <input type="checkbox" value="${c.case_id}" ${isChecked} onchange="toggleSelectCase('${c.case_id}', this.checked)">
      </td>
      <td style="font-weight:600; font-family:var(--g-mono); color:var(--g-blue);">${c.case_id}</td>
      <td>
        <div style="font-weight:500;">${c.title}</div>
        ${c.note ? `<div style="font-size:11px; color:var(--g-text-secondary); margin-top:2px;">${c.note}</div>` : ""}
        ${isSandbox ? `<div style="font-size:11px; color:#64748b; font-style:italic; margin-top:2px;">⚠️ 不判通过模式 (未验证业务)</div>` : ""}
      </td>
      <td>${statusHtml}</td>
      <td style="font-size:12px; color:var(--g-text-secondary);">${c.duration_ms ? c.duration_ms + 'ms' : '-'}</td>
      <td style="text-align:center;">
        <button class="g-btn g-btn-tonal" style="height:24px; font-size:11px; padding:0 8px;" onclick="runSingleCase('${c.case_id}')" title="单独执行该用例">▶ 执行</button>
        <button class="g-btn g-btn-outlined" style="height:24px; font-size:11px; padding:0 8px; margin-left:4px;" onclick="toggleEvidence('${c.case_id}')">证据</button>
      </td>
    `;
    tbody.appendChild(tr);

    // 详情证据抽屉行
    const trEv = document.createElement("tr");
    trEv.id = `ev-row-${c.case_id}`;
    trEv.style.display = "none";
    trEv.innerHTML = `
      <td colspan="6" style="padding:10px 16px; background:var(--g-surface-variant);">
        <div style="font-size:12px; font-weight:600; margin-bottom:4px; color:var(--g-text-primary);">实测比对证据 (Evidence):</div>
        <pre style="margin:0; font-family:var(--g-mono); font-size:11px; background:var(--g-surface); padding:8px 12px; border-radius:4px; border:1px solid var(--g-border); max-height:220px; overflow:auto;">${JSON.stringify(c.evidence || {}, null, 2)}</pre>
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
  const selBadge = document.getElementById("selCountBadge");
  if (selBadge) selBadge.innerText = gState.selectedCases.size;
}

function toggleSelectAll(masterCheckbox) {
  const checked = masterCheckbox.checked;
  const checkboxes = document.querySelectorAll("#caseTableBody input[type='checkbox']");
  checkboxes.forEach((cb) => {
    cb.checked = checked;
    if (checked) gState.selectedCases.add(cb.value);
    else gState.selectedCases.delete(cb.value);
  });
  const selBadge = document.getElementById("selCountBadge");
  if (selBadge) selBadge.innerText = gState.selectedCases.size;
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
  if (!tbody) return;
  tbody.innerHTML = "";
  gState.excelData.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:600; font-family:var(--g-mono);">${row["用例ID"] || ""}</td>
      <td style="color:var(--g-text-secondary);">${row["所属域"] || ""}</td>
      <td>${row["子系统"] || ""}</td>
      <td>
        <div style="font-weight:500;">${row["测试点"] || ""}</div>
        <div style="font-size:11px; color:var(--g-text-secondary);">${row["预期结果"] || ""}</div>
      </td>
      <td>${row["执行方式"] || "手工"}</td>
      <td><span class="status-chip passed">${row["执行状态"] || "未测试"}</span></td>
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
    showToast("提示", "请先在用例列表中勾选至少一条用例！", "warning");
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

  appendTerminal(`\n🚀 [下发执行指令] 目标用例: ${casesArray ? casesArray.join(", ") : "全量66条"} (环境: ${gState.env}, 显示浏览器: ${gState.showBrowser}, 慢放: ${gState.slowmo}ms)\n`);

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const resData = await res.json();
    if (!resData.ok) {
      showToast("启动失败", resData.msg, "danger");
    } else {
      setRunningState(true);
      showToast("开始执行", `测试已启动 (${casesArray ? casesArray.length + "条" : "全量66条"})`, "run");
    }
  } catch (err) {
    showToast("请求异常", String(err), "danger");
  }
}

async function stopRun() {
  if (!confirm("确定要终止正在运行的测试进程吗？")) return;
  try {
    const res = await fetch("/api/stop", { method: "POST" });
    const data = await res.json();
    appendTerminal(`\n⏹️ [停止指令] ${data.msg}\n`);
    setRunningState(false);
    showToast("已停止", data.msg, "warning");
  } catch (err) {
    showToast("停止失败", String(err), "danger");
  }
}

function setRunningState(isRunning) {
  gState.running = isRunning;
  const pill = document.getElementById("statusPill");
  const stopBtn = document.getElementById("btnStop");
  const runSelBtn = document.getElementById("btnRunSelected");
  const runAllBtn = document.getElementById("btnRunAll");

  if (isRunning) {
    if (pill) {
      pill.className = "status-chip running";
      pill.innerText = "● 执行中";
    }
    if (stopBtn) stopBtn.disabled = false;
    if (runSelBtn) runSelBtn.disabled = true;
    if (runAllBtn) runAllBtn.disabled = true;
  } else {
    if (pill) {
      pill.className = "status-chip pending";
      pill.innerText = "就绪空闲";
    }
    if (stopBtn) stopBtn.disabled = true;
    if (runSelBtn) runSelBtn.disabled = false;
    if (runAllBtn) runAllBtn.disabled = false;
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
    const stepEl = document.getElementById("stepText");
    if (stepEl) stepEl.innerText = `[${payload.data.case_id}] ${payload.data.step}`;
  } else if (payload.type === "case_result") {
    const d = payload.data;
    const progText = document.getElementById("progressText");
    if (progText) progText.innerText = `进度: ${d.current_index}/${d.total_cases}`;
    const pct = Math.floor((d.current_index / d.total_cases) * 100);
    const progFill = document.getElementById("progressFill");
    if (progFill) progFill.style.width = Math.min(pct, 100) + "%";

    // 局部更新行状态
    const cObj = gState.casesData.find((x) => x.case_id === d.case_id || (d.case_id && d.case_id.includes(x.case_id)));
    if (cObj) {
      cObj.status = d.status;
      renderCaseTable();
    }
  } else if (payload.type === "finished") {
    setRunningState(false);
    const stepEl = document.getElementById("stepText");
    if (stepEl) stepEl.innerText = "执行完成";
    const progFill = document.getElementById("progressFill");
    if (progFill) progFill.style.width = "100%";
    loadCases(); // 重新拉取落盘最新数据
    showToast("执行完成", "本次自动化测试批次已结束，报告与审计已落盘", "success");
  }
}

function startPollingFallback() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch("/api/status");
      const st = await res.json();
      setRunningState(st.running);
      if (st.current_step) {
        const stepEl = document.getElementById("stepText");
        if (stepEl) stepEl.innerText = st.current_step;
      }
      if (st.total_cases > 0) {
        const progText = document.getElementById("progressText");
        if (progText) progText.innerText = `进度: ${st.current_index}/${st.total_cases}`;
        const progFill = document.getElementById("progressFill");
        if (progFill) progFill.style.width = Math.min(st.percent, 100) + "%";
      }
    } catch (e) {}
  }, 1000);
}

function appendTerminal(text) {
  const term = document.getElementById("terminal");
  if (!term) return;

  const div = document.createElement("div");
  div.className = "t-line";
  if (text.includes("ERROR") || text.includes("失败")) div.className += " ERROR";
  else if (text.includes("WARN") || text.includes("⚠️")) div.className += " WARN";
  else if (text.includes("SUCCESS") || text.includes("通过") || text.includes("✅")) div.className += " SUCCESS";
  else div.className += " INFO";

  div.innerText = text.replace(/[\r\n]+$/, "");
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;

  // 更新顶部简报行
  const latestEl = document.getElementById("termLatestLine");
  if (latestEl) latestEl.innerText = div.innerText;
}

function clearTerminal() {
  const term = document.getElementById("terminal");
  if (term) term.innerHTML = '<div class="t-line INFO">[就绪] FS.TestRunner 控制台已挂载，等待执行指令...</div>';
  const latestEl = document.getElementById("termLatestLine");
  if (latestEl) latestEl.innerText = "";
}

function toggleTerminalDrawer() {
  const drawer = document.getElementById("termDrawer");
  const btn = document.getElementById("btnMinTerm");
  if (drawer) {
    drawer.classList.toggle("collapsed");
    if (btn) btn.innerText = drawer.classList.contains("collapsed") ? "展开" : "收起";
  }
}

function toggleTerminalFloat() {
  const drawer = document.getElementById("termDrawer");
  const btn = document.getElementById("btnToggleFloat");
  if (drawer) {
    drawer.classList.toggle("floating");
    if (btn) btn.innerText = drawer.classList.contains("floating") ? "停靠" : "悬浮";
  }
}

// =========================================================================
// 运行日志模块
// =========================================================================
async function loadLogsList() {
  try {
    const res = await fetch("/api/log-files");
    const list = await res.json();
    const box = document.getElementById("logFileList");
    if (!box) return;
    box.innerHTML = "";

    list.forEach((f) => {
      const item = document.createElement("div");
      item.className = "g-btn g-btn-outlined";
      item.style.padding = "8px 12px";
      item.style.height = "auto";
      item.style.display = "flex";
      item.style.justifyContent = "space-between";
      item.style.alignItems = "center";
      item.style.cursor = "pointer";
      item.style.textAlign = "left";

      const badgeType = f.type === "audit" ? "🛡️ 审计" : "📊 报告";

      item.innerHTML = `
        <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:210px;">
          <div style="font-weight:600; font-size:12px; color:var(--g-text-primary);">${f.name}</div>
          <div style="font-size:11px; color:var(--g-text-secondary); margin-top:2px;">${badgeType} · ${f.size_kb} KB</div>
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
  const titleEl = document.getElementById("logViewerTitle");
  if (titleEl) titleEl.innerText = fileName;
  const downBtn = document.getElementById("downloadLogBtn");
  if (downBtn) downBtn.disabled = false;
  const viewer = document.getElementById("logViewerContent");
  if (viewer) viewer.innerText = "正在载入...";

  try {
    const res = await fetch(`/api/log-files/content?path=${encodeURIComponent(relPath)}`);
    const data = await res.json();
    if (viewer) viewer.innerText = data.content || "（空文件）";
  } catch (err) {
    if (viewer) viewer.innerText = "读取文件失败: " + err;
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
  const inp = document.getElementById("ruleSearchInput");
  const kw = inp ? inp.value.trim().toLowerCase() : "";
  renderRulesCards(kw);
}

function renderRulesCards(kw = "") {
  const box = document.getElementById("rulesList");
  if (!box) return;
  box.innerHTML = "";

  const filtered = gState.rulesData.filter((r) => {
    if (!kw) return true;
    return (r.id + " " + (r.title || "") + " " + (r.statement || "")).toLowerCase().includes(kw);
  });

  filtered.forEach((r) => {
    const card = document.createElement("div");
    card.className = "rule-card";

    const badgeCls = r.kind === "WARN" ? "rule-badge-warn" : "rule-badge-block";
    const statusText = r.status === "confirmed" ? "Confirmed" : "Suspected";

    const affected = (r.affected_cases || []).map((c) => `<span class="rule-param-pill">${c}</span>`).join("");

    card.innerHTML = `
      <div class="rule-card-header">
        <div>
          <span class="rule-id-pill">${r.id}</span>
          <span style="font-size:11px; color:var(--g-text-secondary); margin-left:6px;">[${r.kind}]</span>
        </div>
        <span class="rule-badge ${badgeCls}">${statusText}</span>
      </div>
      <div class="rule-card-title">${r.title}</div>
      <div style="font-size:12px; color:var(--g-text-primary); line-height:1.5; margin:8px 0;">${r.statement}</div>
      ${r.evidence ? `<div style="font-size:11px; color:var(--g-text-secondary); background:var(--g-surface-variant); padding:6px 10px; border-radius:4px; margin-bottom:8px;">实测证据: ${r.evidence}</div>` : ""}
      <div class="rule-card-footer">
        <span style="font-size:11px; color:var(--g-text-secondary);">受影响用例:</span>
        <div class="rule-params-wrap">${affected || "无"}</div>
      </div>
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
    const passRateEl = document.getElementById("healthPassRate");
    if (passRateEl) passRateEl.innerText = `${sum["通过"] || 0} / ${sum["总计"] || 66} 通过`;

    const ruleEl = document.getElementById("healthRuleCount");
    if (ruleEl) ruleEl.innerText = `${data.rule_stats?.total || 57} 条`;

    const createdEl = document.getElementById("healthCreatedText");
    if (createdEl) createdEl.innerText = data.created_text || "门诊患者净增 0 · 测试挂号净增 0";
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
  if (!grid) return;
  grid.innerHTML = "";

  const results = data.results || [];
  if (results.length === 0) {
    grid.innerHTML = '<div style="color:var(--g-text-secondary); font-size:13px;">暂无巡检记录，请点击上方「立即执行界面巡检」</div>';
    return;
  }

  results.forEach((r) => {
    const card = document.createElement("div");
    card.className = "ws-card";

    let statusBadge = "";
    if (r.status === "通过") {
      statusBadge = '<span class="status-chip passed">通过</span>';
    } else if (r.status === "未执行") {
      statusBadge = '<span class="status-chip pending">未执行</span>';
    } else {
      statusBadge = '<span class="status-chip failed">失败</span>';
    }

    card.innerHTML = `
      <div class="ws-card-header">
        <div>
          <span style="font-weight:bold; font-family:var(--g-mono); color:var(--g-blue); font-size:14px;">${r.case_id}</span>
          <div class="ws-card-title" style="margin-top:4px;">${r.title}</div>
        </div>
        ${statusBadge}
      </div>
      <div class="ws-card-desc">${r.note || ""}</div>
      <div class="ws-card-footer">
        <span style="font-size:11px; color:var(--g-text-tertiary);">耗时: ${r.duration_ms}ms</span>
        <span class="badge" style="background:var(--g-blue-surface); color:var(--g-blue);">真实 DOM 对账</span>
      </div>
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
  switchTab("cases"); // 切换到用例控制台查看实时日志

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const resData = await res.json();
    if (!resData.ok) {
      showToast("启动失败", resData.msg, "danger");
    } else {
      setRunningState(true);
      showToast("界面巡检开始", "正在通过独立 Chrome 运行真实 DOM 比对", "run");
    }
  } catch (err) {
    showToast("请求异常", String(err), "danger");
  }
}

// =========================================================================
// 主题切换与辅助组件
// =========================================================================
function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  showToast("主题切换", `已切换为 ${next === "dark" ? "深色模式" : "浅色模式"}`, "info");
}

function showToast(title, desc, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `g-toast toast-${type}`;
  toast.innerHTML = `
    <div class="g-toast-icon">
      ${type === "success" ? "✅" : (type === "danger" ? "❌" : (type === "warning" ? "⚠️" : "ℹ️"))}
    </div>
    <div class="g-toast-content">
      <div class="g-toast-title">${title}</div>
      <div class="g-toast-desc">${desc}</div>
    </div>
    <span class="g-toast-close" onclick="this.parentElement.remove()">✕</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("hide");
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}
