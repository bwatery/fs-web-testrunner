    function initWebSocket() {
      const loc = window.location;
      const wsUrl = (loc.protocol === 'https:' ? 'wss://' : 'ws://') + loc.host + '/ws';
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        syncRunnerStatus();
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWsEvent(msg);
      };

      ws.onclose = () => {
        setTimeout(initWebSocket, 2000);
      };
    }

    function handleWsEvent(msg) {
      const logs = document.getElementById('termLogsContainer');
      if (msg.type === 'LOG') {
        const line = document.createElement('div');
        line.className = `t-line ${msg.data.level}`;
        line.innerText = msg.data.message;
        logs.appendChild(line);
        logs.scrollTop = logs.scrollHeight;
        const latestEl = document.getElementById('termLatestLine');
        if (latestEl) latestEl.innerText = msg.data.message;
      } else if (msg.type === 'TEST_START') {
        const chip = document.getElementById(`status-${msg.data.test_id}`);
        if (chip) chip.innerHTML = `<span class="status-chip running">执行中...</span>`;
        const dot = document.getElementById(`nav-dot-${msg.data.test_id}`);
        if (dot) dot.className = 'nav-status-dot running';
      } else if (msg.type === 'TEST_END') {
        stats.executed++;
        if (msg.data.status === 'PASSED') {
          stats.passed++;
        } else {
          stats.failed++;
        }
        updateKpis();

        const chip = document.getElementById(`status-${msg.data.test_id}`);
        if (chip) {
          if (msg.data.status === 'PASSED') {
            chip.innerHTML = `<span class="status-chip passed">${Icons.checkCircle} 通过</span>`;
          } else {
            chip.innerHTML = `<span class="status-chip failed" title="${msg.data.error || ''}">${Icons.xCircle} 失败</span>`;
          }
        }
        const dot = document.getElementById(`nav-dot-${msg.data.test_id}`);
        if (dot) dot.className = msg.data.status === 'PASSED' ? 'nav-status-dot pass' : 'nav-status-dot fail';
        const dur = document.getElementById(`duration-${msg.data.test_id}`);
        if (dur) dur.innerText = `${msg.data.duration_ms} ms`;

        if (msg.data.screenshot_b64) {
          const img = document.getElementById('liveImgView');
          img.src = `data:image/jpeg;base64,${msg.data.screenshot_b64}`;
          img.style.display = 'block';
          document.getElementById('noImgTip').style.display = 'none';
        }
      } else if (msg.type === 'LOGIN_WAITING') {
        const banner = document.getElementById('loginAlertBanner');
        banner.style.display = 'flex';
        banner.style.background = 'var(--g-yellow-surface)';
        banner.style.borderColor = 'var(--g-yellow)';
        document.getElementById('loginAlertTitle').innerText = '【方案 B: 等待手动登录】已在独立 Chrome 窗口为您打开 HIS 登录页';
        document.getElementById('loginAlertDesc').innerText = '请在弹出的 Chrome 窗口中输入您的医生工号与密码并点击【登录】。系统检测到登录后将立即开始执行用例。';
        const timeout = msg.data.timeout || 180;
        const elapsed = msg.data.elapsed || 0;
        const remaining = msg.data.remaining != null ? msg.data.remaining : (timeout - elapsed);
        const pct = Math.min(100, Math.round((elapsed / timeout) * 100));
        const bar = document.getElementById('loginProgressBar');
        if (bar) {
          bar.style.width = pct + '%';
          bar.style.background = 'var(--g-yellow)';
        }
        document.getElementById('loginAlertCountdown').innerText = `已等待 ${elapsed} 秒 / 剩余 ${remaining} 秒`;
      } else if (msg.type === 'LOGIN_SUCCESS') {
        const banner = document.getElementById('loginAlertBanner');
        banner.style.display = 'flex';
        banner.style.background = 'var(--g-green-surface)';
        banner.style.borderColor = 'var(--g-green)';
        const bar = document.getElementById('loginProgressBar');
        if (bar) {
          bar.style.width = '100%';
          bar.style.background = 'var(--g-green)';
        }
        document.getElementById('loginAlertTitle').innerText = '登录验证通过！正在进入医生工作站执行用例...';
        document.getElementById('loginAlertDesc').innerText = '医生会话已绑定，正在自动加载患者与医嘱录入界面...';
        document.getElementById('loginAlertCountdown').innerText = '认证成功';
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
      } else if (msg.type === 'RUN_END' || msg.type === 'RUN_FINISH') {
        const banner = document.getElementById('loginAlertBanner');
        if (banner) banner.style.display = 'none';
        const stopBtn = document.getElementById('btnStop');
        if (stopBtn) {
          stopBtn.style.display = 'none';
          stopBtn.disabled = false;
          stopBtn.innerHTML = `${Icons.stop} 停止执行`;
        }
        const btnRunSel = document.getElementById('btnRunSelected');
        if (btnRunSel) btnRunSel.disabled = false;
        const btnRunAll = document.getElementById('btnRunAll');
        if (btnRunAll) btnRunAll.disabled = false;

        const now = Date.now();
        if (now - (window._lastRunFinishedToastTime || 0) > 3000) {
          window._lastRunFinishedToastTime = now;
          const failCount = stats.failed || 0;
          const passCount = stats.passed || 0;
          const total = stats.executed || 0;
          if (total > 0) {
            if (failCount > 0) {
              showToast(`测试执行完毕：共 ${total} 项，通过 ${passCount} 项，失败 ${failCount} 项`, 'warning', '测试执行完成', 5000);
            } else {
              showToast(`测试执行完毕：共 ${total} 项全部通过！`, 'success', '测试执行成功', 4500);
            }
          }
        }
      } else if (msg.type.startsWith('rule_') || msg.type === 'env_change') {
        handleRuleSocketEvent(msg);
      }
    }

    function updateKpis() {
      const execEl = document.getElementById('kpiExecuted');
      if (execEl) execEl.innerText = stats.executed;
      const passEl = document.getElementById('kpiPassed');
      if (passEl) {
        const rate = stats.executed > 0 ? Math.round((stats.passed / stats.executed) * 100) : 0;
        passEl.innerText = stats.executed > 0 ? `${stats.passed} (${rate}%)` : `${stats.passed}`;
      }
      const failEl = document.getElementById('kpiFailed');
      if (failEl) failEl.innerText = stats.failed;
    }

    function resetKpis() {
      stats.executed = 0;
      stats.passed = 0;
      stats.failed = 0;
      updateKpis();
    }

    // Run Configuration Modal & Summary Badge
    function updateConfigSummaryBadge() {
      const badge = document.getElementById('configSummaryBadge');
      if (!badge) return;
      const targetEl = document.getElementById('cfgFrontendUrl') || document.getElementById('envPresetSelect');
      const loginEl = document.getElementById('loginModeSelect');
      const chkHeadlessEl = document.getElementById('chkHeadless');
      const chkHeadlessModalEl = document.getElementById('chkHeadlessModal');
      
      const targetVal = targetEl ? (targetEl.value || '') : '';
      const targetStr = (targetVal.includes('127.0.0.1') || targetVal.includes('localhost') || targetVal.includes('local_mock')) ? '沙盒' : '现场';
      const loginStr = (loginEl && loginEl.value === 'A') ? '代登' : '手动';
      const isHeadless = !!((chkHeadlessEl && chkHeadlessEl.checked) || (chkHeadlessModalEl && chkHeadlessModalEl.checked));
      const headlessStr = isHeadless ? ' · 无窗口' : ' · 窗口';
      badge.innerText = `${targetStr} · ${loginStr}${headlessStr}`;
    }

    const btnOpenRunConfig = document.getElementById('btnOpenRunConfig');
    const runSettingsModal = document.getElementById('runSettingsModal');
    if (btnOpenRunConfig && runSettingsModal) {
      btnOpenRunConfig.addEventListener('click', () => {
        runSettingsModal.style.display = 'flex';
      });
      runSettingsModal.addEventListener('click', (e) => {
        if (e.target === runSettingsModal) {
          runSettingsModal.style.display = 'none';
        }
      });
    }

    // Login Mode Toggle
    const loginModeEl = document.getElementById('loginModeSelect');
    if (loginModeEl) {
      loginModeEl.addEventListener('change', (e) => {
        const autoFields = document.getElementById('autoLoginFields');
        if (autoFields) {
          autoFields.style.display = e.target.value === 'A' ? 'block' : 'none';
        }
        updateConfigSummaryBadge();
      });
    }

    const cfgFrontendEl = document.getElementById('cfgFrontendUrl');
    if (cfgFrontendEl) {
      cfgFrontendEl.addEventListener('change', updateConfigSummaryBadge);
      cfgFrontendEl.addEventListener('input', updateConfigSummaryBadge);
    }
    const envPresetEl = document.getElementById('envPresetSelect');
    if (envPresetEl) {
      envPresetEl.addEventListener('change', updateConfigSummaryBadge);
    }

    // Window Mode Switch (Bi-directional sync between Table Toolbar & Run Settings Modal)
    const chkHeadlessEl = document.getElementById('chkHeadless');
    const chkHeadlessModalEl = document.getElementById('chkHeadlessModal');

    function updateHeadlessSwitchUI(overrideVal) {
      let isHeadless = false;
      if (typeof overrideVal === 'boolean') {
        isHeadless = overrideVal;
      } else {
        isHeadless = !!((chkHeadlessEl && chkHeadlessEl.checked) || (chkHeadlessModalEl && chkHeadlessModalEl.checked));
      }

      // Synchronize both input checkbox states
      if (chkHeadlessEl && chkHeadlessEl.checked !== isHeadless) {
        chkHeadlessEl.checked = isHeadless;
      }
      if (chkHeadlessModalEl && chkHeadlessModalEl.checked !== isHeadless) {
        chkHeadlessModalEl.checked = isHeadless;
      }

      // 1. Update Table Toolbar Switch UI
      const modeText = document.getElementById('headlessSwitchModeText');
      const tipText = document.getElementById('headlessSwitchTipText');
      const lblSwitch = document.getElementById('lblHeadlessSwitch');
      if (modeText && tipText) {
        if (isHeadless) {
          modeText.innerHTML = `${Icons.zap} 无窗口模式`;
          tipText.innerText = '(不打开浏览器)';
          if (lblSwitch) {
            lblSwitch.title = '当前为【无窗口模式】：页面实测将在后台隐形执行，不打开桌面浏览器窗口。点击切换为【窗口模式】';
            lblSwitch.style.borderColor = 'var(--g-primary)';
            lblSwitch.style.background = 'var(--g-blue-surface, #e8f0fe)';
          }
        } else {
          modeText.innerHTML = `${Icons.monitor} 窗口模式`;
          tipText.innerText = '(显示浏览器)';
          if (lblSwitch) {
            lblSwitch.title = '当前为【窗口模式】：页面实测将在桌面打开实体 Chrome 窗口供实时观看。点击切换为【无窗口模式】';
            lblSwitch.style.borderColor = 'var(--g-border)';
            lblSwitch.style.background = 'var(--g-surface-variant)';
          }
        }
      }

      // 2. Update Run Settings Modal Switch UI
      const modalModeText = document.getElementById('headlessModalModeText');
      const modalTipText = document.getElementById('headlessModalTipText');
      const lblModalSwitch = document.getElementById('lblHeadlessModalSwitch');
      if (modalModeText && modalTipText) {
        if (isHeadless) {
          modalModeText.innerHTML = `${Icons.zap} 无窗口模式`;
          modalTipText.innerText = '(不打开浏览器)';
          if (lblModalSwitch) {
            lblModalSwitch.title = '当前为【无窗口模式】：页面实测将在后台隐形执行，不打开桌面浏览器窗口。点击切换为【窗口模式】';
            lblModalSwitch.style.borderColor = 'var(--g-primary)';
            lblModalSwitch.style.background = 'var(--g-blue-surface, #e8f0fe)';
          }
        } else {
          modalModeText.innerHTML = `${Icons.monitor} 窗口模式`;
          modalTipText.innerText = '(显示浏览器)';
          if (lblModalSwitch) {
            lblModalSwitch.title = '当前为【窗口模式】：页面实测将在桌面打开实体 Chrome 窗口供实时观看。点击切换为【无窗口模式】';
            lblModalSwitch.style.borderColor = 'var(--g-border)';
            lblModalSwitch.style.background = 'var(--g-surface-variant)';
          }
        }
      }
    }

    function handleHeadlessToggle(newChecked) {
      updateHeadlessSwitchUI(newChecked);
      updateConfigSummaryBadge();
      if (newChecked) {
        showToast('已切换为【无窗口模式】：页面实测将在后台隐形执行，不打开桌面浏览器窗口', 'info', '无窗口模式', 2500);
      } else {
        showToast('已切换为【窗口模式】：页面实测将在桌面打开实体 Chrome 窗口供实时观看', 'info', '窗口模式', 2500);
      }
    }

    if (chkHeadlessEl) {
      chkHeadlessEl.addEventListener('change', (e) => {
        handleHeadlessToggle(e.target.checked);
      });
    }

    if (chkHeadlessModalEl) {
      chkHeadlessModalEl.addEventListener('change', (e) => {
        handleHeadlessToggle(e.target.checked);
      });
    }

    updateConfigSummaryBadge();
    updateHeadlessSwitchUI();

    // Run Tests Action
    async function startExecution(selectedIds, runMode = 'ALL') {
      const btnRunSel = document.getElementById('btnRunSelected');
      const btnRunAll = document.getElementById('btnRunAll');
      const btnStop = document.getElementById('btnStop');

      try {
        resetKpis();
        if (btnRunSel) btnRunSel.disabled = true;
        if (btnRunAll) btnRunAll.disabled = true;
        if (btnStop) {
          btnStop.style.display = 'inline-flex';
          btnStop.disabled = false;
        }

        const count = (selectedIds && selectedIds.length) ? selectedIds.length : (allTestCases.length || '全量');
        showToast(`已开始执行测试任务（${count} 项用例）...`, 'run', '测试已启动', 3500);

        const headless = !!(document.getElementById('chkHeadless')?.checked || document.getElementById('chkHeadlessModal')?.checked);
        const frontendUrl = document.getElementById('cfgFrontendUrl')?.value || '';
        const loginMode = document.getElementById('loginModeSelect')?.value || 'B';
        const username = document.getElementById('autoUsername')?.value || 'admin';
        const password = document.getElementById('autoPassword')?.value || '123456';

        const payload = {
          selected_ids: (selectedIds && selectedIds.length) ? selectedIds : null,
          mode: runMode,
          headless: headless,
          login_mode: loginMode,
          username: username,
          password: password
        };
        if (frontendUrl) {
          payload.url = (frontendUrl.endsWith('/') ? frontendUrl.slice(0, -1) : frontendUrl) + '/#/inpatient/doctor/workstation';
        }

        const resp = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          showToast(`启动失败: ${errData.error || resp.statusText}`, 'danger', '无法启动测试', 4000);
          if (btnRunSel) btnRunSel.disabled = false;
          if (btnRunAll) btnRunAll.disabled = false;
          if (btnStop) btnStop.style.display = 'none';
        }
      } catch (err) {
        showToast(`启动测试异常: ${err.message || err}`, 'danger', '启动失败', 4000);
        if (btnRunSel) btnRunSel.disabled = false;
        if (btnRunAll) btnRunAll.disabled = false;
        if (btnStop) btnStop.style.display = 'none';
      }
    }

    document.getElementById('btnRunSelected').addEventListener('click', () => {
      let ids = Array.from(selectedCaseIds);
      if (ids.length === 0) {
        ids = Array.from(document.querySelectorAll('.case-chk:checked')).map(c => c.dataset.id).filter(Boolean);
      }
      if (ids.length === 0) {
        showToast('请先勾选需要运行的测试用例！', 'warning', '未勾选用例', 3000);
        return;
      }
      startExecution(ids, 'ALL');
    });

    document.getElementById('btnRunAll').addEventListener('click', () => {
      const modal = document.getElementById('runSettingsModal');
      if (modal) modal.style.display = 'none';
      showToast('正在启动全量测试用例（50+ 项）...', 'run', '全量执行', 3500);
      startExecution(null, 'ALL');
    });

    document.getElementById('btnRunSiteScan').addEventListener('click', () => {
      // Filter for healthcheck suite
      const healthIds = allTestCases.filter(t => t.category.includes('健康') || t.category.includes('巡检')).map(t => t.id);
      document.querySelector('.tab-item[data-tab="tab-cases"]').click();
      showToast(`已启动全院业务模块体检（共 ${healthIds.length} 项巡检）...`, 'run', '全院体检巡检', 3500);
      startExecution(healthIds, 'ALL');
    });

    // Stop Execution with instant visual feedback
    document.getElementById('btnStop').addEventListener('click', async () => {
      const btn = document.getElementById('btnStop');
      btn.disabled = true;
      btn.innerText = '正在终止...';
      showToast('已向后台发送停止指令，正在安全关闭并释放资源...', 'warning', '测试终止中', 3500);
      
      const term = document.getElementById('termLogsContainer');
      const line = document.createElement('div');
      line.className = 't-line WARN';
      line.innerText = '[用户操作] 已触发强制终止指令，正在关闭浏览器并释放资源...';
      term.appendChild(line);
      term.scrollTop = term.scrollHeight;

      const banner = document.getElementById('loginAlertBanner');
      if (banner) banner.style.display = 'none';

      try {
        await fetch('/api/stop', { method: 'POST' });
      } catch (e) {
        console.error("停止请求异常:", e);
      } finally {
        setTimeout(() => {
          btn.style.display = 'none';
          btn.disabled = false;
          btn.innerHTML = `${Icons.stop} 停止执行`;
          document.getElementById('btnRunSelected').disabled = false;
          document.getElementById('btnRunAll').disabled = false;
        }, 500);
      }
    });

    // Open Browser Window Directly
    document.getElementById('btnOpenBrowser').addEventListener('click', async () => {
      showToast('正在启动并弹出独立的 Chrome 窗口...', 'info', '启动浏览器', 3000);
      const term = document.getElementById('termLogsContainer');
      const line = document.createElement('div');
      line.className = 't-line INFO';
      line.innerText = '[指令] 正在桌面启动并弹出独立的 Chrome 窗口...';
      term.appendChild(line);
      term.scrollTop = term.scrollHeight;
      try {
        await fetch('/api/open_browser', { method: 'POST' });
      } catch (e) {
        console.error(e);
      }
    });

