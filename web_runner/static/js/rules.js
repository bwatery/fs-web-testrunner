    const expandedTableRows = new Set(); // tracks expanded rows in table view

    function escapeHtml(str) {
      if (typeof str !== 'string') return str === undefined || str === null ? '' : String(str);
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function highlightRuleMatch(text, query) {
      if (!text) return '';
      const safeText = escapeHtml(text);
      if (!query || !query.trim()) return safeText;
      const terms = query.trim().split(/\s+/).filter(Boolean);
      if (query.trim().length >= 4 && !query.includes(' ')) {
        terms.push(query.trim().slice(0, 2), query.trim().slice(2));
      }
      let result = safeText;
      for (const t of terms) {
        if (!t) continue;
        const qClean = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const re = new RegExp(`(${qClean})`, 'gi');
        result = result.replace(re, '<mark class="rule-search-highlight">$1</mark>');
      }
      return result;
    }

    function setRuleView(mode) {
      currentRuleView = mode;
      localStorage.setItem('rule_view_mode', mode);
      document.querySelectorAll('.rule-view-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.view === mode);
      });
      const groupTools = document.getElementById('ruleGroupTools');
      if (groupTools) {
        groupTools.style.display = mode === 'grouped' ? 'inline-flex' : 'none';
      }
      renderBusinessRules();
    }

    function expandAllRuleGroups() {
      document.querySelectorAll('.rule-group-card').forEach(c => c.open = true);
    }

    function collapseAllRuleGroups() {
      document.querySelectorAll('.rule-group-card').forEach(c => c.open = false);
    }

    function applyRuleQuickSearch(keyword) {
      ruleSearchQuery = keyword;
      const input = document.getElementById('ruleSearchInput');
      if (input) {
        input.value = keyword;
        input.focus();
      }
      document.querySelectorAll('.quick-tag-chip').forEach(chip => {
        chip.classList.toggle('active', chip.innerText.includes(keyword));
      });
      renderBusinessRules();
    }

    function clearRuleSearch() {
      ruleSearchQuery = '';
      const input = document.getElementById('ruleSearchInput');
      if (input) {
        input.value = '';
        input.focus();
      }
      document.querySelectorAll('.quick-tag-chip').forEach(chip => chip.classList.remove('active'));
      renderBusinessRules();
    }

    function toggleRuleTableRow(ruleId) {
      if (expandedTableRows.has(ruleId)) {
        expandedTableRows.delete(ruleId);
      } else {
        expandedTableRows.add(ruleId);
      }
      const expandRow = document.getElementById(`expand_row_${ruleId}`);
      const parentRow = document.getElementById(`table_row_${ruleId}`);
      const arrowEl = document.getElementById(`arrow_${ruleId}`);
      if (expandRow) {
        expandRow.style.display = expandedTableRows.has(ruleId) ? 'table-row' : 'none';
      }
      if (parentRow) {
        parentRow.classList.toggle('expanded', expandedTableRows.has(ruleId));
      }
      if (arrowEl) {
        arrowEl.innerText = expandedTableRows.has(ruleId) ? '▼' : '▶';
      }
    }

    // Keyboard shortcut '/' to focus rule search, Esc to clear
    window.addEventListener('keydown', (e) => {
      const activeEl = document.activeElement;
      const isInput = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable);
      
      if (e.key === '/' && !isInput) {
        const rulesTab = document.getElementById('tab-rules');
        if (rulesTab && rulesTab.classList.contains('active')) {
          e.preventDefault();
          const input = document.getElementById('ruleSearchInput');
          if (input) input.focus();
        }
      } else if (e.key === 'Escape' && activeEl && activeEl.id === 'ruleSearchInput') {
        clearRuleSearch();
        activeEl.blur();
      }
    });

    async function loadBusinessRules() {
      try {
        const resp = await fetch('/api/rules');
        const data = await resp.json();
        if (data.status === 'ok') {
          allBusinessRules = data.rules || [];
          const stats = data.stats || {};

          // Update stats ribbon
          const elTotal = document.getElementById('ruleStatTotal');
          const elIP = document.getElementById('ruleStatIP');
          const elOP = document.getElementById('ruleStatOP');
          const elBlock = document.getElementById('ruleStatBlock');
          const elWarn = document.getElementById('ruleStatWarn');
          const elPassed = document.getElementById('ruleStatPassed');

          if (elTotal) elTotal.innerText = stats.total || 0;
          if (elIP) elIP.innerText = stats.inpatient_count || 0;
          if (elOP) elOP.innerText = stats.outpatient_count || 0;
          if (elBlock) elBlock.innerText = stats.block_count || 0;
          if (elWarn) elWarn.innerText = stats.warn_count || 0;
          if (elPassed) elPassed.innerText = `${stats.passed_count || 0} / ${stats.total || 0}`;

          // Update filter badge counts
          const fAll = document.getElementById('filterCountAll');
          const fIP = document.getElementById('filterCountIP');
          const fOP = document.getElementById('filterCountOP');
          if (fAll) fAll.innerText = allBusinessRules.length;
          if (fIP) fIP.innerText = allBusinessRules.filter(r => r.domain === 'inpatient').length;
          if (fOP) fOP.innerText = allBusinessRules.filter(r => r.domain === 'outpatient').length;
          const railBadgeRules = document.getElementById('railBadgeRules');
          if (railBadgeRules) railBadgeRules.innerText = allBusinessRules.length;

          renderBusinessRules();
        }
      } catch (err) {
        console.error("Failed to load business rules:", err);
      }
    }

    function renderSingleRuleCard(r, q) {
      const isIP = r.domain === 'inpatient';
      const isOP = r.domain === 'outpatient';
      const isPharma = r.domain === 'pharmacy';
      const isEMR = r.domain === 'emr';
      const isCharge = r.domain === 'charge';
      
      let domainClass = 'rule-badge-custom';
      if (isIP) domainClass = 'rule-badge-ip';
      else if (isOP) domainClass = 'rule-badge-op';
      else if (isPharma) domainClass = 'rule-badge-pharma';
      else if (isEMR) domainClass = 'rule-badge-emr';
      else if (isCharge) domainClass = 'rule-badge-charge';

      const isBlock = r.severity === 'BLOCK';
      const severityClass = isBlock ? 'rule-badge-block' : 'rule-badge-warn';
      
      let statusChipHtml = '';
      if (r.last_verify_status === 'PASSED') {
        statusChipHtml = `<span class="rule-status-chip pass" title="${r.last_verify_time || ''}">${Icons.checkCircle} 校验通过 (${r.last_verify_duration_ms || 0}ms)</span>`;
      } else if (r.last_verify_status === 'FAILED') {
        statusChipHtml = `<span class="rule-status-chip fail" title="${r.last_verify_time || ''}">${Icons.xCircle} 校验失败</span>`;
      } else {
        statusChipHtml = `<span class="rule-status-chip none">● 待校验</span>`;
      }

      const params = r.parameters || {};
      const paramPills = Object.entries(params).map(([k, v]) => {
        const displayVal = (typeof v === 'object') ? JSON.stringify(v) : v;
        return `<span class="rule-param-pill"><span class="p-key">${escapeHtml(k)}</span>: <span class="p-val">${highlightRuleMatch(String(displayVal), q)}</span></span>`;
      }).join('');

      const isCustom = !!r.is_custom;

      return `
        <div class="rule-card ${r.enabled === false ? 'disabled-rule' : ''}" id="card_${r.id}">
          <!-- Header Row -->
          <div class="rule-card-header">
            <div class="rule-card-badges">
              <span class="rule-id-pill">${highlightRuleMatch(r.id, q)}</span>
              <span class="rule-badge ${domainClass}">${getCategorySvg(r.domain_name)} ${highlightRuleMatch(r.domain_name || '业务规则', q)}</span>
              <span class="rule-badge ${severityClass}">${isBlock ? Icons.alertOctagon : Icons.alertTriangle} ${highlightRuleMatch(r.severity_name || (isBlock ? '阻断门禁' : '预警规范'), q)}</span>
            </div>
            <div class="rule-card-toggle">
              <label class="rule-toggle-label" title="开启/停用此规则">
                <input type="checkbox" onchange="toggleRuleEnabled('${r.id}', this.checked)" ${r.enabled !== false ? 'checked' : ''} style="width:15px; height:15px; accent-color:var(--g-blue);">
                <span>${r.enabled !== false ? '已激活' : '已停用'}</span>
              </label>
              ${isCustom ? `
                <button class="icon-btn btn-rule-del" onclick="deleteRule('${r.id}')" title="删除此自定义规则" style="width:24px; height:24px; font-size:12px; color:var(--g-red); margin-left:4px;">
                  ${Icons.trash}
                </button>
              ` : ''}
            </div>
          </div>

          <!-- Title -->
          <h4 class="rule-card-title" onclick="openRuleDetailModal('${r.id}')" style="cursor:pointer;" title="点击查看规则全景详细说明">
            ${highlightRuleMatch(r.name, q)}
          </h4>

          <!-- Core Rule Callout -->
          <div class="rule-core-callout">
            <span class="callout-icon">${Icons.bulb}</span>
            <span class="callout-text">${highlightRuleMatch(r.summary || '', q)}</span>
          </div>

          <!-- Meta Grid (Trigger & Target) -->
          <div class="rule-meta-grid">
            <div class="rule-meta-row">
              <span class="rule-meta-label">${Icons.zap} 触发环节</span>
              <span class="rule-meta-val">${highlightRuleMatch(r.trigger_phase || '全流程', q)}</span>
            </div>
            <div class="rule-meta-row">
              <span class="rule-meta-label">${Icons.target} 涉及目标</span>
              <span class="rule-meta-val"><code class="rule-meta-code">${highlightRuleMatch(r.target_api_table || 'N/A', q)}</code></span>
            </div>
          </div>

          <!-- Parameters Section -->
          ${Object.keys(params).length > 0 ? `
            <div class="rule-params-wrap">
              <span class="rule-params-title">${Icons.gear} 控制参数:</span>
              ${paramPills}
            </div>
          ` : ''}

          <!-- Details Collapsible -->
          <details class="rule-details-box" ${q ? 'open' : ''}>
            <summary>${Icons.bookOpen} 查看临床背景与规范说明</summary>
            <div class="rule-details-content">${highlightRuleMatch(r.detail || '暂无详细描述', q)}</div>
          </details>

          <!-- Footer Actions -->
          <div class="rule-card-footer">
            <div>
              ${statusChipHtml}
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
              <button class="g-btn g-btn-tonal btn-rule-verify" style="padding:4px 10px; font-size:11.5px; height:26px;" onclick="verifySingleRule('${r.id}', this)" title="现场执行该规则断言测试">
                ${Icons.play} 现场校验
              </button>
              <button class="g-btn g-btn-outlined btn-rule-edit" style="padding:4px 10px; font-size:11.5px; height:26px;" onclick="openEditRuleModal('${r.id}')" title="在线调整此规则参数与规范">
                ${Icons.gear} 维护
              </button>
              <button class="g-btn g-btn-outlined" style="padding:4px 8px; font-size:11.5px; height:26px;" onclick="openRuleDetailModal('${r.id}')" title="全屏查看规则背景">
                ${Icons.bookOpen} 详情
              </button>
              ${(r.last_verify_log && r.last_verify_log.length > 0) ? `
                <button class="g-btn g-btn-outlined" style="padding:4px 8px; font-size:11.5px; height:26px;" onclick="viewRuleLogs('${r.id}')" title="查看断言日志">
                  ${Icons.document} 日志
                </button>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }

    function renderBusinessRules() {
      const container = document.getElementById('rulesCardsContainer');
      if (!container) return;

      const q = ruleSearchQuery.trim().toLowerCase();
      const filtered = allBusinessRules.filter(r => {
        // Domain/Severity/Status filters
        if (currentRuleFilter === 'inpatient' && r.domain !== 'inpatient') return false;
        if (currentRuleFilter === 'outpatient' && r.domain !== 'outpatient') return false;
        if (currentRuleFilter === 'block' && r.severity !== 'BLOCK') return false;
        if (currentRuleFilter === 'warn' && r.severity !== 'WARN') return false;
        if (currentRuleFilter === 'passed' && r.last_verify_status !== 'PASSED') return false;
        if (currentRuleFilter === 'failed' && r.last_verify_status !== 'FAILED') return false;

        // Search query
        if (q) {
          const combined = [
            r.id, r.name, r.target_api_table, r.trigger_phase, r.summary, r.detail, r.domain_name, r.severity_name, JSON.stringify(r.parameters || {})
          ].join(' ').toLowerCase();

          // 1. Direct substring match
          if (combined.includes(q)) return true;

          // 2. Multi-term match (e.g. "时间 跟随")
          const terms = q.split(/\s+/).filter(Boolean);
          if (terms.length > 1 && terms.every(t => combined.includes(t))) return true;

          // 3. Fallback for compound 4+ character queries (e.g. "时间跟随" -> "时间" & "跟随")
          if (q.length >= 4) {
            const sub1 = q.slice(0, 2);
            const sub2 = q.slice(2);
            if (combined.includes(sub1) && combined.includes(sub2)) return true;
          }

          return false;
        }
        return true;
      });

      // Update search count badge & clear button
      const countBadge = document.getElementById('ruleSearchCountBadge');
      const clearBtn = document.getElementById('btnRuleSearchClear');
      if (q) {
        if (countBadge) {
          countBadge.style.display = 'inline-block';
          countBadge.innerText = `匹配 ${filtered.length} / ${allBusinessRules.length} 项`;
        }
        if (clearBtn) clearBtn.style.display = 'inline-flex';
      } else {
        if (countBadge) {
          countBadge.style.display = 'inline-block';
          countBadge.innerText = `共 ${allBusinessRules.length} 项`;
        }
        if (clearBtn) clearBtn.style.display = 'none';
      }

      // Empty State
      if (filtered.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:48px 24px; color:var(--g-text-secondary); background:var(--g-surface); border:1px dashed var(--g-border); border-radius:var(--g-radius-md); box-shadow:var(--g-shadow-1);">
            <div style="margin-bottom:10px; color:var(--g-text-tertiary);"><svg class="ui-icon" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg></div>
            <div style="font-size:15px; font-weight:600; color:var(--g-text-primary);">未找到与 “${escapeHtml(ruleSearchQuery)}” 匹配的业务规则</div>
            <div style="font-size:12px; margin-top:6px; color:var(--g-text-tertiary);">请尝试更换关键词，或者点击下方按钮恢复全部规则查看</div>
            <div style="margin-top:16px;">
              <button class="g-btn g-btn-primary" onclick="clearRuleSearch()" style="height:32px; font-size:12px;">${Icons.refresh} 清空搜索并查看全部</button>
            </div>
          </div>
        `;
        return;
      }

      // Synchronize View Switcher Button states
      document.querySelectorAll('.rule-view-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.view === currentRuleView);
      });
      const groupTools = document.getElementById('ruleGroupTools');
      if (groupTools) {
        groupTools.style.display = currentRuleView === 'grouped' ? 'inline-flex' : 'none';
      }

      // -------------------------------------------------------------
      // View 1: Grouped Accordions (业务模块分组手风琴)
      // -------------------------------------------------------------
      if (currentRuleView === 'grouped') {
        const domainMap = {
          'inpatient': { name: '住院核心业务与医嘱规范', icon: Icons.bed, order: 1 },
          'outpatient': { name: '门诊流程与挂号收费规范', icon: Icons.clinic, order: 2 },
          'pharmacy': { name: '药房药品与库房管理规范', icon: Icons.pill, order: 3 },
          'emr': { name: '电子病历与医疗质控规范', icon: Icons.document, order: 4 },
          'charge': { name: '费用结算与医保控费规范', icon: Icons.card, order: 5 },
          'other': { name: '自定义与其它扩展业务规范', icon: Icons.folder, order: 6 }
        };

        const groups = {};
        filtered.forEach(r => {
          const dom = r.domain || 'other';
          if (!groups[dom]) groups[dom] = [];
          groups[dom].push(r);
        });

        const sortedDomKeys = Object.keys(groups).sort((a, b) => {
          const oA = (domainMap[a] && domainMap[a].order) || 99;
          const oB = (domainMap[b] && domainMap[b].order) || 99;
          return oA - oB;
        });

        container.innerHTML = sortedDomKeys.map(dom => {
          const groupRules = groups[dom];
          const info = domainMap[dom] || { name: `${dom} 业务规范`, icon: Icons.folder };
          const blockCnt = groupRules.filter(r => r.severity === 'BLOCK').length;
          const warnCnt = groupRules.filter(r => r.severity === 'WARN').length;
          const passCnt = groupRules.filter(r => r.last_verify_status === 'PASSED').length;

          const rowsHtml = groupRules.map(r => {
            const isBlock = r.severity === 'BLOCK';
            let statusBadge = '';
            if (r.last_verify_status === 'PASSED') {
              statusBadge = `<span class="rule-status-chip pass" style="font-size:10.5px; padding:1px 6px;">通过 (${r.last_verify_duration_ms || 0}ms)</span>`;
            } else if (r.last_verify_status === 'FAILED') {
              statusBadge = `<span class="rule-status-chip fail" style="font-size:10.5px; padding:1px 6px; display:inline-flex; align-items:center; gap:3px;">${Icons.xCircle} 失败</span>`;
            } else {
              statusBadge = `<span class="rule-status-chip none" style="font-size:10.5px; padding:1px 6px;">● 待校验</span>`;
            }

            return `
              <div class="rule-compact-list-row" onclick="openRuleDetailModal('${r.id}')" title="点击查看【${escapeHtml(r.name)}】临床背景与详细说明">
                <div style="display:flex; align-items:center; gap:8px; flex:1; min-width:0; overflow:hidden;">
                  <span class="rule-id-pill" style="font-size:10.5px; flex-shrink:0;">${highlightRuleMatch(r.id, q)}</span>
                  <span style="font-weight:600; font-size:12px; color:var(--g-text-primary); white-space:nowrap; flex-shrink:0;">${highlightRuleMatch(r.name, q)}</span>
                  <span style="font-size:11px; color:var(--g-text-tertiary); background:var(--g-surface-variant); padding:1px 6px; border-radius:4px; white-space:nowrap; flex-shrink:0;">${Icons.zap} ${highlightRuleMatch(r.trigger_phase || '全流程', q)}</span>
                  <span style="font-size:11.5px; color:var(--g-text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">${highlightRuleMatch(r.summary || '', q)}</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">
                  <code class="rule-meta-code" style="font-size:10.5px; max-width:130px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(r.target_api_table || '')}">${highlightRuleMatch(r.target_api_table || 'N/A', q)}</code>
                  <span class="rule-badge ${isBlock ? 'rule-badge-block' : 'rule-badge-warn'}" style="font-size:10.5px; padding:1px 6px;">${isBlock ? Icons.alertOctagon : Icons.alertTriangle} ${isBlock ? '阻断' : '预警'}</span>
                  ${statusBadge}
                  <input type="checkbox" onchange="event.stopPropagation(); toggleRuleEnabled('${r.id}', this.checked)" ${r.enabled !== false ? 'checked' : ''} style="width:14px; height:14px; accent-color:var(--g-blue);" title="启用/停用此规则">
                  <button class="g-btn g-btn-tonal" style="height:22px; padding:0 6px; font-size:10.5px; border-radius:11px;" onclick="event.stopPropagation(); verifySingleRule('${r.id}', this)" title="现场执行校验" style="display:inline-flex; align-items:center; gap:3px;">${Icons.play} 校验</button>
                  <button class="g-btn g-btn-outlined" style="height:22px; padding:0 6px; font-size:10.5px; border-radius:11px;" onclick="event.stopPropagation(); openEditRuleModal('${r.id}')" title="编辑参数与规范" style="display:inline-flex; align-items:center; gap:3px;">${Icons.gear} 维护</button>
                  <button class="g-btn g-btn-outlined" style="height:22px; padding:0 6px; font-size:10.5px; border-radius:11px;" onclick="event.stopPropagation(); openRuleDetailModal('${r.id}')" title="全屏查看详情" style="display:inline-flex; align-items:center; gap:3px;">${Icons.bookOpen} 详情</button>
                </div>
              </div>
            `;
          }).join('');

          return `
            <details class="rule-group-card" open id="group_${dom}">
              <summary class="rule-group-summary">
                <div style="display:flex; align-items:center; gap:10px;">
                  <span style="font-size:16px;">${info.icon}</span>
                  <span style="font-weight:700; font-size:13.5px;">${info.name}</span>
                  <span class="badge" style="background:var(--g-surface); border:1px solid var(--g-border); color:var(--g-text-secondary); font-size:11px; padding:1px 7px; border-radius:10px;">${groupRules.length} 项</span>
                  <span style="font-size:11px; color:var(--g-text-tertiary); font-weight:normal;">
                    (${Icons.alertOctagon} ${blockCnt} 阻断 · ${Icons.alertTriangle} ${warnCnt} 预警)
                  </span>
                  ${passCnt > 0 ? `<span class="badge" style="background:var(--g-green-surface); color:var(--g-green); font-size:11px; padding:1px 7px; border-radius:10px; display:inline-flex; align-items:center; gap:4px;">${Icons.checkCircle} ${passCnt}/${groupRules.length} 已通过</span>` : ''}
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <button type="button" class="g-btn g-btn-tonal" style="height:24px; font-size:11px; padding:0 8px; border-radius:12px;" onclick="event.stopPropagation(); verifyGroupRules('${dom}', this)" title="仅校验该分组下的全部规则">
                    ${Icons.zap} 校验本组 (${groupRules.length})
                  </button>
                  <span class="rule-group-chevron">▼</span>
                </div>
              </summary>
              <div class="rule-group-body">
                ${rowsHtml}
              </div>
            </details>
          `;
        }).join('');
        return;
      }

      // -------------------------------------------------------------
      // View 2: Compact Master Table (紧凑清单表格视图 - 一屏全览)
      // -------------------------------------------------------------
      if (currentRuleView === 'table') {
        const tableRows = filtered.map(r => {
          const isIP = r.domain === 'inpatient';
          const isOP = r.domain === 'outpatient';
          const isPharma = r.domain === 'pharmacy';
          const isEMR = r.domain === 'emr';
          const isCharge = r.domain === 'charge';
          
          let domainBadge = 'rule-badge-custom';
          if (isIP) domainBadge = 'rule-badge-ip';
          else if (isOP) domainBadge = 'rule-badge-op';
          else if (isPharma) domainBadge = 'rule-badge-pharma';
          else if (isEMR) domainBadge = 'rule-badge-emr';
          else if (isCharge) domainBadge = 'rule-badge-charge';

          const isBlock = r.severity === 'BLOCK';
          const severityBadge = isBlock ? 'rule-badge-block' : 'rule-badge-warn';
          
          let statusBadge = '';
          if (r.last_verify_status === 'PASSED') {
            statusBadge = `<span class="rule-status-chip pass" style="font-size:11px; padding:2px 8px;">通过 (${r.last_verify_duration_ms || 0}ms)</span>`;
          } else if (r.last_verify_status === 'FAILED') {
            statusBadge = `<span class="rule-status-chip fail" style="font-size:11px; padding:2px 8px; display:inline-flex; align-items:center; gap:3px;">${Icons.xCircle} 失败</span>`;
          } else {
            statusBadge = `<span class="rule-status-chip none" style="font-size:11px; padding:2px 8px;">● 待校验</span>`;
          }

          const isExpanded = expandedTableRows.has(r.id);
          const params = r.parameters || {};
          const paramPills = Object.entries(params).map(([k, v]) => {
            const displayVal = (typeof v === 'object') ? JSON.stringify(v) : v;
            return `<span class="rule-param-pill"><span class="p-key">${escapeHtml(k)}</span>: <span class="p-val">${highlightRuleMatch(String(displayVal), q)}</span></span>`;
          }).join('');

          return `
            <tr class="rule-table-row ${isExpanded ? 'expanded' : ''}" id="table_row_${r.id}">
              <td style="text-align:center; width:36px;" onclick="toggleRuleTableRow('${r.id}')">
                <span id="arrow_${r.id}" style="font-size:11px; color:var(--g-text-tertiary);">${isExpanded ? '▼' : '▶'}</span>
              </td>
              <td style="font-family:var(--g-mono); font-weight:700; font-size:11.5px; white-space:nowrap;" onclick="toggleRuleTableRow('${r.id}')">
                <span class="rule-id-pill">${highlightRuleMatch(r.id, q)}</span>
              </td>
              <td style="white-space:nowrap;" onclick="toggleRuleTableRow('${r.id}')">
                <span class="rule-badge ${domainBadge}">${highlightRuleMatch(r.domain_name || '规则', q)}</span>
              </td>
              <td onclick="toggleRuleTableRow('${r.id}')">
                <div style="font-weight:600; color:var(--g-text-primary); font-size:12.5px;">${highlightRuleMatch(r.name, q)}</div>
                <div style="font-size:11.5px; color:var(--g-text-secondary); margin-top:2px;">${highlightRuleMatch(r.summary || '', q)}</div>
              </td>
              <td style="white-space:nowrap;" onclick="toggleRuleTableRow('${r.id}')">
                <span class="rule-badge ${severityBadge}">${isBlock ? Icons.alertOctagon : Icons.alertTriangle} ${highlightRuleMatch(r.severity_name || (isBlock ? '阻断' : '预警'), q)}</span>
              </td>
              <td style="font-size:11.5px; color:var(--g-text-secondary); max-width:125px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" onclick="toggleRuleTableRow('${r.id}')" title="${escapeHtml(r.trigger_phase || '')}">
                ${highlightRuleMatch(r.trigger_phase || '全流程', q)}
              </td>
              <td style="font-size:11px; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" onclick="toggleRuleTableRow('${r.id}')" title="${escapeHtml(r.target_api_table || '')}">
                <code class="rule-meta-code">${highlightRuleMatch(r.target_api_table || 'N/A', q)}</code>
              </td>
              <td style="white-space:nowrap;" onclick="toggleRuleTableRow('${r.id}')">
                ${statusBadge}
              </td>
              <td style="text-align:center; width:45px;">
                <input type="checkbox" onchange="toggleRuleEnabled('${r.id}', this.checked)" ${r.enabled !== false ? 'checked' : ''} style="width:15px; height:15px; accent-color:var(--g-blue);" title="启用/停用此规则">
              </td>
              <td style="text-align:right; white-space:nowrap; width:150px;">
                <div style="display:inline-flex; align-items:center; gap:4px;">
                  <button class="g-btn g-btn-tonal" style="height:24px; padding:0 8px; font-size:11px; border-radius:12px;" onclick="verifySingleRule('${r.id}', this)" title="现场执行断言测试" style="display:inline-flex; align-items:center; gap:3px;">${Icons.play} 校验</button>
                  <button class="g-btn g-btn-outlined" style="height:24px; padding:0 8px; font-size:11px; border-radius:12px;" onclick="openEditRuleModal('${r.id}')" title="编辑参数" style="display:inline-flex; align-items:center; gap:3px;">${Icons.gear} 维护</button>
                  <button class="g-btn g-btn-outlined" style="height:24px; padding:0 8px; font-size:11px; border-radius:12px;" onclick="openRuleDetailModal('${r.id}')" title="查看完整详情" style="display:inline-flex; align-items:center; gap:3px;">${Icons.bookOpen} 详情</button>
                </div>
              </td>
            </tr>
            <tr id="expand_row_${r.id}" class="rule-table-expand-row" style="display:${isExpanded ? 'table-row' : 'none'};">
              <td colspan="10" class="rule-table-expand-cell">
                <div class="rule-table-expand-content">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;">
                    <div style="flex:1; min-width:300px;">
                      <div style="font-weight:600; font-size:12px; color:var(--g-text-secondary); margin-bottom:4px;"><span style="display:inline-flex; align-items:center; gap:4px;">${Icons.bookOpen} 临床痛点背景与规范说明:</span></div>
                      <div style="background:var(--g-surface); border:1px solid var(--g-border-subtle); border-radius:6px; padding:8px 12px; line-height:1.6; white-space:pre-wrap; color:var(--g-text-primary); font-size:12px;">${highlightRuleMatch(r.detail || '暂无详细描述', q)}</div>
                    </div>
                    ${Object.keys(params).length > 0 ? `
                      <div style="min-width:280px; max-width:400px;">
                        <div style="font-weight:600; font-size:12px; color:var(--g-text-secondary); margin-bottom:4px;"><span style="display:inline-flex; align-items:center; gap:4px;">${Icons.gear} 控制参数 (JSON):</span></div>
                        <div class="rule-params-wrap" style="background:var(--g-surface); border:1px solid var(--g-border-subtle); border-radius:6px; padding:8px 10px;">
                          ${paramPills}
                        </div>
                      </div>
                    ` : ''}
                  </div>
                </div>
              </td>
            </tr>
          `;
        }).join('');

        container.innerHTML = `
          <div class="rule-table-container">
            <table class="rule-table">
              <thead>
                <tr>
                  <th style="width:32px; text-align:center;"></th>
                  <th style="width:95px;">编号</th>
                  <th style="width:80px;">模块</th>
                  <th>规则名称 & 核心约束</th>
                  <th style="width:88px;">门禁级别</th>
                  <th style="width:125px;">触发环节</th>
                  <th style="width:160px;">涉及目标 (表/字段)</th>
                  <th style="width:105px;">校验状态</th>
                  <th style="width:45px; text-align:center;">启用</th>
                  <th style="width:150px; text-align:right;">操作</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows}
              </tbody>
            </table>
          </div>
        `;
        return;
      }

      // -------------------------------------------------------------
      // View 3: Card Grid View (详细卡片网格)
      // -------------------------------------------------------------
      container.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(460px, 1fr)); gap:16px;">
          ${filtered.map(r => renderSingleRuleCard(r, q)).join('')}
        </div>
      `;
    }

    // Toggle rule filter buttons
    document.querySelectorAll('.rule-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.rule-filter-btn').forEach(b => {
          b.classList.remove('active', 'g-btn-tonal');
          b.classList.add('g-btn-outlined');
        });
        btn.classList.add('active', 'g-btn-tonal');
        btn.classList.remove('g-btn-outlined');
        currentRuleFilter = btn.dataset.filter;
        renderBusinessRules();
      });
    });

    // Rule search input
    const ruleSearchInputEl = document.getElementById('ruleSearchInput');
    if (ruleSearchInputEl) {
      ruleSearchInputEl.addEventListener('input', (e) => {
        ruleSearchQuery = e.target.value;
        renderBusinessRules();
      });
    }

    // Open Rule Detail Modal
    function openRuleDetailModal(ruleId) {
      const r = allBusinessRules.find(x => x.id === ruleId);
      if (!r) return;

      const modal = document.getElementById('ruleDetailModal');
      const body = document.getElementById('ruleDetailModalBody');
      const idBadge = document.getElementById('detailRuleIdBadge');
      const domainBadge = document.getElementById('detailRuleDomainBadge');
      const severityBadge = document.getElementById('detailRuleSeverityBadge');
      const statusChip = document.getElementById('detailRuleStatusChip');
      const btnVerify = document.getElementById('btnDetailVerifyRule');
      const btnEdit = document.getElementById('btnDetailEditRule');

      if (idBadge) idBadge.innerText = r.id;
      if (domainBadge) {
        domainBadge.innerText = r.domain_name || r.domain;
        domainBadge.className = `rule-badge rule-badge-${r.domain || 'custom'}`;
      }
      if (severityBadge) {
        severityBadge.innerHTML = r.severity === 'BLOCK' ? `${Icons.alertOctagon} 硬性阻断门禁` : `${Icons.alertTriangle} 业务预警规范`;
        severityBadge.className = `rule-badge ${r.severity === 'BLOCK' ? 'rule-badge-block' : 'rule-badge-warn'}`;
      }

      if (statusChip) {
        if (r.last_verify_status === 'PASSED') {
          statusChip.innerHTML = `<span class="rule-status-chip pass">${Icons.checkCircle} 校验通过 (${r.last_verify_duration_ms || 0}ms - ${r.last_verify_time || ''})</span>`;
        } else if (r.last_verify_status === 'FAILED') {
          statusChip.innerHTML = `<span class="rule-status-chip fail">${Icons.xCircle} 校验失败 (${r.last_verify_time || ''})</span>`;
        } else {
          statusChip.innerHTML = `<span class="rule-status-chip none">● 待校验</span>`;
        }
      }

      const params = r.parameters || {};
      const paramsJson = JSON.stringify(params, null, 2);

      body.innerHTML = `
        <div style="font-size:16px; font-weight:700; color:var(--g-text-primary);">${escapeHtml(r.name)}</div>
        <div class="rule-core-callout">
          <span class="callout-icon">${Icons.bulb}</span>
          <span class="callout-text" style="font-size:13px; font-weight:600;">${escapeHtml(r.summary || '')}</span>
        </div>

        <div class="rule-meta-grid" style="grid-template-columns: 1fr 1fr; gap:10px; padding:12px;">
          <div class="rule-meta-row">
            <span class="rule-meta-label">${Icons.zap} 触发环节</span>
            <span class="rule-meta-val" style="font-weight:600;">${escapeHtml(r.trigger_phase || '全流程')}</span>
          </div>
          <div class="rule-meta-row">
            <span class="rule-meta-label">${Icons.target} 涉及目标</span>
            <span class="rule-meta-val"><code class="rule-meta-code">${escapeHtml(r.target_api_table || 'N/A')}</code></span>
          </div>
          <div class="rule-meta-row">
            <span class="rule-meta-label">${Icons.activity} 自动化用例</span>
            <span class="rule-meta-val"><code class="rule-meta-code">${escapeHtml(r.test_id || 'N/A')}</code></span>
          </div>
          <div class="rule-meta-row">
            <span class="rule-meta-label">${Icons.lock} 门禁防篡改</span>
            <span class="rule-meta-val">${r.severity === 'BLOCK' ? '强门禁·数据库及接口级物理阻断' : '软预警·界面弹窗提醒并记入审计'}</span>
          </div>
        </div>

        <div>
          <div style="font-size:12px; font-weight:700; color:var(--g-text-secondary); margin-bottom:6px; display:inline-flex; align-items:center; gap:5px;">${Icons.bookOpen} 临床痛点背景与国家/行业业务规范说明:</div>
          <div style="background:var(--g-surface-variant); border:1px solid var(--g-border-subtle); border-radius:6px; padding:12px 14px; font-size:12.5px; line-height:1.7; white-space:pre-wrap; color:var(--g-text-primary); max-height:220px; overflow-y:auto;">${escapeHtml(r.detail || '暂无详细描述')}</div>
        </div>

        ${Object.keys(params).length > 0 ? `
          <div>
            <div style="font-size:12px; font-weight:700; color:var(--g-text-secondary); margin-bottom:6px; display:inline-flex; align-items:center; gap:5px;">${Icons.gear} 当前动态控制参数 (JSON):</div>
            <pre style="background:#1e1e1e; color:#9cdcfe; font-family:var(--g-mono); font-size:12px; padding:10px 14px; border-radius:6px; max-height:140px; overflow:auto; margin:0;">${escapeHtml(paramsJson)}</pre>
          </div>
        ` : ''}

        ${(r.last_verify_log && r.last_verify_log.length > 0) ? `
          <div>
            <div style="font-size:12px; font-weight:700; color:var(--g-text-secondary); margin-bottom:6px; display:inline-flex; align-items:center; gap:5px;">${Icons.document} 最近断言校验执行日志:</div>
            <pre style="background:var(--g-surface-variant); border:1px solid var(--g-border-subtle); font-family:var(--g-mono); font-size:11px; padding:8px 12px; border-radius:6px; max-height:120px; overflow:auto; margin:0; line-height:1.5;">${escapeHtml(r.last_verify_log.join('\n'))}</pre>
          </div>
        ` : ''}
      `;

      if (btnVerify) {
        btnVerify.onclick = async () => {
          await verifySingleRule(ruleId, btnVerify);
          openRuleDetailModal(ruleId);
        };
      }
      if (btnEdit) {
        btnEdit.onclick = () => {
          modal.style.display = 'none';
          openEditRuleModal(ruleId);
        };
      }

      modal.style.display = 'flex';
    }

    // Verify rules in a single group
    async function verifyGroupRules(domain, btnElement) {
      const origText = btnElement ? btnElement.innerHTML : '';
      if (btnElement) {
        btnElement.innerHTML = `${Icons.clock} 校验中...`;
        btnElement.disabled = true;
      }
      showToast(`正在批量校验分组 [${domain}] 规则...`, 'run', '分组校验启动', 2500);
      try {
        const rulesToVerify = allBusinessRules.filter(r => (r.domain || 'other') === domain && r.enabled !== false);
        for (const r of rulesToVerify) {
          await fetch(`/api/rules/${r.id}/verify`, { method: 'POST' });
        }
        await loadBusinessRules();
        showToast(`分组 [${domain}] 规则校验完成！`, 'success', '校验完成', 3000);
      } catch (err) {
        showToast(`校验分组规则失败: ${err}`, 'danger', '校验失败', 4000);
      } finally {
        if (btnElement) {
          btnElement.innerHTML = origText;
          btnElement.disabled = false;
        }
      }
    }

    // Verify single rule
    async function verifySingleRule(ruleId, btnElement) {
      const origText = btnElement ? btnElement.innerHTML : '';
      if (btnElement) {
        btnElement.innerHTML = `${Icons.clock} 校验中...`;
        btnElement.disabled = true;
      }
      showToast(`正在现场执行规则 [${ruleId}] 断言测试...`, 'run', '单项校验', 2000);

      try {
        const resp = await fetch(`/api/rules/${ruleId}/verify`, { method: 'POST' });
        const data = await resp.json();
        if (data.status === 'ok') {
          const res = data.result;
          await loadBusinessRules();
          if (res.status === 'PASSED') {
            showToast(`规则 [${ruleId}] 校验通过！耗时 ${res.duration_ms || 0}ms`, 'success', '校验通过', 3500);
          } else if (res.status === 'FAILED') {
            showToast(`规则 [${ruleId}] 校验未通过: ${res.error || ''}`, 'danger', '校验失败', 5000);
            viewRuleLogs(ruleId);
          }
        } else {
          showToast(`校验异常: ${data.error || '未知错误'}`, 'danger', '校验异常', 4000);
        }
      } catch (err) {
        showToast(`网络请求异常: ${err}`, 'danger', '网络异常', 4000);
      } finally {
        if (btnElement) {
          btnElement.innerHTML = origText;
          btnElement.disabled = false;
        }
      }
    }

    // Verify all rules
    const btnVerifyAllRulesEl = document.getElementById('btnVerifyAllRules');
    if (btnVerifyAllRulesEl) {
      btnVerifyAllRulesEl.addEventListener('click', async () => {
        btnVerifyAllRulesEl.innerHTML = `${Icons.clock} 正在全量自动化验收 16 条规则...`;
        btnVerifyAllRulesEl.disabled = true;
        showToast('已启动全院 16 项业务规则全量自动化验收...', 'run', '全规则验收启动', 3000);

        try {
          const resp = await fetch('/api/rules/verify_all', { method: 'POST' });
          const data = await resp.json();
          await loadBusinessRules();
          showToast(`业务规则自动化验收完成！通过率: ${data.passed} / ${data.total} 条，失败 ${data.failed} 条`, data.failed > 0 ? 'warning' : 'success', '验收完成', 5000);
        } catch (err) {
          showToast(`全规则校验异常: ${err}`, 'danger', '校验异常', 4000);
        } finally {
          btnVerifyAllRulesEl.innerHTML = `${Icons.zap} 一键全规则自动化验收`;
          btnVerifyAllRulesEl.disabled = false;
        }
      });
    }

    // Refresh & Reset Rules Buttons
    const btnRefreshRulesEl = document.getElementById('btnRefreshRules');
    if (btnRefreshRulesEl) {
      btnRefreshRulesEl.addEventListener('click', async () => {
        await loadBusinessRules();
        showToast('业务规则与指标数据已刷新！', 'info', '刷新完成', 2000);
      });
    }

    const btnResetRulesEl = document.getElementById('btnResetRules');
    if (btnResetRulesEl) {
      btnResetRulesEl.addEventListener('click', async () => {
        if (!confirm('确定要恢复系统预设的标准 16 条业务规则吗？自定义规则将被清除。')) return;
        try {
          const resp = await fetch('/api/rules/reset', { method: 'POST' });
          const data = await resp.json();
          await loadBusinessRules();
          showToast('已成功恢复系统出厂 16 条标准业务规则！', 'success', '重置成功', 3500);
        } catch (err) {
          showToast(`恢复默认异常: ${err}`, 'danger', '重置失败', 4000);
        }
      });
    }

    // Toggle rule enabled
    async function toggleRuleEnabled(ruleId, enabled) {
      try {
        await fetch(`/api/rules/${ruleId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: enabled })
        });
        const rule = allBusinessRules.find(r => r.id === ruleId);
        if (rule) rule.enabled = enabled;
        renderBusinessRules();
      } catch (err) {
        console.error("Failed to toggle rule:", err);
      }
    }

    // Edit Rule Modal
    function openEditRuleModal(ruleId) {
      const rule = allBusinessRules.find(r => r.id === ruleId);
      if (!rule) return;

      document.getElementById('editRuleId').value = rule.id;
      document.getElementById('editModalRuleIdBadge').innerText = rule.id;
      document.getElementById('editRuleName').value = rule.name || '';
      document.getElementById('editRuleSeverity').value = rule.severity || 'BLOCK';
      document.getElementById('editRulePhase').value = rule.trigger_phase || '';
      document.getElementById('editRuleTarget').value = rule.target_api_table || '';
      document.getElementById('editRuleSummary').value = rule.summary || '';
      document.getElementById('editRuleDetail').value = rule.detail || '';
      document.getElementById('editRuleParams').value = JSON.stringify(rule.parameters || {}, null, 2);
      document.getElementById('editRuleEnabled').checked = (rule.enabled !== false);

      const modal = document.getElementById('ruleEditModal');
      modal.style.display = 'flex';
    }

    function formatEditJsonParams() {
      const ta = document.getElementById('editRuleParams');
      try {
        const parsed = JSON.parse(ta.value);
        ta.value = JSON.stringify(parsed, null, 2);
        showToast('JSON 格式校验通过并已美化格式！', 'success', '格式化成功', 2000);
      } catch (err) {
        showToast("JSON 语法有误，无法格式化: " + err, 'warning', '格式错误', 3500);
      }
    }

    const ruleEditFormEl = document.getElementById('ruleEditForm');
    if (ruleEditFormEl) {
      ruleEditFormEl.addEventListener('submit', async (e) => {
        e.preventDefault();
        const ruleId = document.getElementById('editRuleId').value;
        let params = {};
        try {
          params = JSON.parse(document.getElementById('editRuleParams').value || '{}');
        } catch (err) {
          showToast("控制参数必须为有效的 JSON 格式！", 'warning', '参数格式错误', 3500);
          return;
        }

        const payload = {
          name: document.getElementById('editRuleName').value.trim(),
          severity: document.getElementById('editRuleSeverity').value,
          trigger_phase: document.getElementById('editRulePhase').value.trim(),
          target_api_table: document.getElementById('editRuleTarget').value.trim(),
          summary: document.getElementById('editRuleSummary').value.trim(),
          detail: document.getElementById('editRuleDetail').value.trim(),
          parameters: params,
          enabled: document.getElementById('editRuleEnabled').checked
        };

        try {
          const resp = await fetch(`/api/rules/${ruleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const res = await resp.json();
          if (res.status === 'ok') {
            document.getElementById('ruleEditModal').style.display = 'none';
            await loadBusinessRules();
            showToast(`业务规则 [${ruleId}] 配置已更新并持久化保存！`, 'success', '规则保存成功', 3500);
          } else {
            showToast(`保存失败: ${res.error}`, 'danger', '保存失败', 4000);
          }
        } catch (err) {
          showToast(`网络异常: ${err}`, 'danger', '请求异常', 4000);
        }
      });
    }

    // View rule logs modal
    function viewRuleLogs(ruleId) {
      const rule = allBusinessRules.find(r => r.id === ruleId);
      if (!rule) return;

      document.getElementById('logModalRuleName').innerText = `[${rule.id}] ${rule.name}`;
      const logs = rule.last_verify_log || ['暂无执行日志'];
      const formatted = logs.map(line => {
        if (line.includes('✓') || line.includes('✅')) return `<span style="color:#4ade80;">${line}</span>`;
        if (line.includes('❌') || line.includes('ERROR')) return `<span style="color:#f87171; font-weight:700;">${line}</span>`;
        if (line.includes('👉') || line.includes('🚀')) return `<span style="color:#60a5fa;">${line}</span>`;
        if (line.includes('ℹ️') || line.includes('⚠️')) return `<span style="color:#fbbf24;">${line}</span>`;
        return line;
      }).join('\n');

      document.getElementById('ruleLogContent').innerHTML = formatted;
      document.getElementById('ruleLogModal').style.display = 'flex';
    }

    // =========================================================================
    // Create & Delete Business Rule Handlers
    // =========================================================================
    const btnOpenCreateRuleModalEl = document.getElementById('btnOpenCreateRuleModal');
    if (btnOpenCreateRuleModalEl) {
      btnOpenCreateRuleModalEl.addEventListener('click', () => {
        openCreateRuleModal();
      });
    }

    function openCreateRuleModal() {
      const domain = document.getElementById('createRuleDomain').value || 'outpatient';
      const prefix = domain === 'inpatient' ? 'RULE_IP_' : (domain === 'outpatient' ? 'RULE_OP_' : 'RULE_CUSTOM_');
      let count = allBusinessRules.filter(r => r.id && r.id.startsWith(prefix)).length + 1;
      let suggestedId = `${prefix}${count < 10 ? '0' : ''}${count}`;
      while (allBusinessRules.some(r => r.id === suggestedId)) {
        count++;
        suggestedId = `${prefix}${count < 10 ? '0' : ''}${count}`;
      }

      document.getElementById('createRuleId').value = suggestedId;
      document.getElementById('createRuleName').value = '';
      document.getElementById('createRulePhase').value = '';
      document.getElementById('createRuleTarget').value = '';
      document.getElementById('createRuleSummary').value = '';
      document.getElementById('createRuleDetail').value = '';
      document.getElementById('createRuleParams').value = '{\n  "enforceGate": true,\n  "maxThreshold": 5\n}';
      document.getElementById('createRuleEnabled').checked = true;

      document.getElementById('ruleCreateModal').style.display = 'flex';
    }

    const createDomainEl = document.getElementById('createRuleDomain');
    if (createDomainEl) {
      createDomainEl.addEventListener('change', (e) => {
        const domain = e.target.value;
        const prefix = domain === 'inpatient' ? 'RULE_IP_' : (domain === 'outpatient' ? 'RULE_OP_' : 'RULE_CUSTOM_');
        let count = allBusinessRules.filter(r => r.id && r.id.startsWith(prefix)).length + 1;
        let suggestedId = `${prefix}${count < 10 ? '0' : ''}${count}`;
        while (allBusinessRules.some(r => r.id === suggestedId)) {
          count++;
          suggestedId = `${prefix}${count < 10 ? '0' : ''}${count}`;
        }
        document.getElementById('createRuleId').value = suggestedId;
      });
    }

    function formatCreateJsonParams() {
      const ta = document.getElementById('createRuleParams');
      try {
        const parsed = JSON.parse(ta.value);
        ta.value = JSON.stringify(parsed, null, 2);
        showToast('JSON 格式校验通过并已美化格式！', 'success', '格式化成功', 2000);
      } catch (err) {
        showToast("JSON 语法有误，无法格式化: " + err, 'warning', '格式错误', 3500);
      }
    }

    const ruleCreateFormEl = document.getElementById('ruleCreateForm');
    if (ruleCreateFormEl) {
      ruleCreateFormEl.addEventListener('submit', async (e) => {
        e.preventDefault();
        let params = {};
        const paramsText = document.getElementById('createRuleParams').value.trim();
        if (paramsText) {
          try {
            params = JSON.parse(paramsText);
          } catch (err) {
            showToast("控制参数必须为有效的 JSON 格式！", 'warning', '参数格式错误', 3500);
            return;
          }
        }

        const domainVal = document.getElementById('createRuleDomain').value;
        const domainNames = {
          inpatient: '住院业务',
          outpatient: '门诊业务',
          pharmacy: '药房药库',
          emr: '电子病历',
          charge: '计费财务',
          system: '系统底座'
        };

        const payload = {
          id: document.getElementById('createRuleId').value.trim() || undefined,
          domain: domainVal,
          domain_name: domainNames[domainVal] || '综合规则',
          name: document.getElementById('createRuleName').value.trim(),
          severity: document.getElementById('createRuleSeverity').value,
          trigger_phase: document.getElementById('createRulePhase').value.trim(),
          target_api_table: document.getElementById('createRuleTarget').value.trim(),
          summary: document.getElementById('createRuleSummary').value.trim(),
          detail: document.getElementById('createRuleDetail').value.trim(),
          parameters: params,
          enabled: document.getElementById('createRuleEnabled').checked
        };

        try {
          const resp = await fetch('/api/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const res = await resp.json();
          if (res.status === 'ok') {
            document.getElementById('ruleCreateModal').style.display = 'none';
            await loadBusinessRules();
            showToast(`新增业务规则 [${res.rule.id}] 成功并已持久化保存！`, 'success', '规则创建成功', 4000);
          } else {
            showToast(`新增规则失败: ${res.error || '未知错误'}`, 'danger', '创建失败', 4000);
          }
        } catch (err) {
          showToast(`网络异常: ${err}`, 'danger', '请求异常', 4000);
        }
      });
    }

    // ${Icons.trash} Delete Rule
    async function deleteRule(ruleId) {
      if (!confirm(`确定要彻底删除业务规则 [${ruleId}] 吗？`)) return;
      try {
        const resp = await fetch(`/api/rules/${ruleId}`, { method: 'DELETE' });
        const res = await resp.json();
        if (res.status === 'ok') {
          await loadBusinessRules();
          showToast(`规则 [${ruleId}] 已成功删除！`, 'info', '删除成功', 3000);
        } else {
          showToast(`删除失败: ${res.error || '未知错误'}`, 'danger', '删除失败', 4000);
        }
      } catch (err) {
        showToast(`删除异常: ${err}`, 'danger', '请求异常', 4000);
      }
    }

    // WebSocket event handler for rule live events
    function handleRuleSocketEvent(msg) {
      if (msg.type === 'rule_verify_done' || msg.type === 'rule_update' || msg.type === 'rule_create' || msg.type === 'rule_delete') {
        loadBusinessRules();
      } else if (msg.type === 'env_change') {
        loadEnvironmentStatus();
      }
    }

    // Keyboard shortcut / for search
    window.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        document.getElementById('searchInput').focus();
      }
    });
