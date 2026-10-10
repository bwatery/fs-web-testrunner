    function updateSelectionUI() {
      // 1. Update table checkboxes
      document.querySelectorAll('.case-chk').forEach(c => {
        c.checked = selectedCaseIds.has(c.dataset.id);
      });

      // 2. Update sidebar sub-item checkboxes
      document.querySelectorAll('.sub-case-chk').forEach(c => {
        c.checked = selectedCaseIds.has(c.dataset.id);
      });

      // 3. Update module/category checkboxes (checked / unchecked / indeterminate)
      document.querySelectorAll('.cat-select-chk').forEach(catChk => {
        const cat = catChk.dataset.cat;
        const catCases = allTestCases.filter(t => t.category === cat);
        const checkedCount = catCases.filter(t => selectedCaseIds.has(t.id)).length;
        if (checkedCount === 0) {
          catChk.checked = false;
          catChk.indeterminate = false;
        } else if (checkedCount === catCases.length) {
          catChk.checked = true;
          catChk.indeterminate = false;
        } else {
          catChk.checked = false;
          catChk.indeterminate = true;
        }
      });

      // 4. Update global drawer select-all checkbox (reflects ALL 38 tests in system)
      const allCount = allTestCases.length;
      const selCount = selectedCaseIds.size;
      const isDrawerAll = allCount > 0 && selCount === allCount;
      const isDrawerInd = selCount > 0 && selCount < allCount;

      const chkDrawer = document.getElementById('chkSelectAll');
      if (chkDrawer) {
        chkDrawer.checked = isDrawerAll;
        chkDrawer.indeterminate = isDrawerInd;
      }

      // 5. Update TABLE Select-All checkbox (STRICTLY reflects currentDisplayedTests!)
      const dispCount = currentDisplayedTests.length;
      const dispSelCount = currentDisplayedTests.filter(t => selectedCaseIds.has(t.id)).length;
      const isTableAll = dispCount > 0 && dispSelCount === dispCount;
      const isTableInd = dispSelCount > 0 && dispSelCount < dispCount;

      const chkTable = document.getElementById('chkTableSelectAll');
      if (chkTable) {
        chkTable.checked = isTableAll;
        chkTable.indeterminate = isTableInd;
        if (isTableAll) {
          chkTable.title = `已全选当前展示的全部 ${dispCount} 项用例，点击取消全选`;
        } else if (isTableInd) {
          chkTable.title = `当前展示列表中已勾选 ${dispSelCount}/${dispCount} 项，点击全选当前展示列表`;
        } else {
          chkTable.title = `点击全选当前展示的 ${dispCount} 项用例`;
        }
      }

      // 6. Update Selection Status Badge & Menu Counts
      const selCountBadge = document.getElementById('selCountBadge');
      if (selCountBadge) selCountBadge.innerText = `${selCount}`;
      const totalCountBadge = document.getElementById('totalCountBadge');
      if (totalCountBadge) totalCountBadge.innerText = `${allCount}`;
      const dispSelCountBadge = document.getElementById('dispSelCountBadge');
      if (dispSelCountBadge) dispSelCountBadge.innerText = `${dispSelCount}/${dispCount}`;

      const menuCntVisible = document.getElementById('menuCntVisible');
      if (menuCntVisible) menuCntVisible.innerText = `${dispCount}`;
      const menuCntAll = document.getElementById('menuCntAll');
      if (menuCntAll) menuCntAll.innerText = `${allCount}`;

      // 7. Update Run Selected Button badge
      const btnRunSel = document.getElementById('btnRunSelected');
      if (btnRunSel) {
        btnRunSel.innerHTML = `${Icons.play} 运行选中用例 (${selCount})`;
        btnRunSel.title = `运行当前勾选的 ${selCount} 项用例（当前展示中 ${dispSelCount} 项，其他未展示项 ${selCount - dispSelCount} 项）`;
      }

      // 8. Update Smart Selection Banner
      updateSmartBanner(dispCount, dispSelCount, allCount, selCount);
    }

    function updateSmartBanner(dispCount, dispSelCount, allCount, selCount) {
      const banner = document.getElementById('smartSelectionBanner');
      if (!banner) return;
      const bannerText = document.getElementById('smartBannerText');
      const bannerActions = document.getElementById('smartBannerActions');
      const bannerIcon = document.getElementById('smartBannerIcon');

      // If viewing all items (dispCount === allCount):
      if (dispCount >= allCount) {
        if (selCount > 0 && selCount < allCount) {
          banner.style.display = 'flex';
          bannerIcon.innerHTML = Icons.info;
          bannerText.innerHTML = `已选择系统 <b>${selCount}</b> / <b>${allCount}</b> 项用例。`;
          bannerActions.innerHTML = `
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('select_all_system')">${Icons.globe} 全选全部 (${allCount})</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('invert_visible')">${Icons.refresh} 反选</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('clear_all')">${Icons.trash} 全部清空</button>
          `;
        } else {
          banner.style.display = 'none';
        }
        return;
      }

      // When in a filtered or searched view (dispCount < allCount):
      const outsideCount = allCount - dispCount;
      const outsideSelCount = selCount - dispSelCount;

      if (dispSelCount === dispCount && dispCount > 0) {
        banner.style.display = 'flex';
        if (selCount === allCount) {
          bannerIcon.innerHTML = Icons.globe;
          bannerText.innerHTML = `已勾选系统全部 <b>${allCount}</b> 项用例（包含此处未展示的 ${outsideCount} 项）。`;
          bannerActions.innerHTML = `
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('only_visible')">${Icons.target} 仅保留当前展示 (${dispCount})</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('deselect_visible')">取消勾选当前项</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('clear_all')">${Icons.trash} 清空全部</button>
          `;
        } else {
          bannerIcon.innerHTML = Icons.bulb;
          bannerText.innerHTML = `已勾选当前展示的全部 <b>${dispCount}</b> 项用例。需要连同系统其余 ${outsideCount} 项一起勾选吗？`;
          bannerActions.innerHTML = `
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('select_all_system')">${Icons.globe} 勾选系统全部 (${allCount})</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('invert_visible')">${Icons.refresh} 反选当前</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('deselect_visible')">${Icons.xCircle} 取消当前所选</button>
          `;
        }
      } else if (dispSelCount > 0) {
        banner.style.display = 'flex';
        bannerIcon.innerHTML = Icons.info;
        if (outsideSelCount > 0) {
          bannerText.innerHTML = `当前展示已选 <b>${dispSelCount}/${dispCount}</b> 项（全系统共勾选 <b>${selCount}</b> 项，含其他模块 ${outsideSelCount} 项）。`;
        } else {
          bannerText.innerHTML = `当前展示已选 <b>${dispSelCount}/${dispCount}</b> 项用例。`;
        }
        bannerActions.innerHTML = `
          <button type="button" class="smart-banner-btn" onclick="tableBatchAction('select_visible')">${Icons.checkSquare} 全选当前展示 (${dispCount})</button>
          <button type="button" class="smart-banner-btn" onclick="tableBatchAction('invert_visible')">${Icons.refresh} 反选当前</button>
          ${outsideSelCount > 0 ? `<button type="button" class="smart-banner-btn" onclick="tableBatchAction('only_current_selected')">${Icons.target} 仅保留当前所选</button>` : ''}
          <button type="button" class="smart-banner-btn" onclick="tableBatchAction('deselect_visible')">${Icons.xCircle} 取消当前所选</button>
        `;
      } else {
        if (selCount > 0) {
          banner.style.display = 'flex';
          bannerIcon.innerHTML = Icons.alertTriangle;
          bannerText.innerHTML = `当前展示中<b>未勾选任何用例</b>（但其他分类中已勾选了 <b>${selCount}</b> 项）。`;
          bannerActions.innerHTML = `
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('select_visible')">${Icons.checkSquare} 全选当前展示 (${dispCount})</button>
            <button type="button" class="smart-banner-btn" onclick="tableBatchAction('clear_all')">${Icons.trash} 清空全部已选</button>
          `;
        } else {
          banner.style.display = 'none';
        }
      }
    }

    window.tableBatchAction = function(action) {
      const menu = document.getElementById('tableSelectMenu');
      if (menu) menu.classList.remove('show');

      if (action === 'select_visible') {
        currentDisplayedTests.forEach(t => selectedCaseIds.add(t.id));
      } else if (action === 'deselect_visible') {
        currentDisplayedTests.forEach(t => selectedCaseIds.delete(t.id));
      } else if (action === 'invert_visible') {
        currentDisplayedTests.forEach(t => {
          if (selectedCaseIds.has(t.id)) {
            selectedCaseIds.delete(t.id);
          } else {
            selectedCaseIds.add(t.id);
          }
        });
      } else if (action === 'only_visible') {
        selectedCaseIds.clear();
        currentDisplayedTests.forEach(t => selectedCaseIds.add(t.id));
      } else if (action === 'only_current_selected') {
        const keep = new Set(currentDisplayedTests.filter(t => selectedCaseIds.has(t.id)).map(t => t.id));
        selectedCaseIds = keep;
      } else if (action === 'select_all_system') {
        allTestCases.forEach(t => selectedCaseIds.add(t.id));
      } else if (action === 'clear_all') {
        selectedCaseIds.clear();
      }
      updateSelectionUI();
    };

    function toggleModuleSelection(cat, isChecked) {
      const catCases = allTestCases.filter(t => t.category === cat);
      catCases.forEach(t => {
        if (isChecked) {
          selectedCaseIds.add(t.id);
        } else {
          selectedCaseIds.delete(t.id);
        }
      });
      updateSelectionUI();
    }

    function toggleAllSelection(isChecked) {
      if (isChecked) {
        allTestCases.forEach(t => selectedCaseIds.add(t.id));
      } else {
        selectedCaseIds.clear();
      }
      updateSelectionUI();
    }

    function toggleTableSelection(isChecked) {
      if (isChecked) {
        currentDisplayedTests.forEach(t => selectedCaseIds.add(t.id));
      } else {
        currentDisplayedTests.forEach(t => selectedCaseIds.delete(t.id));
      }
      updateSelectionUI();
    }

    // Test Case Loaders
    async function loadTests() {
      try {
        const resp = await fetch('/api/tests');
        const data = await resp.json();
        allTestCases = data.tests || [];
        stats.total = allTestCases.length;
        const invasiveCnt = allTestCases.filter(t => t.mode === 'INVASIVE').length;
        const nonInvasiveCnt = allTestCases.filter(t => t.mode === 'NON_INVASIVE').length;
        document.getElementById('totalTestsCount').innerText = `${stats.total}`;
        document.getElementById('kpiTotal').innerText = `${stats.total}`;
        const railBadgeTests = document.getElementById('railBadgeTests');
        if (railBadgeTests) railBadgeTests.innerText = `${stats.total}`;
        const subModesEl = document.getElementById('kpiSubModes');
        if (subModesEl) subModesEl.innerHTML = `(${Icons.monitor} 页面实测 ${invasiveCnt} · ${Icons.zap} 接口直测 ${nonInvasiveCnt})`;
        
        // Update filter buttons badge count
        const btnInv = document.getElementById('btnFilterInvasive');
        if (btnInv) btnInv.innerHTML = `${Icons.monitor} 页面实测 (${invasiveCnt})`;
        const btnNonInv = document.getElementById('btnFilterNonInvasive');
        if (btnNonInv) btnNonInv.innerHTML = `${Icons.zap} 接口直测 (${nonInvasiveCnt})`;

        // Initialize all cases selected by default
        allTestCases.forEach(t => selectedCaseIds.add(t.id));

        renderNavCategories(allTestCases);
        renderTableRows(allTestCases);
        updateSelectionUI();
      } catch (err) {
        console.error("加载测试清单失败:", err);
      }
    }

    let currentDrawerMode = 'ALL';

    window.setDrawerModeFilter = function(mode) {
      currentDrawerMode = mode;
      document.querySelectorAll('.drawer-mode-pill').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
      });
      renderNavCategories(allTestCases);
      
      // Also sync table rows
      if (mode === 'ALL') {
        renderTableRows(allTestCases);
      } else if (mode === 'INVASIVE') {
        renderTableRows(allTestCases.filter(t => t.mode === 'INVASIVE'));
      } else if (mode === 'NON_INVASIVE') {
        renderTableRows(allTestCases.filter(t => t.mode === 'NON_INVASIVE'));
      }
    };

    function renderNavCategories(tests) {
      const nav = document.getElementById('drawerNavContainer');
      nav.innerHTML = '';
      
      const invCount = tests.filter(t => t.mode === 'INVASIVE').length;
      const nonInvCount = tests.filter(t => t.mode === 'NON_INVASIVE').length;

      // 1. Compact Segmented Mode Selector at Top of Drawer
      const segWrap = document.createElement('div');
      segWrap.style.cssText = 'display:flex; gap:4px; padding:2px 4px 10px; border-bottom:1px solid var(--g-border); margin-bottom:8px;';
      segWrap.innerHTML = `
        <button type="button" class="drawer-mode-pill ${currentDrawerMode === 'ALL' ? 'active' : ''}" data-mode="ALL" onclick="setDrawerModeFilter('ALL')" title="查看全部业务测试用例">全部 (${tests.length})</button>
        <button type="button" class="drawer-mode-pill ${currentDrawerMode === 'INVASIVE' ? 'active' : ''}" data-mode="INVASIVE" onclick="setDrawerModeFilter('INVASIVE')" title="仅显示页面实测用例(真实浏览器UI交互与表单填报)">${Icons.monitor} 页面实测 (${invCount})</button>
        <button type="button" class="drawer-mode-pill ${currentDrawerMode === 'NON_INVASIVE' ? 'active' : ''}" data-mode="NON_INVASIVE" onclick="setDrawerModeFilter('NON_INVASIVE')" title="仅显示接口直测用例(后端API与数据库契约校验)">${Icons.zap} 接口直测 (${nonInvCount})</button>
      `;
      nav.appendChild(segWrap);

      // Filter tests by selected mode for business category listing
      let filteredTests = tests;
      if (currentDrawerMode === 'INVASIVE') {
        filteredTests = tests.filter(t => t.mode === 'INVASIVE');
      } else if (currentDrawerMode === 'NON_INVASIVE') {
        filteredTests = tests.filter(t => t.mode === 'NON_INVASIVE');
      }

      // Group strictly by Canonical Business Modules
      const groups = {};
      filteredTests.forEach(t => {
        groups[t.category] = groups[t.category] || [];
        groups[t.category].push(t);
      });

      // 'All' item
      const allItem = document.createElement('div');
      allItem.className = 'nav-item active';
      allItem.innerHTML = `<span style="font-weight:600; display:inline-flex; align-items:center; gap:6px;">${Icons.clipboard} 业务用例清单</span> <span class="nav-pill">${filteredTests.length}</span>`;
      allItem.addEventListener('click', () => {
        document.querySelectorAll('.nav-cat-header, .nav-sub-item, .nav-item').forEach(n => n.classList.remove('active'));
        allItem.classList.add('active');
        switchTab('tab-cases');
        renderTableRows(filteredTests);
      });
      nav.appendChild(allItem);

      // Render each Pure Business Category and its Test Cases with Module-level Select All Checkbox
      for (const [cat, list] of Object.entries(groups)) {
        let catIcon = getCategorySvg(cat);

        const catWrap = document.createElement('div');
        catWrap.className = 'nav-cat-wrap';

        // Category Header with Module-level Select All Checkbox (collapsed by default for neatness)
        const catHeader = document.createElement('div');
        catHeader.className = 'nav-cat-header collapsed';
        const catTitle = cat.replace(/^[^\u4e00-\u9fa5a-zA-Z0-9]+/, '').trim();
        catHeader.innerHTML = `
          <div style="display:flex; align-items:center; gap:6px; overflow:hidden; flex:1; margin-right:6px;">
            <span class="arrow">▼</span>
            <input type="checkbox" class="cat-select-chk" data-cat="${cat}" checked title="全选/全不选【${catTitle}】全部用例">
            <span style="flex-shrink:0;">${catIcon}</span>
            <span class="cat-title" style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${cat}">${catTitle}</span>
          </div>
          <span class="nav-pill">${list.length}</span>
        `;

        // Checkbox Click: Toggle all test cases for this specific module
        const catChk = catHeader.querySelector('.cat-select-chk');
        catChk.addEventListener('click', (e) => {
          e.stopPropagation();
          toggleModuleSelection(cat, e.target.checked);
        });

        // Sub List for Cases (collapsed by default)
        const subList = document.createElement('div');
        subList.className = 'nav-sub-list collapsed';

        list.forEach(t => {
          const subItem = document.createElement('div');
          subItem.className = 'nav-sub-item';
          subItem.id = `nav-sub-${t.id}`;
          subItem.title = `${t.id} - ${t.name}`;
          const isInv = t.mode === 'INVASIVE';
          const modeTag = isInv
            ? `<span style="font-size:10px; padding:1px 5px; border-radius:3px; background:#fff3e0; color:#e65100; font-weight:600; flex-shrink:0; display:inline-flex; align-items:center; gap:3px;" title="页面实测 (真实浏览器UI交互与表单)">${Icons.monitor} 页面</span>`
            : `<span style="font-size:10px; padding:1px 5px; border-radius:3px; background:#e8f0fe; color:#1a73e8; font-weight:600; flex-shrink:0; display:inline-flex; align-items:center; gap:3px;" title="接口直测 (后端API与数据库)">${Icons.zap} 接口</span>`;

          subItem.innerHTML = `
            <input type="checkbox" class="sub-case-chk" data-id="${t.id}" data-cat="${cat}" ${selectedCaseIds.has(t.id) ? 'checked' : ''} title="勾选/取消勾选该用例">
            <span class="nav-status-dot" id="nav-dot-${t.id}"></span>
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">${t.name}</span>
            ${modeTag}
          `;

          // Checkbox Click: Toggle single test case selection
          const subChk = subItem.querySelector('.sub-case-chk');
          subChk.addEventListener('click', (e) => {
            e.stopPropagation();
            if (e.target.checked) {
              selectedCaseIds.add(t.id);
            } else {
              selectedCaseIds.delete(t.id);
            }
            updateSelectionUI();
          });

          // Text Click: Auto switch to tab-cases, scroll to row, and highlight
          subItem.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.nav-cat-header, .nav-sub-item, .nav-item').forEach(n => n.classList.remove('active'));
            subItem.classList.add('active');
            catHeader.classList.add('active');

            // 1. 自动切换到对应 tab 页 (用例执行清单)
            switchTab('tab-cases');

            // 2. 检查表格中是否存在此用例，若不在（如当前处于其他过滤分类下），则重新渲染完整或当前分类用例
            let tr = document.getElementById(`row-${t.id}`);
            if (!tr) {
              renderTableRows(list);
              tr = document.getElementById(`row-${t.id}`);
            }

            // 3. 平滑滚动并高亮定位 (在 #caseTableContainer 表格滚动容器内部平滑滚动)
            if (tr) {
              const scrollBox = document.getElementById('caseTableContainer') || document.getElementById('tab-cases');
              if (scrollBox) {
                const trRect = tr.getBoundingClientRect();
                const containerRect = scrollBox.getBoundingClientRect();
                const targetScroll = scrollBox.scrollTop + (trRect.top - containerRect.top) - 40;
                scrollBox.scrollTo({ top: Math.max(0, targetScroll), behavior: 'smooth' });
              }
              tr.classList.remove('row-highlight');
              void tr.offsetWidth;
              tr.classList.add('row-highlight');
            }
          });

          subList.appendChild(subItem);
        });

        // Click on category header (text/arrow): toggles sub-list & filters table & auto-switches to tab-cases!
        catHeader.addEventListener('click', () => {
          const isCollapsed = subList.classList.toggle('collapsed');
          catHeader.classList.toggle('collapsed', isCollapsed);

          document.querySelectorAll('.nav-cat-header, .nav-sub-item, .nav-item').forEach(n => n.classList.remove('active'));
          catHeader.classList.add('active');

          // 自动切换到用例执行清单 Tab!
          switchTab('tab-cases');
          renderTableRows(list);
        });

        catWrap.appendChild(catHeader);
        catWrap.appendChild(subList);
        nav.appendChild(catWrap);
    }
    }

    window.collapseAllCategories = function() {
      document.querySelectorAll('.nav-cat-wrap').forEach(wrap => {
        const header = wrap.querySelector('.nav-cat-header');
        const subList = wrap.querySelector('.nav-sub-list');
        if (header) header.classList.add('collapsed');
        if (subList) subList.classList.add('collapsed');
      });
    };

    window.expandAllCategories = function() {
      document.querySelectorAll('.nav-cat-wrap').forEach(wrap => {
        const header = wrap.querySelector('.nav-cat-header');
        const subList = wrap.querySelector('.nav-sub-list');
        if (header) header.classList.remove('collapsed');
        if (subList) subList.classList.remove('collapsed');
      });
    };

    function renderTableRows(tests) {
      currentDisplayedTests = tests || [];
      const tbody = document.getElementById('caseTableBody');
      tbody.innerHTML = '';
      const countEl = document.getElementById('filteredCasesCount');
      if (countEl) countEl.innerText = `(显示 ${tests.length} 项)`;

      tests.forEach(t => {
        const tr = document.createElement('tr');
        tr.id = `row-${t.id}`;
        
        let catBadgeStyle = "background:var(--g-surface-variant); color:var(--g-text-secondary);";
        let catIcon = getCategorySvg(t.category);
        if (t.category.includes("医嘱")) { catBadgeStyle = "background:#e0f2fe; color:#0369a1;"; }
        else if (t.category.includes("门诊")) { catBadgeStyle = "background:#ecfdf5; color:#047857;"; }
        else if (t.category.includes("住院")) { catBadgeStyle = "background:#f3e8ff; color:#7e22ce;"; }
        else if (t.category.includes("药房") || t.category.includes("药库")) { catBadgeStyle = "background:#fef3c7; color:#b45309;"; }
        else if (t.category.includes("收费") || t.category.includes("医保")) { catBadgeStyle = "background:#fef2f2; color:#b91c1c;"; }
        else if (t.category.includes("医技") || t.category.includes("LIS") || t.category.includes("PACS")) { catBadgeStyle = "background:#f0fdf4; color:#15803d;"; }
        else if (t.category.includes("接口") || t.category.includes("集成")) { catBadgeStyle = "background:#faf5ff; color:#6b21a8;"; }
        else if (t.category.includes("病历") || t.category.includes("EMR") || t.category.includes("文本") || t.category.includes("数值") || t.category.includes("单选") || t.category.includes("控件") || t.category.includes("表达式") || t.category.includes("XML")) { catBadgeStyle = "background:#eef2ff; color:#4338ca;"; }
        else if (t.category.includes("巡检") || t.category.includes("健康") || t.category.includes("底座")) { catBadgeStyle = "background:#ecfeff; color:#0e7490;"; }

        const isInvasive = t.mode === 'INVASIVE';
        const modeBadge = isInvasive
          ? `<span style="font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; background:#fff3e0; color:#e65100; border:1px solid #ffe0b2; display:inline-flex; align-items:center; gap:4px;" title="【页面实测】真实调用Chrome模拟人工点击与表单填报，并保留实操证据截图">${Icons.monitor} 页面实测</span>`
          : `<span style="font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; background:#e8f0fe; color:#1a73e8; border:1px solid #d2e3fc; display:inline-flex; align-items:center; gap:4px;" title="【接口直测】直接调用后端API与Oracle数据校验，毫秒级快速断言，不启动浏览器">${Icons.zap} 接口直测</span>`;

        tr.innerHTML = `
          <td style="text-align:center;"><input type="checkbox" class="case-chk" data-id="${t.id}" ${selectedCaseIds.has(t.id) ? 'checked' : ''}></td>
          <td style="font-family:var(--g-mono); font-size:12px; font-weight:500; color:var(--g-text-secondary);">${t.id}</td>
          <td style="font-weight:500;">
            <div>${t.name}</div>
            ${t.description ? `<div style="font-size:11px; color:var(--g-text-tertiary); margin-top:2px;">${t.description}</div>` : ''}
          </td>
          <td>${modeBadge}</td>
          <td>
            <span style="font-size:11px; font-weight:600; padding:3px 9px; border-radius:12px; display:inline-flex; align-items:center; gap:4px; ${catBadgeStyle}">
              <span>${catIcon}</span> ${t.category}
            </span>
          </td>
          <td id="duration-${t.id}" style="color:var(--g-text-tertiary); font-size:12px;">-</td>
          <td id="status-${t.id}"><span class="status-chip pending">待执行</span></td>
          <td style="text-align:center;">
            <button class="g-btn g-btn-tonal" style="height:26px; font-size:11px; padding:0 10px; border-radius:13px; display:inline-flex; align-items:center; gap:4px;" onclick="runSingleCase('${t.id}')" title="单独执行该用例">${Icons.play} 执行</button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      // Bind change event to table checkboxes
      tbody.querySelectorAll('.case-chk').forEach(c => {
        c.addEventListener('change', (e) => {
          if (e.target.checked) {
            selectedCaseIds.add(e.target.dataset.id);
          } else {
            selectedCaseIds.delete(e.target.dataset.id);
          }
          updateSelectionUI();
        });
      });

      updateSelectionUI();
    }

    window.runSingleCase = function(testId) {
      startExecution([testId]);
    };

    window.filterCases = function(type) {
      document.querySelectorAll('.table-toolbar .g-btn').forEach(b => {
        b.classList.remove('g-btn-tonal', 'active');
        b.classList.add('g-btn-outlined');
      });
      if (window.event && window.event.target) {
        window.event.target.classList.remove('g-btn-outlined');
        window.event.target.classList.add('g-btn-tonal', 'active');
      }

      if (type === 'all') {
        renderTableRows(allTestCases);
      } else if (type === 'invasive') {
        renderTableRows(allTestCases.filter(t => t.mode === 'INVASIVE'));
      } else if (type === 'non_invasive') {
        renderTableRows(allTestCases.filter(t => t.mode === 'NON_INVASIVE'));
      } else if (type === 'order') {
        renderTableRows(allTestCases.filter(t => t.category.includes('医嘱') || t.name.includes('医嘱') || t.id.includes('order')));
      } else if (type === 'his') {
        renderTableRows(allTestCases.filter(t => t.category.includes('门诊') || t.category.includes('住院') || t.category.includes('药房') || t.category.includes('收费') || t.category.includes('医保') || t.category.includes('医技') || t.category.includes('字典') || t.category.includes('HIS')));
      } else if (type === 'billing') {
        renderTableRows(allTestCases.filter(t => 
          t.category.includes('收费') || 
          t.category.includes('医保') || 
          t.workstation_code === 'OUTPATIENT_BILLING' || 
          t.workstation_code === 'INPATIENT_BILLING' || 
          (t.workstation && (t.workstation.includes('收费') || t.workstation.includes('医保'))) ||
          t.id.includes('l6') || 
          t.id.includes('bill') || 
          t.id.includes('charge')
        ));
      } else if (type === 'emr') {
        renderTableRows(allTestCases.filter(t => t.category.includes('病历') || t.id.startsWith('text_') || t.id.startsWith('num_') || t.id.startsWith('choice_') || t.id.startsWith('med_') || t.id.startsWith('expr_') || t.id.startsWith('xml_')));
      } else if (type === 'health') {
        renderTableRows(allTestCases.filter(t => t.category.includes('健康') || t.category.includes('巡检')));
      } else if (type === 'failed') {
        renderTableRows(allTestCases.filter(t => {
          const chip = document.getElementById(`status-${t.id}`);
          return chip && chip.innerText.includes('失败');
        }));
      } else if (type === 'healed') {
        renderTableRows(allTestCases.filter(t => {
          const chip = document.getElementById(`status-${t.id}`);
          return chip && chip.innerText.includes('自愈');
        }));
      }
    };

    // Global Select All Checkboxes (Drawer & Table)
    const chkDrawerSelectAll = document.getElementById('chkSelectAll');
    if (chkDrawerSelectAll) {
      chkDrawerSelectAll.addEventListener('change', (e) => {
        toggleAllSelection(e.target.checked);
      });
    }
    const chkTableSelectAll = document.getElementById('chkTableSelectAll');
    if (chkTableSelectAll) {
      chkTableSelectAll.addEventListener('change', (e) => {
        toggleTableSelection(e.target.checked);
      });
    }

    // Table Header Dropdown Controls
    const btnTableDropdown = document.getElementById('btnTableSelectDropdown');
    if (btnTableDropdown) {
      btnTableDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
        const menu = document.getElementById('tableSelectMenu');
        if (menu) menu.classList.toggle('show');
      });
    }
    document.addEventListener('click', (e) => {
      const menu = document.getElementById('tableSelectMenu');
      const btn = document.getElementById('btnTableSelectDropdown');
      if (menu && menu.classList.contains('show')) {
        if (!menu.contains(e.target) && e.target !== btn) {
          menu.classList.remove('show');
        }
      }
    });

    // Search Filter
    document.getElementById('searchInput').addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = allTestCases.filter(t => t.name.toLowerCase().includes(q) || t.id.toLowerCase().includes(q) || t.category.toLowerCase().includes(q));
      renderTableRows(filtered);
    });

