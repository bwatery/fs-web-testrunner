    // Load HIS Modules Matrix
    async function loadModules() {
      try {
        const resp = await fetch('/api/modules');
        const data = await resp.json();
        const container = document.getElementById('moduleRadarContainer');
        container.innerHTML = '';

        data.modules.forEach(g => {
          const groupDiv = document.createElement('div');
          groupDiv.innerHTML = `<h3 style="font-size:14px; font-weight:600; color:var(--g-blue); margin-bottom:12px;">${g.group}</h3>`;
          const grid = document.createElement('div');
          grid.className = 'module-grid';

          g.items.forEach(m => {
            const card = document.createElement('div');
            card.className = 'module-card';
            card.innerHTML = `
              <div class="module-header">
                <span class="module-name">${m.name}</span>
                <span class="module-badge">Vue 3 路由</span>
              </div>
              <div class="module-desc">${m.desc}</div>
              <div class="module-path">#${m.path}</div>
            `;
            card.addEventListener('click', () => {
              // Open in REPL or quick test
              document.querySelector('.tab-item[data-tab="tab-repl"]').click();
              window.setRepl(`window.location.hash = '${m.path}'`);
            });
            grid.appendChild(card);
          });
          groupDiv.appendChild(grid);
          container.appendChild(groupDiv);
        });
      } catch (e) {
        console.error("加载HIS模块失败:", e);
      }
    }

    // WebSocket Connection


    // XML Inspector Actions
    document.getElementById('btnRefreshXml').addEventListener('click', async () => {
      const resp = await fetch('/api/xml');
      const data = await resp.json();
      if (data.status === 'ok') {
        document.getElementById('xmlContentBlock').innerText = data.xml || '<!-- 当前画布无XML内容 -->';
      } else {
        document.getElementById('xmlContentBlock').innerText = '获取失败: ' + data.message;
      }
    });

    document.getElementById('btnCopyXml').addEventListener('click', () => {
      const txt = document.getElementById('xmlContentBlock').innerText;
      navigator.clipboard.writeText(txt).then(() => showToast('病历 XML 数据已成功复制到剪贴板！', 'copy', '复制成功', 2500));
    });

    // REPL Actions
    window.setRepl = function(code) {
      document.getElementById('replEditor').value = code;
    };

    document.getElementById('btnExecRepl').addEventListener('click', async () => {
      const code = document.getElementById('replEditor').value;
      if (!code.trim()) return;
      const out = document.getElementById('replResultBlock');
      out.innerText = '正在执行...';
      try {
        const resp = await fetch('/api/eval', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expression: code })
        });
        const res = await resp.json();
        out.innerText = JSON.stringify(res, null, 2);
      } catch (e) {
        out.innerText = '执行错误: ' + e;
      }
    });

    // Live Snapshot Refresh
    document.getElementById('btnRefreshScreen').addEventListener('click', async () => {
      const resp = await fetch('/api/screenshot');
      const data = await resp.json();
      if (data.status === 'ok') {
        const img = document.getElementById('liveImgView');
        img.src = data.data;
        img.style.display = 'block';
        document.getElementById('noImgTip').style.display = 'none';
      }
    });



    // =========================================================================
    // Environment Mode Switcher (Live Intranet vs Offline Mock Sandbox)
    // =========================================================================
    async function loadEnvironmentStatus() {
      try {
        const resp = await fetch('/api/environment');
        const data = await resp.json();
        const sel = document.getElementById('envModeSelect');
        if (sel && data.mode) {
          sel.value = data.mode;
        }
        const chip = document.getElementById('rulesEnvChip');
        if (chip) {
          if (data.is_mock) {
            chip.style.background = 'var(--g-green-surface)';
            chip.style.color = 'var(--g-green)';
            chip.innerText = '离线沙盒模式 (免库/零内网依赖)';
          } else {
            chip.style.background = 'var(--g-blue-surface)';
            chip.style.color = 'var(--g-blue)';
            chip.innerText = '内网直连模式 (现场微服务+Oracle)';
          }
        }
      } catch (err) {
        console.warn("Failed to load environment status:", err);
      }
    }

    const envModeSelectEl = document.getElementById('envModeSelect');
    if (envModeSelectEl) {
      envModeSelectEl.addEventListener('change', async (e) => {
        const newMode = e.target.value;
        try {
          const resp = await fetch('/api/environment/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode })
          });
          const res = await resp.json();
          await loadEnvironmentStatus();
          showToast(`已切换运行模式: ${res.mode_name}`, 'env', '环境模式变更', 3500);
        } catch (err) {
          showToast(`模式切换失败: ${err}`, 'danger', '切换失败', 4000);
        }
      });
    }



// =========================================================================
// Local Persistent Disk Logging System API
// =========================================================================
async function fetchDiskLogs(logType = 'app', limit = 100) {
  try {
    const resp = await fetch(`/api/logs?log_type=${encodeURIComponent(logType)}&limit=${limit}`);
    return await resp.json();
  } catch (e) {
    console.error('Failed to fetch disk logs:', e);
    return { lines: [] };
  }
}

async function fetchDiskLogFiles() {
  try {
    const resp = await fetch('/api/logs/files');
    return await resp.json();
  } catch (e) {
    console.error('Failed to fetch disk log files:', e);
    return { files: [] };
  }
}

async function clearDiskLogs() {
  try {
    const resp = await fetch('/api/logs', { method: 'DELETE' });
    return await resp.json();
  } catch (e) {
    console.error('Failed to clear disk logs:', e);
    return { status: 'error', message: String(e) };
  }
}

// =========================================================================
// Target Environment Configuration & Adaptive Strategy Manager
// =========================================================================
let cachedEnvConfig = null;

async function loadFullEnvConfig() {
  try {
    const res = await fetch('/api/environment/config');
    const data = await res.json();
    if (data.status === 'ok') {
      cachedEnvConfig = data.config;
      populateEnvConfigForm(cachedEnvConfig);
    }
  } catch (e) {
    console.error('Failed to load full env config:', e);
  }
}

function populateEnvConfigForm(conf) {
  if (!conf) return;

  const presetSel = document.getElementById('envPresetSelect');
  if (presetSel && conf.active_preset) {
    presetSel.value = conf.active_preset;
  }

  const feUrl = document.getElementById('cfgFrontendUrl');
  if (feUrl && conf.frontend_base_url) feUrl.value = conf.frontend_base_url;

  const gwUrl = document.getElementById('cfgApiGatewayUrl');
  if (gwUrl && conf.api_gateway_url) gwUrl.value = conf.api_gateway_url;

  const emrUrl = document.getElementById('cfgEmrDesignerUrl');
  if (emrUrl && conf.emr_designer_url) emrUrl.value = conf.emr_designer_url;

  const ora = conf.oracle || {};
  const hostInput = document.getElementById('cfgOracleHost');
  if (hostInput && ora.host) hostInput.value = ora.host;
  const portInput = document.getElementById('cfgOraclePort');
  if (portInput && ora.port) portInput.value = ora.port;
  const svcInput = document.getElementById('cfgOracleService');
  if (svcInput && ora.service_name) svcInput.value = ora.service_name;

  // Adaptive Strategy Radio
  const strategy = conf.offline_adaptive_strategy || 'ADAPTIVE_MOCK';
  const radio = document.querySelector(`input[name="adaptiveStrategyRadio"][value="${strategy}"]`);
  if (radio) {
    radio.checked = true;
    updateAdaptiveStrategyCardStyles(strategy);
  }
}

function updateAdaptiveStrategyCardStyles(strategy) {
  const lblA = document.getElementById('lblOptA');
  const lblB = document.getElementById('lblOptB');
  const lblStrict = document.getElementById('lblOptStrict');
  if (lblA) lblA.style.background = (strategy === 'ADAPTIVE_MOCK') ? 'var(--g-surface-variant)' : 'var(--g-surface)';
  if (lblB) lblB.style.background = (strategy === 'SKIP_INVASIVE') ? 'var(--g-surface-variant)' : 'var(--g-surface)';
  if (lblStrict) lblStrict.style.background = (strategy === 'STRICT') ? 'var(--g-surface-variant)' : 'var(--g-surface)';
}

async function saveTargetEnvConfig() {
  const feUrl = document.getElementById('cfgFrontendUrl')?.value.trim();
  const gwUrl = document.getElementById('cfgApiGatewayUrl')?.value.trim();
  const emrUrl = document.getElementById('cfgEmrDesignerUrl')?.value.trim();
  const oraHost = document.getElementById('cfgOracleHost')?.value.trim();
  const oraPort = parseInt(document.getElementById('cfgOraclePort')?.value.trim() || '1521');
  const oraService = document.getElementById('cfgOracleService')?.value.trim();
  const preset = document.getElementById('envPresetSelect')?.value;

  const strategyEl = document.querySelector('input[name="adaptiveStrategyRadio"]:checked');
  const strategy = strategyEl ? strategyEl.value : 'ADAPTIVE_MOCK';

  const payload = {
    active_preset: preset,
    frontend_base_url: feUrl,
    api_gateway_url: gwUrl,
    emr_designer_url: emrUrl,
    offline_adaptive_strategy: strategy,
    oracle: {
      host: oraHost,
      port: oraPort,
      service_name: oraService
    }
  };

  try {
    const res = await fetch('/api/environment/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showToast('目标环境配置已成功保存并即时生效！', 'success', '环境配置已更新');
      await loadEnvironmentStatus();
      if (typeof window.loadWorkstationsData === 'function') {
        await window.loadWorkstationsData();
      }
    } else {
      showToast('保存失败: ' + (data.message || '未知错误'), 'danger');
    }
  } catch (e) {
    showToast('网络错误: ' + e.message, 'danger');
  }
}

async function testTargetConnectivity() {
  const box = document.getElementById('connectivityStatusBox');
  if (box) {
    box.style.display = 'block';
    box.innerHTML = '正在探测前端与微服务连通性...';
    box.style.color = 'var(--g-blue)';
  }

  const gwUrl = document.getElementById('cfgApiGatewayUrl')?.value.trim();
  try {
    const res = await fetch('/api/environment/test_connectivity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_type: 'api_gateway', target_url: gwUrl })
    });
    const data = await res.json();
    if (box && data.status === 'ok') {
      const r = data.result;
      if (r.reachable) {
        box.innerHTML = `<span style="color:var(--g-green); font-weight:600;">✓ 连通正常 (${r.status})</span>: 目标 ${r.target}, 延迟 ${r.latency_ms} ms (HTTP ${r.http_status || 'Port Open'})`;
        showToast(`目标服务连通正常: 延迟 ${r.latency_ms}ms`, 'success');
      } else {
        box.innerHTML = `<span style="color:var(--g-yellow); font-weight:600;">⚠️ 目标不可达 (${r.status})</span>: 目标 ${r.target} 无法连接 (${r.latency_ms} ms)。当前已由【离线高仿沙盒】自动兜底接管！`;
        showToast(`目标不可达: 当前将启用离线高仿沙盒模式`, 'warning');
      }
    }
  } catch (e) {
    if (box) {
      box.innerHTML = `<span style="color:var(--g-red);">探测失败: ${e.message}</span>`;
    }
  }
}

// Event Listeners for Env Modal
document.addEventListener('DOMContentLoaded', () => {
  const btnSave = document.getElementById('btnSaveEnvConfig');
  if (btnSave) btnSave.addEventListener('click', saveTargetEnvConfig);

  const btnTest = document.getElementById('btnTestConnectivity');
  if (btnTest) btnTest.addEventListener('click', testTargetConnectivity);

  const presetSel = document.getElementById('envPresetSelect');
  if (presetSel) {
    presetSel.addEventListener('change', (e) => {
      const p = e.target.value;
      if (p === 'hospital_live') {
        document.getElementById('cfgFrontendUrl').value = 'http://192.168.1.198:8088';
        document.getElementById('cfgApiGatewayUrl').value = 'http://192.168.1.198:8081';
        document.getElementById('cfgEmrDesignerUrl').value = 'http://192.168.1.198:8088/#/emr/templatesrecords/emrDesigner';
        document.getElementById('cfgOracleHost').value = '192.168.1.199';
      } else if (p === 'local_mock') {
        document.getElementById('cfgFrontendUrl').value = 'http://127.0.0.1:8989';
        document.getElementById('cfgApiGatewayUrl').value = 'http://127.0.0.1:8989/mock-api';
        document.getElementById('cfgEmrDesignerUrl').value = 'http://127.0.0.1:8989/static/index.html';
        document.getElementById('cfgOracleHost').value = '127.0.0.1';
      }
    });
  }

  document.querySelectorAll('input[name="adaptiveStrategyRadio"]').forEach(radio => {
    radio.addEventListener('change', async (e) => {
      const val = e.target.value;
      updateAdaptiveStrategyCardStyles(val);
      try {
        await fetch('/api/environment/adaptive_strategy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ strategy: val })
        });
        showToast(`已切换离线沙盒自适应策略: ${val === 'ADAPTIVE_MOCK' ? '选项A (全绿灯通过)' : (val === 'SKIP_INVASIVE' ? '选项B (自动跳过)' : '严格模式')}`, 'success');
      } catch (err) {
        console.error('Failed to switch strategy:', err);
      }
    });
  });
});

window.loadFullEnvConfig = loadFullEnvConfig;
window.saveTargetEnvConfig = saveTargetEnvConfig;

