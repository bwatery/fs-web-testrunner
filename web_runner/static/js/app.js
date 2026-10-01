    // Theme Toggle
    const themeBtn = document.getElementById('btnToggleTheme');
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
    });

    // -------------------------------------------------------------
    // Level 1 (Domain) & Level 2 (Tab) Navigation Management (方案2)
    // -------------------------------------------------------------
    const DOMAIN_MAP = {
      'domain-tests': {
        name: '测试中心',
        defaultTab: 'tab-cases',
        tabs: ['tab-cases', 'tab-workstations']
      },
      'domain-rules': {
        name: '业务规则',
        defaultTab: 'tab-rules',
        tabs: ['tab-rules', 'tab-health']
      },
      'domain-auth': {
        name: '鉴权验证',
        defaultTab: 'tab-validator',
        tabs: ['tab-validator']
      },
      'domain-devtools': {
        name: '调试工具',
        defaultTab: 'tab-xml',
        tabs: ['tab-xml', 'tab-repl', 'tab-screen']
      },
      'domain-ai': {
        name: 'AI 智能体',
        defaultTab: 'tab-ai-hub',
        tabs: ['tab-ai-hub', 'tab-ai-playground', 'tab-ai-deploy']
      }
    };

    let currentDomain = 'domain-tests';
    const domainLastActiveTab = {
      'domain-tests': 'tab-cases',
      'domain-rules': 'tab-rules',
      'domain-auth': 'tab-validator',
      'domain-devtools': 'tab-xml',
      'domain-ai': 'tab-ai-hub'
    };

    // Drawer Collapse/Expand Management
    window.toggleDrawer = function(forceState) {
      const drawer = document.getElementById('caseDrawer');
      if (!drawer) return;
      const isCurrentlyCollapsed = drawer.classList.contains('collapsed');
      const shouldCollapse = typeof forceState === 'boolean' ? forceState : !isCurrentlyCollapsed;
      drawer.classList.toggle('collapsed', shouldCollapse);

      const btnInDrawer = document.getElementById('btnToggleDrawer');
      if (btnInDrawer) {
        btnInDrawer.title = shouldCollapse ? '展开分类侧栏' : '收起分类侧栏';
        btnInDrawer.innerHTML = shouldCollapse
          ? '<svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>'
          : '<svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>';
      }

      const btnInTable = document.getElementById('btnToggleDrawerFromTable');
      if (btnInTable) {
        btnInTable.title = shouldCollapse ? '展开左侧业务分类侧栏' : '收起左侧业务分类侧栏';
        btnInTable.style.color = shouldCollapse ? 'var(--g-text-secondary)' : 'var(--g-blue)';
        btnInTable.style.borderColor = shouldCollapse ? 'var(--g-border)' : 'var(--g-blue)';
        btnInTable.style.background = shouldCollapse ? 'transparent' : 'var(--g-blue-surface)';
      }
    };

    // Global Tab Navigation
    window.switchTab = function(tabId) {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;

      // 1. Identify which domain this tab belongs to
      let targetDomain = null;
      for (const [dom, conf] of Object.entries(DOMAIN_MAP)) {
        if (conf.tabs.includes(tabId)) {
          targetDomain = dom;
          break;
        }
      }

      if (targetDomain) {
        domainLastActiveTab[targetDomain] = tabId;
        if (targetDomain !== currentDomain) {
          currentDomain = targetDomain;
          // Sync Activity Rail selection
          document.querySelectorAll('.rail-top .rail-item').forEach(item => {
            if (item.dataset.domain === currentDomain) {
              item.classList.add('active');
            } else {
              item.classList.remove('active');
            }
          });
          // Sync Tab visibility
          document.querySelectorAll('.tab-bar .tab-item').forEach(tab => {
            if (tab.dataset.domain === currentDomain) {
              tab.style.display = 'inline-flex';
            } else {
              tab.style.display = 'none';
            }
          });
        }
      }

      // 2. Tab header active classes
      document.querySelectorAll('.tab-item').forEach(t => {
        if (t.dataset.tab === tabId) {
          t.classList.add('active');
        } else {
          t.classList.remove('active');
        }
      });

      // 3. Content area active classes
      document.querySelectorAll('.content-area').forEach(c => {
        if (c.id === tabId) {
          c.classList.add('active');
        } else {
          c.classList.remove('active');
        }
      });

      document.querySelectorAll('.workspace-nav-item').forEach(w => {
        if (w.dataset.tab === tabId) {
          w.classList.add('active');
        } else {
          w.classList.remove('active');
        }
      });

      // 4. Drawer visibility: only expand on tab-cases, collapse on other tabs to free up full width
      const drawer = document.getElementById('caseDrawer');
      if (drawer) {
        if (tabId === 'tab-cases') {
          window.toggleDrawer(false); // expand
        } else {
          window.toggleDrawer(true);  // collapse
        }
      }

      // 5. Special tab lifecycle hooks
      if (tabId === 'tab-workstations' && typeof window.loadWorkstationsData === 'function') {
        window.loadWorkstationsData();
      }
    };

    // Global Domain Navigation
    window.switchDomain = function(domainId, targetTabId) {
      if (!DOMAIN_MAP[domainId]) domainId = 'domain-tests';
      currentDomain = domainId;

      // 1. Update Activity Rail selection
      document.querySelectorAll('.rail-top .rail-item').forEach(item => {
        if (item.dataset.domain === domainId) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      });

      // 2. Filter Tab Bar items: only show tabs that belong to this domain
      document.querySelectorAll('.tab-bar .tab-item').forEach(tab => {
        if (tab.dataset.domain === domainId) {
          tab.style.display = 'inline-flex';
        } else {
          tab.style.display = 'none';
        }
      });

      // 3. Determine which tab to activate
      let tabToActivate = targetTabId;
      if (!tabToActivate || !DOMAIN_MAP[domainId].tabs.includes(tabToActivate)) {
        tabToActivate = domainLastActiveTab[domainId] || DOMAIN_MAP[domainId].defaultTab;
      }

      // 4. Activate target tab
      window.switchTab(tabToActivate);
    };

    // Bind Activity Rail Domain Items
    document.querySelectorAll('.rail-top .rail-item').forEach(item => {
      item.addEventListener('click', () => {
        const domain = item.dataset.domain;
        if (!domain) return;
        if (domain === currentDomain && domain === 'domain-tests') {
          // Clicking active test domain toggles the drawer (VS Code pattern)
          window.toggleDrawer();
        } else {
          window.switchDomain(domain);
        }
      });
    });

    // Bind Rail Bottom Actions
    const railBtnSettings = document.getElementById('railBtnSettings');
    if (railBtnSettings) {
      railBtnSettings.addEventListener('click', () => {
        const modal = document.getElementById('runSettingsModal');
        if (modal) modal.style.display = 'flex';
      });
    }

    const railBtnLogs = document.getElementById('railBtnLogs');
    if (railBtnLogs) {
      railBtnLogs.addEventListener('click', () => {
        const modal = document.getElementById('diskLogsModal');
        if (modal) {
          modal.style.display = 'flex';
          if (typeof window.reloadDiskLogsView === 'function') {
            window.reloadDiskLogsView();
          }
        }
      });
    }

    // Bind Drawer Toggle Buttons
    const btnToggleDrawer = document.getElementById('btnToggleDrawer');
    if (btnToggleDrawer) {
      btnToggleDrawer.addEventListener('click', () => window.toggleDrawer());
    }

    const btnToggleDrawerFromTable = document.getElementById('btnToggleDrawerFromTable');
    if (btnToggleDrawerFromTable) {
      btnToggleDrawerFromTable.addEventListener('click', () => window.toggleDrawer());
    }

    // Bind Tab click events
    document.querySelectorAll('.tab-item').forEach(tab => {
      tab.addEventListener('click', () => {
        switchTab(tab.dataset.tab);
      });
    });

    // Support smooth horizontal mouse wheel scrolling across tabs
    const tabBarEl = document.querySelector('.tab-bar');
    if (tabBarEl) {
      tabBarEl.addEventListener('wheel', (e) => {
        if (e.deltaY !== 0 && tabBarEl.scrollWidth > tabBarEl.clientWidth) {
          e.preventDefault();
          tabBarEl.scrollLeft += e.deltaY;
        }
      }, { passive: false });
    }

    const btnNavValidatorEl = document.getElementById('btnNavValidator');
    if (btnNavValidatorEl) {
      btnNavValidatorEl.addEventListener('click', () => switchTab('tab-validator'));
    }



    // Synchronize test execution button state with server
    async function syncRunnerStatus() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        const btnRunSel = document.getElementById('btnRunSelected');
        const btnRunAll = document.getElementById('btnRunAll');
        const stopBtn = document.getElementById('btnStop');
        if (data.is_running) {
          if (btnRunSel) btnRunSel.disabled = true;
          if (btnRunAll) btnRunAll.disabled = true;
          if (stopBtn) stopBtn.style.display = 'inline-flex';
        } else {
          if (btnRunSel) btnRunSel.disabled = false;
          if (btnRunAll) btnRunAll.disabled = false;
          if (stopBtn) stopBtn.style.display = 'none';
        }
      } catch (err) {
        console.warn("Status sync failed:", err);
      }
    }

    // Initialize
    async function initPlatform() {
      await loadEnvironmentStatus();
      if (typeof window.loadFullEnvConfig === 'function') await window.loadFullEnvConfig();
      if (typeof window.loadWorkstationsData === 'function') await window.loadWorkstationsData();
      await loadBusinessRules();
      await loadTests();
      await loadModules();
      await syncRunnerStatus();
      initWebSocket();
      checkValidatorStatus();
      startValidatorPolling();
      searchOrderItems("丹参");
      await loadRolePresets();
      await loadRolesDropdown();
    }

    initPlatform();
