    // Terminal Drawer Controls & Drag Resize
    const termDrawer = document.getElementById('termDrawer');
    const termToggleBtn = document.getElementById('termToggleBtn');
    const btnMinTerm = document.getElementById('btnMinTerm');
    const btnToggleFloat = document.getElementById('btnToggleFloat');
    const btnClearTerm = document.getElementById('btnClearTerm');
    const resizeHandle = document.getElementById('termResizeHandle');

    function toggleTermCollapse(forceState) {
      if (typeof forceState === 'boolean') {
        termDrawer.classList.toggle('collapsed', forceState);
      } else {
        termDrawer.classList.toggle('collapsed');
      }
      const isCollapsed = termDrawer.classList.contains('collapsed');
      if (btnMinTerm) {
        btnMinTerm.innerHTML = isCollapsed ? `${Icons.chevronUp} 展开` : `${Icons.chevronDown} 收起`;
      }
    }

    if (termToggleBtn) {
      termToggleBtn.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON' && !e.target.closest('button')) {
          toggleTermCollapse();
        }
      });
    }

    if (btnMinTerm) {
      btnMinTerm.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleTermCollapse();
      });
    }

    if (btnToggleFloat) {
      btnToggleFloat.addEventListener('click', (e) => {
        e.stopPropagation();
        const isFloating = termDrawer.classList.toggle('floating');
        btnToggleFloat.innerHTML = isFloating ? `${Icons.pin} 底部停靠` : `${Icons.card} 悬浮`;
        btnToggleFloat.title = isFloating ? '恢复底部停靠分割模式' : '切换为悬浮窗模式，完全不占下方测试用例空间';
        if (isFloating) {
          termDrawer.classList.remove('collapsed');
          if (btnMinTerm) btnMinTerm.innerHTML = `${Icons.chevronDown} 收起`;
        }
      });
    }

    if (btnClearTerm) {
      btnClearTerm.addEventListener('click', (e) => {
        e.stopPropagation();
        document.getElementById('termLogsContainer').innerHTML = '';
        const line = document.getElementById('termLatestLine');
        if (line) line.innerText = '';
      });
    }

    // Drag-to-Resize Handle
    let isDraggingTerm = false;
    let startY = 0;
    let startH = 0;

    if (resizeHandle && termDrawer) {
      resizeHandle.addEventListener('mousedown', (e) => {
        isDraggingTerm = true;
        startY = e.clientY;
        startH = termDrawer.offsetHeight;
        resizeHandle.classList.add('active');
        termDrawer.classList.remove('collapsed');
        if (btnMinTerm) btnMinTerm.innerHTML = `${Icons.chevronDown} 收起`;
        document.body.style.userSelect = 'none';
        document.body.style.cursor = 'ns-resize';
      });

      window.addEventListener('mousemove', (e) => {
        if (!isDraggingTerm) return;
        const diff = startY - e.clientY;
        const maxH = window.innerHeight - 140;
        const newH = Math.max(70, Math.min(maxH, startH + diff));
        termDrawer.style.height = newH + 'px';
      });

      window.addEventListener('mouseup', () => {
        if (isDraggingTerm) {
          isDraggingTerm = false;
          resizeHandle.classList.remove('active');
          document.body.style.userSelect = '';
          document.body.style.cursor = '';
        }
      });
    }


// =========================================================================
// Local Persistent Disk Logs Viewer Integration
// =========================================================================
const btnOpenDiskLogs = document.getElementById('btnOpenDiskLogs');
const diskLogsModal = document.getElementById('diskLogsModal');
const diskLogsModalDialog = document.getElementById('diskLogsModalDialog');
const diskLogSourceSelect = document.getElementById('diskLogSourceSelect');
const diskLogLimitSelect = document.getElementById('diskLogLimitSelect');
const diskLogContent = document.getElementById('diskLogContent');
const diskLogMetaInfo = document.getElementById('diskLogMetaInfo');
const btnRefreshDiskLogs = document.getElementById('btnRefreshDiskLogs');
const btnClearDiskLogs = document.getElementById('btnClearDiskLogs');
const btnToggleLogWrap = document.getElementById('btnToggleLogWrap');
const btnToggleLogFullscreen = document.getElementById('btnToggleLogFullscreen');
const btnCopyDiskLogs = document.getElementById('btnCopyDiskLogs');

async function reloadDiskLogsView() {
  if (!diskLogContent) return;
  const source = diskLogSourceSelect ? diskLogSourceSelect.value : 'app';
  const limit = diskLogLimitSelect ? parseInt(diskLogLimitSelect.value, 10) : 200;
  diskLogContent.textContent = '正在读取本地磁盘日志文件...';

  try {
    const data = await fetchDiskLogs(source, limit);
    if (data.lines && data.lines.length > 0) {
      diskLogContent.textContent = data.lines.join('\n');
    } else {
      diskLogContent.textContent = `[${source}.log] 暂无日志记录`;
    }
    diskLogContent.scrollTop = diskLogContent.scrollHeight;

    // Load file sizes and update metadata
    const fileData = await fetchDiskLogFiles();
    if (fileData.files && diskLogMetaInfo) {
      const activeFile = fileData.files.find(f => (f.name || f.filename || '').startsWith(source));
      if (activeFile) {
        const fname = activeFile.name || activeFile.filename;
        const fsize = activeFile.size_formatted || ((activeFile.size_bytes / 1024).toFixed(1) + ' KB');
        diskLogMetaInfo.textContent = `当前文件: logs/${fname} | 大小: ${fsize} | 自动循环滚动归档 (max 10MB)`;
      } else {
        diskLogMetaInfo.textContent = `当前文件: logs/${source}.log | 自动循环滚动归档 (max 10MB)`;
      }
    }
  } catch (err) {
    diskLogContent.textContent = `加载日志失败: ${err}`;
  }
}
window.reloadDiskLogsView = reloadDiskLogsView;

if (btnOpenDiskLogs) {
  btnOpenDiskLogs.addEventListener('click', (e) => {
    e.stopPropagation();
    if (diskLogsModal) {
      diskLogsModal.style.display = 'flex';
      reloadDiskLogsView();
    }
  });
}

if (diskLogSourceSelect) {
  diskLogSourceSelect.addEventListener('change', reloadDiskLogsView);
}

if (diskLogLimitSelect) {
  diskLogLimitSelect.addEventListener('change', reloadDiskLogsView);
}

if (btnRefreshDiskLogs) {
  btnRefreshDiskLogs.addEventListener('click', () => {
    reloadDiskLogsView();
    showToast('本地磁盘日志已刷新', 'info', '日志刷新', 1500);
  });
}

let isLogWrapped = false;
if (btnToggleLogWrap && diskLogContent) {
  btnToggleLogWrap.addEventListener('click', () => {
    isLogWrapped = !isLogWrapped;
    if (isLogWrapped) {
      diskLogContent.style.whiteSpace = 'pre-wrap';
      diskLogContent.style.wordBreak = 'break-all';
      btnToggleLogWrap.textContent = '换行: 开';
      btnToggleLogWrap.classList.add('g-btn-filled');
      btnToggleLogWrap.classList.remove('g-btn-tonal');
    } else {
      diskLogContent.style.whiteSpace = 'pre';
      diskLogContent.style.wordBreak = 'normal';
      btnToggleLogWrap.textContent = '换行: 关';
      btnToggleLogWrap.classList.remove('g-btn-filled');
      btnToggleLogWrap.classList.add('g-btn-tonal');
    }
  });
}

let isLogFullscreen = false;
if (btnToggleLogFullscreen && diskLogsModalDialog) {
  btnToggleLogFullscreen.addEventListener('click', () => {
    isLogFullscreen = !isLogFullscreen;
    if (isLogFullscreen) {
      diskLogsModalDialog.style.width = '98vw';
      diskLogsModalDialog.style.maxWidth = '98vw';
      diskLogsModalDialog.style.height = '96vh';
      diskLogsModalDialog.style.maxHeight = '96vh';
      if (diskLogContent) {
        diskLogContent.style.maxHeight = 'calc(96vh - 165px)';
        diskLogContent.style.minHeight = 'calc(96vh - 165px)';
      }
      btnToggleLogFullscreen.title = '退出全屏 (还原窗口)';
    } else {
      diskLogsModalDialog.style.width = '95%';
      diskLogsModalDialog.style.maxWidth = '1160px';
      diskLogsModalDialog.style.height = '';
      diskLogsModalDialog.style.maxHeight = '90vh';
      if (diskLogContent) {
        diskLogContent.style.maxHeight = '540px';
        diskLogContent.style.minHeight = '300px';
      }
      btnToggleLogFullscreen.title = '切换全屏/常规尺寸';
    }
  });
}

if (btnCopyDiskLogs && diskLogContent) {
  btnCopyDiskLogs.addEventListener('click', async () => {
    const text = diskLogContent.textContent || '';
    if (!text || text.includes('暂无日志记录')) {
      showToast('当前没有可复制的日志内容', 'warning', '复制提示', 2000);
      return;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      showToast(`已复制 ${text.split('\n').length} 行日志到剪贴板`, 'success', '复制成功', 2000);
    } catch (e) {
      showToast('复制日志失败: ' + e, 'danger', '复制失败', 2500);
    }
  });
}

if (btnClearDiskLogs) {
  btnClearDiskLogs.addEventListener('click', async () => {
    if (!confirm('确定要清空本地磁盘中的所有日志记录吗？')) return;
    try {
      const res = await clearDiskLogs();
      if (res && (res.status === 'ok' || res.status === 'success' || (res.message && res.message.includes('成功')))) {
        showToast('本地磁盘日志已清空', 'success', '清空成功', 2000);
        reloadDiskLogsView();
      } else {
        showToast(`清空失败: ${res ? res.message : '未知错误'}`, 'danger', '清空失败', 3000);
      }
    } catch (err) {
      showToast(`清空异常: ${err}`, 'danger', '清空异常', 3000);
    }
  });
}
