    // Floating Toast / Bubble Notification Helper
    function showToast(message, type = 'info', title = null, duration = 3200) {
      const container = document.getElementById('toastContainer');
      if (!container) return;

      const toast = document.createElement('div');
      toast.className = `g-toast toast-${type}`;

      const iconMap = {
        info: Icons.info,
        success: Icons.checkCircle,
        warning: Icons.alertTriangle,
        danger: Icons.xCircle,
        run: Icons.play,
        stop: Icons.stop,
        env: Icons.zap,
        role: Icons.target,
        copy: Icons.copy
      };
      const icon = iconMap[type] || Icons.info;

      const esc = (s) => (s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));
      toast.innerHTML = `
        <span class="g-toast-icon">${icon}</span>
        <div class="g-toast-content">
          ${title ? `<div class="g-toast-title">${esc(title)}</div>` : ''}
          <div class="g-toast-desc">${esc(message)}</div>
        </div>
        <span class="g-toast-close" title="关闭"><svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></span>
      `;

      const closeBtn = toast.querySelector('.g-toast-close');
      let timer = null;
      const dismiss = () => {
        if (timer) clearTimeout(timer);
        toast.classList.add('hide');
        setTimeout(() => {
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 220);
      };

      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          dismiss();
        });
      }
      toast.addEventListener('click', dismiss);

      container.appendChild(toast);

      if (duration > 0) {
        timer = setTimeout(dismiss, duration);
      }
    }

