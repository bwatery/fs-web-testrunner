    // Switch to Validator Tab via Header Button (if exists)
    const bnv = document.getElementById('btnNavValidator');
    if (bnv) {
      bnv.addEventListener('click', () => {
        const tabEl = document.querySelector('.tab-item[data-tab="tab-validator"]');
        if (tabEl) tabEl.click();
        checkValidatorStatus();
      });
    }

    document.getElementById('btnTriggerValidate').addEventListener('click', () => {
      checkValidatorStatus(true);
    });

    document.getElementById('btnValidatorOpenBrowser').addEventListener('click', async () => {
      await fetch('/api/open_browser', { method: 'POST' });
      setTimeout(checkValidatorStatus, 1500);
    });

    async function checkValidatorStatus(manual = false) {
      const chip = document.getElementById('validatorGlobalChip');
      if (manual && chip) chip.innerHTML = '● 正在请求诊断...';
      
      try {
        const resp = await fetch('/api/validator/status');
        const data = await resp.json();
        liveValidatorData = data;
        renderValidatorData(data);
      } catch (err) {
        console.error("Validator check failed:", err);
        if (chip) {
          chip.className = 'status-chip fail';
          chip.innerHTML = '● 后端连接失败';
        }
      }
    }

    function renderValidatorData(data) {
      const chip = document.getElementById('validatorGlobalChip');
      const loginBadge = document.getElementById('valLoginBadge');
      const dbBadge = document.getElementById('valDbBadge');

      if (data.status === 'FAIL') {
        if (chip) {
          chip.className = 'status-chip fail';
          chip.innerHTML = '● 浏览器未连接';
        }
        if (loginBadge) {
          loginBadge.className = 'status-chip fail';
          loginBadge.innerText = '未连接 Chrome';
        }
        document.getElementById('valRoute').innerText = data.message || '未启动 Chrome 调试通道';
        return;
      }

      if (data.status === 'WAITING_LOGIN') {
        if (chip) {
          chip.className = 'status-chip pending';
          chip.innerHTML = '● 等待在 Chrome 中登录';
        }
        if (loginBadge) {
          loginBadge.className = 'status-chip pending';
          loginBadge.innerText = '未登录';
        }
        const s = data.details || {};
        document.getElementById('valRoute').innerText = s.href || '-';
        document.getElementById('valTitle').innerText = s.title || '-';
        document.getElementById('valTokenText').innerText = '当前未检测到 token，请在弹出的 Chrome 窗口中输入工号密码并点击【登录】';
        return;
      }

      // Success
      if (chip) {
        chip.className = 'status-chip pass';
        chip.innerHTML = '● 登录正常 (已连接 HIS 后端)';
      }
      if (loginBadge) {
        loginBadge.className = 'status-chip pass';
        loginBadge.innerText = '有效已认证';
      }
      if (dbBadge) {
        dbBadge.className = 'status-chip pass';
        dbBadge.innerText = 'Oracle 11g/19c 畅通';
      }

      const s = data.session || {};
      const svcs = data.services || {};

      document.getElementById('valUsername').innerText = s.username || 'admin';
      const uInfo = svcs.user_info || {};
      document.getElementById('valRole').innerText = `${uInfo.role_name || '住院医生'} (${uInfo.role_key || 'ZYYS'})`;
      
      const patQueue = svcs.patient_queue || {};
      document.getElementById('valDept').innerText = `科室ID: ${patQueue.dept_id || 910092} (在院 ${patQueue.patient_count || 0} 人)`;
      document.getElementById('valRoute').innerText = s.current_page || '-';
      document.getElementById('valRoute').title = s.current_page || '';
      document.getElementById('valTitle').innerText = s.page_title || '-';
      document.getElementById('valTokenText').innerText = s.token ? `Bearer ${s.token}` : '-';

      // Services
      // 1. UserInfo
      const svcUser = svcs.user_info || {};
      document.getElementById('svcUserStatus').className = svcUser.status === 'PASS' ? 'status-chip pass' : 'status-chip fail';
      document.getElementById('svcUserStatus').innerText = svcUser.status || 'PASS';
      document.getElementById('svcUserMsg').innerText = `${svcUser.message || '通过'} (耗时 ${svcUser.elapsed_ms || 0}ms)`;

      // 2. Patient Queue
      const svcPat = svcs.patient_queue || {};
      document.getElementById('svcPatStatus').className = svcPat.status === 'PASS' ? 'status-chip pass' : 'status-chip pending';
      document.getElementById('svcPatStatus').innerText = svcPat.status || 'PASS';
      document.getElementById('svcPatMsg').innerText = `${svcPat.message || '正常'} (耗时 ${svcPat.elapsed_ms || 0}ms)`;
      const patSampleEl = document.getElementById('svcPatSamples');
      if (svcPat.samples && svcPat.samples.length > 0) {
        patSampleEl.innerHTML = svcPat.samples.map(p => `• 床位: ${p.bedNo} | 患者: <b>${p.patientName}</b> (住院号: ${p.inpatientNo})`).join('&nbsp;&nbsp;|&nbsp;&nbsp;');
      } else {
        patSampleEl.innerText = '';
      }

      // 3. Order Dict
      const svcOrder = svcs.order_dict || {};
      document.getElementById('svcOrderDictStatus').className = svcOrder.status === 'PASS' ? 'status-chip pass' : 'status-chip fail';
      document.getElementById('svcOrderDictStatus').innerText = svcOrder.status || 'PASS';
      document.getElementById('svcOrderDictMsg').innerText = `${svcOrder.message || '正常'} (耗时 ${svcOrder.elapsed_ms || 0}ms)`;
      const sample = svcOrder.sample || {};
      if (sample.itemName) {
        document.getElementById('svcOrderDictSample').innerText = `示例数据: [${sample.itemId}] ${sample.itemName} ${sample.specs || ''} (单价: ¥${sample.price || 0}/${sample.packageUnit || ''})`;
      }

      // 4. Rule Engine
      const svcRule = svcs.order_rule_service || {};
      document.getElementById('svcRuleStatus').className = svcRule.status === 'PASS' ? 'status-chip pass' : 'status-chip pending';
      document.getElementById('svcRuleStatus').innerText = svcRule.status || 'PASS';
      document.getElementById('svcRuleMsg').innerText = svcRule.message || '规则引擎活跃';
    }

    // Copy Bearer & JWT
    document.getElementById('btnCopyBearer').addEventListener('click', () => {
      const tok = liveValidatorData?.session?.token;
      if (!tok) return showToast('当前尚未获取到 Token，请先完成登录认证', 'warning', '暂无凭证');
      navigator.clipboard.writeText(`Bearer ${tok}`).then(() => showToast('Bearer Token 已成功复制到剪贴板！', 'copy', '复制成功', 2500));
    });

    document.getElementById('btnCopyJwt').addEventListener('click', () => {
      const tok = liveValidatorData?.session?.token;
      if (!tok) return showToast('当前尚未获取到 Token，请先完成登录认证', 'warning', '暂无凭证');
      navigator.clipboard.writeText(tok).then(() => showToast('原始 JWT Token 已成功复制到剪贴板！', 'copy', '复制成功', 2500));
    });

    // Auto-polling checkbox
    document.getElementById('chkAutoPollValidator').addEventListener('change', (e) => {
      if (e.target.checked) {
        startValidatorPolling();
      } else {
        stopValidatorPolling();
      }
    });

    function startValidatorPolling() {
      stopValidatorPolling();
      validatorPollInterval = setInterval(() => {
        const activeTab = document.querySelector('.tab-item.active');
        if (activeTab && activeTab.dataset.tab === 'tab-validator') {
          checkValidatorStatus();
        }
      }, 5000);
    }

    function stopValidatorPolling() {
      if (validatorPollInterval) {
        clearInterval(validatorPollInterval);
        validatorPollInterval = null;
      }
    }

    // Order items search
    async function searchOrderItems(kw = "") {
      const classify = document.getElementById('orderClassifySelect').value;
      const tbody = document.getElementById('orderSearchResultBody');
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--g-text-secondary);"><span style="display:inline-flex; align-items:center; gap:6px;">${Icons.clock} 正在通过 HIS 后端查询 Oracle 数据库...</span></td></tr>`;

      try {
        const resp = await fetch('/api/validator/search_order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            keyword: kw,
            classifyType: classify,
            pageNum: 1,
            pageSize: 15
          })
        });
        const res = await resp.json();
        if (res.status !== 'SUCCESS') {
          tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:var(--g-red);">检索失败: ${res.message || '未知异常'}</td></tr>`;
          return;
        }

        const items = res.items || [];
        cachedOrderItems = items;
        document.getElementById('searchResultCountBadge').innerText = `已检索到 ${res.count || items.length} 条 (Oracle 耗时 ${res.elapsed_ms || 0}ms)`;

        if (items.length === 0) {
          tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--g-text-tertiary);">未匹配到包含 "${kw}" 的药品或项目</td></tr>`;
          return;
        }

        tbody.innerHTML = '';
        items.forEach((item, idx) => {
          const tr = document.createElement('tr');
          const typeName = item.itemSysTypeName || (item.drugType === 'Z' ? '中药' : '西药');
          tr.innerHTML = `
            <td style="font-family:var(--g-mono); font-weight:600; color:var(--g-blue);">${item.itemId || item.itemNo}</td>
            <td style="font-weight:600;">${item.itemName || '-'}</td>
            <td style="font-size:12px; color:var(--g-text-secondary);">${item.specs || '-'}</td>
            <td style="font-weight:600; color:#b45309;">¥${item.price != null ? Number(item.price).toFixed(2) : '0.00'}</td>
            <td style="font-size:12px;">${item.packageUnit || item.bulkUnit || '支'}</td>
            <td style="font-family:var(--g-mono); font-size:12px; color:var(--g-text-secondary);">${item.spellCode || '-'}</td>
            <td><span class="module-badge">${typeName}</span></td>
            <td style="text-align:center;">
              <button class="g-btn g-btn-tonal" style="height:24px; font-size:11px; padding:0 8px;" onclick="inspectOrderPayload(${idx})">${Icons.document} 查看报文</button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:var(--g-red);">网络或接口请求错误: ${err}</td></tr>`;
      }
    }

    window.quickSearchOrder = function(kw) {
      document.getElementById('orderSearchInput').value = kw;
      searchOrderItems(kw);
    };

    document.getElementById('btnSearchOrderItems').addEventListener('click', () => {
      const kw = document.getElementById('orderSearchInput').value;
      searchOrderItems(kw);
    });

    document.getElementById('orderSearchInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        searchOrderItems(e.target.value);
      }
    });

    window.inspectOrderPayload = function(idx) {
      const item = cachedOrderItems[idx];
      if (!item) return;

      const modal = document.getElementById('orderPayloadModal');
      const jsonEl = document.getElementById('orderPayloadJson');
      
      const samplePayload = {
        patientId: 10001,
        inpatientNo: "000010",
        deptId: 910092,
        orderDoctorId: liveValidatorData?.session?.username || "admin",
        orderType: "LONG",
        orderClassify: item.drugType || "W",
        items: [
          {
            itemId: item.itemId,
            itemNo: item.itemNo,
            itemName: item.itemName,
            specs: item.specs,
            price: item.price,
            packageUnit: item.packageUnit,
            dosage: item.stdDosage || 1,
            dosageUnit: item.stdDosageUnit || "ml",
            frequencyCode: "QD",
            frequencyName: "每日一次",
            usageCode: "IVGTT",
            usageName: "静脉滴注",
            qty: 1
          }
        ],
        validateEngine: "FAITH_ORACLE_ENGINE_V2",
        status: "READY_TO_SUBMIT"
      };

      jsonEl.innerText = JSON.stringify(samplePayload, null, 2);
      modal.style.display = 'flex';
    };

    // -------------------------------------------------------------
    // Role & Department Switching Hub Logic (方案 1 & 3)
    // -------------------------------------------------------------
    let allRolePresets = [];
    let allAvailableRoles = [];

    async function loadRolePresets() {
      try {
        const resp = await fetch('/api/validator/role_presets');
        const data = await resp.json();
        allRolePresets = data.presets || [];
        renderRolePresetCards(allRolePresets);
      } catch (err) {
        console.error("Failed to load role presets:", err);
      }
    }

    function renderRolePresetCards(presets) {
      const container = document.getElementById('rolePresetsContainer');
      if (!container) return;
      container.innerHTML = '';

      presets.forEach(p => {
        const card = document.createElement('div');
        card.className = 'module-card';
        card.style.padding = '12px 14px';
        card.style.gap = '6px';
        card.style.background = 'var(--g-surface)';
        card.style.cursor = 'pointer';
        card.style.border = '1px solid var(--g-border)';
        card.style.transition = 'all 0.15s ease';

        const roleIcon = getRoleSvg(p.icon || p.roleName || p.roleKey);
        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:600; font-size:13px; display:flex; align-items:center; gap:6px;">
              <span>${roleIcon}</span> <span>${p.roleName}</span>
            </div>
            <span class="module-badge" style="font-family:var(--g-mono); font-size:10px;">${p.roleKey}</span>
          </div>
          <div style="font-size:12px; color:var(--g-blue); font-weight:500;">
            科室: ${p.deptName} (${p.deptId})
          </div>
          <div style="font-size:11px; color:var(--g-text-secondary); line-height:1.4;">
            ${p.desc}
          </div>
          <div style="display:flex; justify-content:flex-end; margin-top:4px;">
            <span style="font-size:11px; font-weight:600; color:var(--g-blue); background:var(--g-blue-surface); padding:2px 8px; border-radius:10px; display:inline-flex; align-items:center; gap:3px;">
              一键切岗 ${Icons.arrowRight}
            </span>
          </div>
        `;

        card.addEventListener('click', () => {
          executeSwitchIdentity(p.roleId, p.deptId, p.route, `${p.roleName} · ${p.deptName}`);
        });

        container.appendChild(card);
      });
    }

    async function loadRolesDropdown() {
      try {
        const resp = await fetch('/api/validator/roles');
        const data = await resp.json();
        allAvailableRoles = data.roles || [];
        const roleSel = document.getElementById('switchRoleSelect');
        if (!roleSel) return;
        roleSel.innerHTML = '<option value="">-- 请选择目标角色 (15种) --</option>';
        allAvailableRoles.forEach(r => {
          const opt = document.createElement('option');
          opt.value = r.roleId;
          opt.innerText = `[${r.roleId}] ${r.roleName} (${r.roleKey})`;
          roleSel.appendChild(opt);
        });

        roleSel.value = '15';
        await onRoleSelected(15);
      } catch (err) {
        console.error("Failed to load roles:", err);
      }
    }

    async function onRoleSelected(roleId) {
      const deptSel = document.getElementById('switchDeptSelect');
      if (!deptSel) return;
      deptSel.innerHTML = '<option value="">正在加载科室...</option>';
      try {
        const resp = await fetch(`/api/validator/depts?roleId=${roleId}`);
        const data = await resp.json();
        const depts = data.depts || [];
        deptSel.innerHTML = '';
        depts.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d.deptId;
          opt.innerText = `${d.deptName} (代码: ${d.deptId} / 类型: ${d.deptType || '-'})`;
          deptSel.appendChild(opt);
        });

        const preset = allRolePresets.find(p => p.roleId === Number(roleId));
        if (preset) {
          document.getElementById('switchRouteInput').value = preset.route;
          if (preset.deptId) deptSel.value = String(preset.deptId);
        } else {
          document.getElementById('switchRouteInput').value = '#/index';
        }
      } catch (err) {
        console.error("Failed to load depts:", err);
      }
    }

    document.getElementById('switchRoleSelect').addEventListener('change', (e) => {
      const rid = e.target.value;
      if (rid) onRoleSelected(rid);
    });

    async function executeSwitchIdentity(roleId, deptId, targetRoute, label = "") {
      const fb = document.getElementById('switchFeedback');
      if (fb) fb.innerText = `正在切换身份至 [${label || roleId}]...`;

      try {
        const resp = await fetch('/api/validator/switch_identity', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            roleId: Number(roleId),
            deptId: Number(deptId),
            targetRoute: targetRoute || ""
          })
        });
        const res = await resp.json();
        if (res.status === 'SUCCESS') {
          showToast(`身份已切换至: ${label || roleId}`, 'role', '换岗成功', 3500);
          if (fb) {
            fb.style.color = 'var(--g-green)';
            fb.innerText = `切换成功！浏览器正在载入工作站...`;
          }
          const badge = document.getElementById('switchStatusBadge');
          if (badge) {
            badge.style.display = 'inline-block';
            badge.innerText = `已切换至: ${label || roleId}`;
          }
          setTimeout(() => {
            checkValidatorStatus();
            if (fb) fb.innerText = '';
          }, 3000);
        } else {
          showToast(`换岗失败: ${res.message || '未知错误'}`, 'danger', '切换失败', 4000);
          if (fb) {
            fb.style.color = 'var(--g-red)';
            fb.innerText = `切换失败: ${res.message || '未知错误'}`;
          }
        }
      } catch (err) {
        showToast(`换岗请求异常: ${err}`, 'danger', '请求异常', 4000);
        if (fb) {
          fb.style.color = 'var(--g-red)';
          fb.innerText = `请求异常: ${err}`;
        }
      }
    }

    document.getElementById('btnExecuteSwitch').addEventListener('click', () => {
      const roleId = document.getElementById('switchRoleSelect').value;
      const deptId = document.getElementById('switchDeptSelect').value;
      const route = document.getElementById('switchRouteInput').value;
      if (!roleId || !deptId) return showToast('请先选择角色和科室！', 'warning', '操作提示');
      const roleName = document.getElementById('switchRoleSelect').selectedOptions[0]?.text;
      const deptName = document.getElementById('switchDeptSelect').selectedOptions[0]?.text;
      executeSwitchIdentity(roleId, deptId, route, `${roleName} · ${deptName}`);
    });

    document.getElementById('btnExecutePreset').addEventListener('click', async () => {
      const roleId = document.getElementById('switchRoleSelect').value;
      const deptId = document.getElementById('switchDeptSelect').value;
      const route = document.getElementById('switchRouteInput').value;
      if (!roleId || !deptId) return showToast('请先选择角色和科室！', 'warning', '操作提示');
      
      const roleName = document.getElementById('switchRoleSelect').selectedOptions[0]?.text;
      const deptName = document.getElementById('switchDeptSelect').selectedOptions[0]?.text;
      const fb = document.getElementById('switchFeedback');
      if (fb) fb.innerText = '正在预置身份缓存...';

      try {
        const resp = await fetch('/api/validator/preset_identity', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            roleId: Number(roleId),
            deptId: Number(deptId),
            targetRoute: route || ""
          })
        });
        const res = await resp.json();
        if (res.status === 'SUCCESS') {
          showToast(`已成功预设下次登录身份: ${roleName} · ${deptName}`, 'role', '预设已保存', 3500);
          if (fb) {
            fb.style.color = 'var(--g-green)';
            fb.innerText = `预置成功！下次在 Chrome 中登录将直接进入此岗位！`;
          }
        } else {
          showToast(`预设身份失败: ${res.message || '未知错误'}`, 'danger', '预设失败', 4000);
          if (fb) {
            fb.style.color = 'var(--g-red)';
            fb.innerText = res.message;
          }
        }
      } catch (err) {
        showToast(`预设请求异常: ${err}`, 'danger', '请求异常', 4000);
        if (fb) {
          fb.style.color = 'var(--g-red)';
          fb.innerText = `异常: ${err}`;
        }
      }
    });

