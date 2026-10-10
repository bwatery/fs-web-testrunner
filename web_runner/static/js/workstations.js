/**
 * HIS WebRunner - 6 Core Hospital Workstations Modular Testing Module
 * (六大核心工作站模块测试管理前端交互)
 * 1. 住院工作站 (INPATIENT_DOCTOR)
 * 2. 门诊工作站 (OUTPATIENT_DOCTOR)
 * 3. 药房系统 (PHARMACY)
 * 4. 门诊收费 (OUTPATIENT_BILLING)
 * 5. 住院收费 (INPATIENT_BILLING)
 * 6. 住院护士 (INPATIENT_NURSE)
 */

let activeWorkstationCode = "INPATIENT_DOCTOR";
let cachedWorkstations = [];

const WORKSTATION_ICONS = {
  INPATIENT_DOCTOR: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7h18M3 12h18M3 17h18"></path><rect x="2" y="3" width="20" height="18" rx="2"></rect></svg>`,
  OUTPATIENT_DOCTOR: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`,
  PHARMACY: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M12 8v8M8 12h8"></path></svg>`,
  OUTPATIENT_BILLING: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>`,
  INPATIENT_BILLING: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v4M12 14v4M16 14v4"></path></svg>`,
  INPATIENT_NURSE: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 8v8M8 12h8"></path></svg>`
};

const WORKSTATION_THEMES = {
  INPATIENT_DOCTOR: {
    color: '#1a73e8',
    surface: 'var(--g-blue-surface, #e8f0fe)',
    badge: '住院医生'
  },
  OUTPATIENT_DOCTOR: {
    color: '#6366f1',
    surface: 'rgba(99, 102, 241, 0.12)',
    badge: '门诊医生'
  },
  PHARMACY: {
    color: '#0d9488',
    surface: 'rgba(13, 148, 136, 0.12)',
    badge: '药剂管理'
  },
  OUTPATIENT_BILLING: {
    color: '#d97706',
    surface: 'rgba(217, 119, 6, 0.12)',
    badge: '门诊结算'
  },
  INPATIENT_BILLING: {
    color: '#0284c7',
    surface: 'rgba(2, 132, 199, 0.12)',
    badge: '住院结算'
  },
  INPATIENT_NURSE: {
    color: '#e11d48',
    surface: 'rgba(225, 29, 72, 0.12)',
    badge: '病区护理'
  }
};

const WORKSTATION_FUNCTIONS = {
  INPATIENT_DOCTOR: [
    "在院患者管理与床位管辖检索",
    "长期医嘱开立与同组频次(QD/BID)校验",
    "临时急诊医嘱下达与时效规则",
    "临床诊断下达与ICD-10主副规范",
    "住院病历与首次病程记录完整性",
    "跨科急会诊申请与病危重分级通知",
    "出院医嘱开立与出院带药≤7天闭环"
  ],
  OUTPATIENT_DOCTOR: [
    "候诊队列检索与接诊排队叫号",
    "门诊电子病历结构化数据元规范",
    "门诊西药处方开立与皮试关联",
    "门诊中草药处方付数与配伍校验",
    "门诊检验检查申请开立与条码生成",
    "门诊就诊完成与收费处计费推送"
  ],
  PHARMACY: [
    "处方前置合理用药审核与配伍拦截",
    "门诊窗口处方调配与扫码发药",
    "住院病区医嘱批量自动摆药出库",
    "药品退药审核与批次库存冲正",
    "麻精特殊药品双人复核专管",
    "药房库存盘点与低库存警戒预警"
  ],
  OUTPATIENT_BILLING: [
    "门诊建档与挂号收费结算 (自费/医保)",
    "门诊处方划价预结算分账模型",
    "门诊收费确认与电子发票凭证生成",
    "门诊退费处理与医保交易冲正",
    "收费员日结对账与交班汇总报表"
  ],
  INPATIENT_BILLING: [
    "入院登记与预交金押金缴纳",
    "住院一日清单实时查询与穿透",
    "欠费预警线与信用额度控制",
    "住院中途结算与阶段性分段清算",
    "出院多渠道医保报销分解结算",
    "住院押金多退少补与病案归档结账"
  ],
  INPATIENT_NURSE: [
    "新入院接诊入科、分床与条码腕带",
    "新开立医嘱双人校对转抄确认",
    "医嘱扫码执行与输液巡视签名",
    "生命体征批量录入与三测单绘制",
    "首次护理评估与压疮跌倒风险评分",
    "出院带药护理宣教与终末床位消毒"
  ]
};

async function loadWorkstationsData() {
  try {
    const res = await fetch('/api/workstations');
    const data = await res.json();
    if (data.status === 'ok') {
      cachedWorkstations = data.workstations;
      renderWorkstationCards(cachedWorkstations);
      renderWorkstationDetail(activeWorkstationCode);
    }
  } catch (e) {
    console.error('Failed to load workstations:', e);
  }
}

function renderWorkstationCards(workstations) {
  const container = document.getElementById('workstationCardsGrid');
  if (!container) return;

  container.innerHTML = workstations.map(ws => {
    const isActive = (ws.code === activeWorkstationCode);
    const theme = WORKSTATION_THEMES[ws.code] || { color: '#1a73e8', surface: 'var(--g-blue-surface)', badge: '工作站' };
    const iconSvg = WORKSTATION_ICONS[ws.code] || WORKSTATION_ICONS.INPATIENT_DOCTOR;
    
    // Status text
    let statBadge = `<span class="badge" style="background:var(--g-surface-variant); color:var(--g-text-secondary); font-size:11px; padding:3px 8px; border-radius:12px;">待测试</span>`;
    if (ws.passed_count > 0 && ws.failed_count === 0) {
      statBadge = `<span class="badge" style="background:var(--g-green-surface); color:var(--g-green); font-size:11px; font-weight:600; padding:3px 9px; border-radius:12px; display:inline-flex; align-items:center; gap:5px;"><span style="width:6px; height:6px; border-radius:50%; background:var(--g-green);"></span>全部通过 (${ws.passed_count}/${ws.tests_count})</span>`;
    } else if (ws.failed_count > 0) {
      statBadge = `<span class="badge" style="background:var(--g-red-surface); color:var(--g-red); font-size:11px; font-weight:600; padding:3px 9px; border-radius:12px; display:inline-flex; align-items:center; gap:5px;"><span style="width:6px; height:6px; border-radius:50%; background:var(--g-red);"></span>异常 (${ws.failed_count}项)</span>`;
    } else if (ws.skipped_count > 0) {
      statBadge = `<span class="badge" style="background:var(--g-yellow-surface); color:var(--g-yellow); font-size:11px; font-weight:600; padding:3px 9px; border-radius:12px; display:inline-flex; align-items:center; gap:5px;"><span style="width:6px; height:6px; border-radius:50%; background:var(--g-yellow);"></span>跳过 (${ws.skipped_count}项)</span>`;
    }

    return `
      <div class="ws-card ${isActive ? 'active' : ''}" onclick="selectWorkstation('${ws.code}')">
        <div class="ws-card-header">
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="ws-icon-box" style="background:${isActive ? 'var(--g-blue-surface)' : theme.surface}; color:${isActive ? 'var(--g-blue)' : theme.color};">
              ${iconSvg}
            </div>
            <div>
              <div class="ws-card-title">
                ${ws.name}
                ${isActive ? `<span class="badge" style="background:var(--g-blue); color:#fff; font-size:10px; font-weight:600; padding:1px 6px; border-radius:10px;">● 当前查看</span>` : ''}
              </div>
              <div class="ws-card-tag">${ws.tag}</div>
            </div>
          </div>
          ${statBadge}
        </div>

        <div class="ws-card-desc">
          ${ws.desc || '核心功能全流程模块化自动化校验'}
        </div>

        <div class="ws-card-footer">
          <div style="font-size:12px; color:var(--g-text-tertiary);">
            包含 <strong style="color:var(--g-text-primary); font-size:13px;">${ws.tests_count}</strong> 项核心功能
          </div>
          <button class="g-btn g-btn-primary" style="height:28px; padding:0 12px; font-size:12px;" onclick="event.stopPropagation(); runSingleWorkstation('${ws.code}')">
            ▶ 模块测试
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function selectWorkstation(code) {
  activeWorkstationCode = code;
  renderWorkstationCards(cachedWorkstations);
  renderWorkstationDetail(code);
}

function renderWorkstationDetail(code) {
  const ws = cachedWorkstations.find(w => w.code === code);
  if (!ws) return;

  const headerElem = document.getElementById('wsDetailHeader');
  const funcsElem = document.getElementById('wsDetailFunctions');
  const tableElem = document.getElementById('wsTestCasesTableBody');

  if (headerElem) {
    const theme = WORKSTATION_THEMES[ws.code] || { color: '#1a73e8', surface: 'var(--g-blue-surface)', badge: '工作站' };
    headerElem.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:44px; height:44px; border-radius:12px; background:${theme.surface}; color:${theme.color}; display:flex; align-items:center; justify-content:center;">
            ${WORKSTATION_ICONS[ws.code] || WORKSTATION_ICONS.INPATIENT_DOCTOR}
          </div>
          <div>
            <div style="font-size:17px; font-weight:600; display:flex; align-items:center; gap:8px;">
              <span>${ws.name} — 业务模块全景测试</span>
              <span class="badge" style="background:${theme.surface}; color:${theme.color}; font-size:11px; font-weight:600;">${ws.code}</span>
            </div>
            <div style="font-size:12px; color:var(--g-text-secondary); margin-top:3px; display:flex; align-items:center; gap:6px;">
              <span>目标系统工作台路由:</span>
              <code style="background:var(--g-surface-variant); padding:2px 8px; border-radius:4px; font-family:var(--g-mono); font-size:11.5px; color:var(--g-text-primary);">${ws.url}</code>
            </div>
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <button class="g-btn g-btn-tonal" onclick="window.open('${ws.url}', '_blank')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
            <span>访问现场页面</span>
          </button>
          <button class="g-btn g-btn-primary" onclick="runSingleWorkstation('${ws.code}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            <span>立即执行【${ws.name}】全套模块测试</span>
          </button>
        </div>
      </div>
    `;
  }

  // Render Key Clinical/Financial Functions
  if (funcsElem) {
    const funcs = WORKSTATION_FUNCTIONS[ws.code] || [];
    const theme = WORKSTATION_THEMES[ws.code] || { color: '#1a73e8', surface: 'var(--g-blue-surface)' };
    funcsElem.innerHTML = `
      <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:10px;">
        ${funcs.map((fn, idx) => `
          <div style="display:flex; align-items:center; gap:10px; font-size:12px; color:var(--g-text-primary); background:var(--g-surface-variant); padding:9px 12px; border-radius:8px; border:1px solid var(--g-border); transition:all 0.15s ease;">
            <span style="width:20px; height:20px; border-radius:50%; background:${theme.color}; color:#fff; font-size:11px; font-weight:600; display:flex; align-items:center; justify-content:center; flex-shrink:0;">${idx + 1}</span>
            <span style="line-height:1.4;">${fn}</span>
          </div>
        `).join('')}
      </div>
    `;
  }

  // Render Outpatient Billing Core Cases Showcase (用户指定门诊收费处四大核心测试用例及页面)
  const showcaseElem = document.getElementById('wsCoreShowcaseContainer');
  if (showcaseElem) {
    if (ws.code === 'OUTPATIENT_BILLING') {
      showcaseElem.innerHTML = `
        <div style="background:linear-gradient(135deg, rgba(217,119,6,0.08), rgba(245,158,11,0.02)); border:1px solid rgba(217,119,6,0.25); border-radius:10px; padding:16px 18px; margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:18px;">💳</span>
              <strong style="font-size:14px; color:#b45309;">门诊收费处 · 核心业务测试用例专区 (挂号/办档/号序/发票/快捷键)</strong>
              <span class="badge" style="background:#fef3c7; color:#92400e; font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600;">门诊收费处 100% 页面可达实测</span>
            </div>
            <div style="font-size:12px; color:var(--g-text-secondary);">
              角色: 14 (门诊收费员) | 科室: 2 (收费处) | 基础路由: <code>#/outpatient/charge/chargeMain</code>
            </div>
          </div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px;">
            <!-- Card 1: L6-009 -->
            <div style="background:var(--g-surface); border:1px solid var(--g-border); border-radius:8px; padding:12px 14px; display:flex; flex-direction:column; justify-content:space-between; gap:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span class="badge" style="background:#e0f2fe; color:#0369a1; font-weight:600; font-size:11px;">L6-009 · 临时办档</span>
                  <span id="showcase-status-ui_l6_009_charge_reg_create_patient" class="badge" style="background:var(--g-surface-variant); color:var(--g-text-secondary); font-size:11px;">检测中...</span>
                </div>
                <div style="font-weight:600; font-size:13px; color:var(--g-text-primary); margin-bottom:4px;">门诊收费_挂号新建患者(临时办档)字段完整与查重防重复主索引</div>
                <div style="font-size:11.5px; color:var(--g-text-secondary); line-height:1.5;">
                  <span style="color:#d97706; font-weight:600;">★ 验收准则:</span> 不产生重复主索引；办档字段完整；可立即收费打印
                </div>
                <div style="font-size:11px; color:var(--g-text-tertiary); margin-top:4px;">
                  实测页面: <code style="font-family:monospace; background:var(--g-surface-variant); padding:1px 4px; border-radius:3px;">#/outpatient/charge/chargeMain</code>
                </div>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding-top:6px; border-top:1px dashed var(--g-border);">
                <button class="g-btn g-btn-tonal" style="height:26px; padding:0 10px; font-size:11.5px;" onclick="window.open('http://192.168.1.198:8088/#/outpatient/charge/chargeMain', '_blank')">查看页面</button>
                <button class="g-btn g-btn-primary" style="height:26px; padding:0 12px; font-size:11.5px;" onclick="runSingleCase('ui_l6_009_charge_reg_create_patient')">▶ 单项实测</button>
              </div>
            </div>

            <!-- Card 2: L6-012 -->
            <div style="background:var(--g-surface); border:1px solid var(--g-border); border-radius:8px; padding:12px 14px; display:flex; flex-direction:column; justify-content:space-between; gap:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span class="badge" style="background:#f3e8ff; color:#7e22ce; font-weight:600; font-size:11px;">L6-012 · 号序与费用</span>
                  <span id="showcase-status-ui_l6_012_charge_reg_number_sequence" class="badge" style="background:var(--g-surface-variant); color:var(--g-text-secondary); font-size:11px;">检测中...</span>
                </div>
                <div style="font-weight:600; font-size:13px; color:var(--g-text-primary); margin-bottom:4px;">门诊收费_号序连续不跳号不重号与结算类型挂号费变化</div>
                <div style="font-size:11.5px; color:var(--g-text-secondary); line-height:1.5;">
                  <span style="color:#d97706; font-weight:600;">★ 验收准则:</span> 号序不跳号不重号；退号后号序规则按配置；挂号费随结算类型正确变化
                </div>
                <div style="font-size:11px; color:var(--g-text-tertiary); margin-top:4px;">
                  实测页面: <code style="font-family:monospace; background:var(--g-surface-variant); padding:1px 4px; border-radius:3px;">#/outpatient/charge/chargeMain</code>
                </div>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding-top:6px; border-top:1px dashed var(--g-border);">
                <button class="g-btn g-btn-tonal" style="height:26px; padding:0 10px; font-size:11.5px;" onclick="window.open('http://192.168.1.198:8088/#/outpatient/charge/chargeMain', '_blank')">查看页面</button>
                <button class="g-btn g-btn-primary" style="height:26px; padding:0 12px; font-size:11.5px;" onclick="runSingleCase('ui_l6_012_charge_reg_number_sequence')">▶ 单项实测</button>
              </div>
            </div>

            <!-- Card 3: L6-013 -->
            <div style="background:var(--g-surface); border:1px solid var(--g-border); border-radius:8px; padding:12px 14px; display:flex; flex-direction:column; justify-content:space-between; gap:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span class="badge" style="background:#fef2f2; color:#b91c1c; font-weight:600; font-size:11px;">L6-013 · 票面与作废</span>
                  <span id="showcase-status-ui_l6_013_charge_reg_ticket_reprint" class="badge" style="background:var(--g-surface-variant); color:var(--g-text-secondary); font-size:11px;">检测中...</span>
                </div>
                <div style="font-weight:600; font-size:13px; color:var(--g-text-primary); margin-bottom:4px;">门诊收费_挂号票面信息完整性与补打作废追溯</div>
                <div style="font-size:11.5px; color:var(--g-text-secondary); line-height:1.5;">
                  <span style="color:#d97706; font-weight:600;">★ 验收准则:</span> 票面信息完整；补打可追溯；作废票不可再使用
                </div>
                <div style="font-size:11px; color:var(--g-text-tertiary); margin-top:4px;">
                  实测页面: <code style="font-family:monospace; background:var(--g-surface-variant); padding:1px 4px; border-radius:3px;">#/outpatient/charge/invoiceManagement</code>
                </div>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding-top:6px; border-top:1px dashed var(--g-border);">
                <button class="g-btn g-btn-tonal" style="height:26px; padding:0 10px; font-size:11.5px;" onclick="window.open('http://192.168.1.198:8088/#/outpatient/charge/invoiceManagement', '_blank')">查看页面</button>
                <button class="g-btn g-btn-primary" style="height:26px; padding:0 12px; font-size:11.5px;" onclick="runSingleCase('ui_l6_013_charge_reg_ticket_reprint')">▶ 单项实测</button>
              </div>
            </div>

            <!-- Card 4: L6-014 -->
            <div style="background:var(--g-surface); border:1px solid var(--g-border); border-radius:8px; padding:12px 14px; display:flex; flex-direction:column; justify-content:space-between; gap:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span class="badge" style="background:#ecfdf5; color:#047857; font-weight:600; font-size:11px;">L6-014 · 快捷键防错</span>
                  <span id="showcase-status-ui_l6_014_charge_reg_shortcuts_validation" class="badge" style="background:var(--g-surface-variant); color:var(--g-text-secondary); font-size:11px;">检测中...</span>
                </div>
                <div style="font-weight:600; font-size:13px; color:var(--g-text-primary); margin-bottom:4px;">门诊收费_院方习惯快捷键操作与前后端双重校验防脏记录</div>
                <div style="font-size:11.5px; color:var(--g-text-secondary); line-height:1.5;">
                  <span style="color:#d97706; font-weight:600;">★ 验收准则:</span> 快捷键符合院方操作习惯；非法值前后端双重校验；不产生脏挂号记录
                </div>
                <div style="font-size:11px; color:var(--g-text-tertiary); margin-top:4px;">
                  实测页面: <code style="font-family:monospace; background:var(--g-surface-variant); padding:1px 4px; border-radius:3px;">#/outpatient/charge/chargeMain</code>
                </div>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding-top:6px; border-top:1px dashed var(--g-border);">
                <button class="g-btn g-btn-tonal" style="height:26px; padding:0 10px; font-size:11.5px;" onclick="window.open('http://192.168.1.198:8088/#/outpatient/charge/chargeMain', '_blank')">查看页面</button>
                <button class="g-btn g-btn-primary" style="height:26px; padding:0 12px; font-size:11.5px;" onclick="runSingleCase('ui_l6_014_charge_reg_shortcuts_validation')">▶ 单项实测</button>
              </div>
            </div>
          </div>
        </div>
      `;
    } else {
      showcaseElem.innerHTML = '';
    }
  }

  // Load and render corresponding test cases
  fetchWorkstationTestResults(ws.code);
}

async function fetchWorkstationTestResults(code) {
  try {
    const [testsRes, statusRes] = await Promise.all([
      fetch('/api/tests'),
      fetch('/api/status')
    ]);
    const testsData = await testsRes.json();
    const statusData = await statusRes.json();

    const allTests = testsData.tests || [];
    const results = statusData.results || [];
    const resultMap = {};
    results.forEach(r => { resultMap[r.test_id] = r; });

    // Update showcase status badges if present
    ['ui_l6_009_charge_reg_create_patient', 'ui_l6_012_charge_reg_number_sequence', 'ui_l6_013_charge_reg_ticket_reprint', 'ui_l6_014_charge_reg_shortcuts_validation'].forEach(tid => {
      const el = document.getElementById(`showcase-status-${tid}`);
      if (el) {
        const r = resultMap[tid];
        if (r) {
          if (r.status === 'PASSED') {
            el.className = 'badge';
            el.style.background = 'var(--g-green-surface)';
            el.style.color = 'var(--g-green)';
            el.style.fontWeight = '600';
            el.innerText = '✓ 通过';
          } else if (r.status === 'FAILED') {
            el.className = 'badge';
            el.style.background = 'var(--g-red-surface)';
            el.style.color = 'var(--g-red)';
            el.style.fontWeight = '600';
            el.innerText = '✕ 失败';
          }
        } else {
          el.className = 'badge';
          el.style.background = 'var(--g-surface-variant)';
          el.style.color = 'var(--g-text-secondary)';
          el.innerText = '待运行';
        }
      }
    });

    const filteredTests = allTests.filter(t => t.workstation_code === code || (t.workstation && t.workstation.includes(code)));
    const tableBody = document.getElementById('wsTestCasesTableBody');
    if (!tableBody) return;

    if (filteredTests.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:30px; color:var(--g-text-tertiary);">暂无针对该工作站的模块测试用例</td></tr>`;
      return;
    }

    tableBody.innerHTML = filteredTests.map((t, idx) => {
      const res = resultMap[t.id];
      let statusBadge = `<span class="badge" style="background:var(--g-surface-variant); color:var(--g-text-secondary);">待运行</span>`;
      let durationStr = '-';
      let errorStr = '';

      if (res) {
        durationStr = `${res.duration_ms || 0} ms`;
        if (res.status === 'PASSED') {
          statusBadge = `<span class="badge" style="background:var(--g-green-surface); color:var(--g-green); font-weight:600;">✓ 通过</span>`;
        } else if (res.status === 'SKIPPED') {
          statusBadge = `<span class="badge" style="background:var(--g-yellow-surface); color:var(--g-yellow); font-weight:600;">⊘ 已跳过</span>`;
        } else if (res.status === 'FAILED') {
          statusBadge = `<span class="badge" style="background:var(--g-red-surface); color:var(--g-red); font-weight:600;">✕ 失败</span>`;
          errorStr = `<div style="font-size:11px; color:var(--g-red); margin-top:4px;">${res.error || ''}</div>`;
        }
      }

      return `
        <tr>
          <td style="width:40px; text-align:center; color:var(--g-text-tertiary);">${idx + 1}</td>
          <td>
            <div style="font-weight:600; color:var(--g-text-primary); font-size:13px;">${t.name}</div>
            <div style="font-size:11px; color:var(--g-text-tertiary);">${t.description || ''}</div>
            ${errorStr}
          </td>
          <td style="width:110px;">
            <span class="badge" style="font-size:11px; ${t.mode === 'INVASIVE' ? 'background:rgba(234,67,53,0.1); color:var(--g-red);' : 'background:rgba(52,168,83,0.1); color:var(--g-green);'}">
              ${t.mode === 'INVASIVE' ? '🖥️ 页面实测' : '⚡ 接口直测'}
            </span>
          </td>
          <td style="width:100px;">${statusBadge}</td>
          <td style="width:90px; font-family:monospace; font-size:12px; color:var(--g-text-secondary);">${durationStr}</td>
          <td style="width:90px; text-align:center;">
            <button class="g-btn g-btn-tonal" style="height:26px; padding:0 8px; font-size:11px;" onclick="runSingleCase('${t.id}')">
              单项测
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (e) {
    console.error('Error fetching workstation test results:', e);
  }
}

async function runSingleWorkstation(code) {
  const ws = cachedWorkstations.find(w => w.code === code);
  const name = ws ? ws.name : code;
  showToast(`正在启动【${name}】模块专项自动化测试...`, 'info');

  try {
    const isWindow = !!(document.getElementById('chkHeadless')?.checked || document.getElementById('chkHeadlessModal')?.checked);
    const isHeadless = !isWindow;
    const isSelfHeal = (document.getElementById('chkSelfHeal') ? document.getElementById('chkSelfHeal').checked : (document.getElementById('chkSelfHealTable') ? document.getElementById('chkSelfHealTable').checked : true));
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workstation: code,
        mode: 'ALL',
        headless: isHeadless,
        self_heal: isSelfHeal
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showToast(`已开始执行【${name}】测试项，请观察实时控制台`, 'success');
      // Poll progress
      pollWorkstationProgress(code);
    } else {
      showToast(data.error || '测试执行触发失败', 'error');
    }
  } catch (e) {
    showToast(`触发测试失败: ${e.message}`, 'error');
  }
}

async function runAllWorkstationsTests() {
  showToast('正在启动【全院六大工作站】全生命周期闭环模块测试...', 'info');
  try {
    const isWindow = !!(document.getElementById('chkHeadless')?.checked || document.getElementById('chkHeadlessModal')?.checked);
    const isHeadless = !isWindow;
    const isSelfHeal = (document.getElementById('chkSelfHeal') ? document.getElementById('chkSelfHeal').checked : (document.getElementById('chkSelfHealTable') ? document.getElementById('chkSelfHealTable').checked : true));
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: 'ALL',
        headless: isHeadless,
        self_heal: isSelfHeal
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showToast('全院工作站测试套件已在后台启动！', 'success');
      pollWorkstationProgress();
    }
  } catch (e) {
    showToast(`触发测试失败: ${e.message}`, 'error');
  }
}

function pollWorkstationProgress(code) {
  let count = 0;
  const interval = setInterval(async () => {
    count++;
    await loadWorkstationsData();
    const statusRes = await fetch('/api/status');
    const statusData = await statusRes.json();
    if (!statusData.is_running || count > 30) {
      clearInterval(interval);
      showToast('工作站模块测试执行完毕！', 'success');
    }
  }, 1500);
}

// Global hook
window.loadWorkstationsData = loadWorkstationsData;
window.selectWorkstation = selectWorkstation;
window.runSingleWorkstation = runSingleWorkstation;
window.runAllWorkstationsTests = runAllWorkstationsTests;
