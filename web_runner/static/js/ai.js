/**
 * HIS WebRunner - AI Agent Hub Frontend Controller
 * Manages AI integrations, MCP tools showcase, interactive playground, and copy-paste utilities.
 */

window.copyToClipboard = function(text, btn) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showCopySuccess(btn);
    }).catch(() => fallbackCopy(text, btn));
  } else {
    fallbackCopy(text, btn);
  }
};

function fallbackCopy(text, btn) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showCopySuccess(btn);
  } catch (err) {
    if (window.showToast) window.showToast("复制失败，请手动选择复制", "warning");
  }
  document.body.removeChild(ta);
}

function showCopySuccess(btn) {
  if (window.showToast) {
    window.showToast("已成功复制到剪贴板！", "success");
  }
  if (btn) {
    const originalText = btn.innerHTML;
    btn.innerHTML = "<span>✓ 已复制</span>";
    btn.style.borderColor = "var(--g-green)";
    btn.style.color = "var(--g-green)";
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.style.borderColor = "";
      btn.style.color = "";
    }, 1600);
  }
}

// 快速填入演练输入框
window.setPlaygroundPrompt = function(text) {
  const input = document.getElementById('aiPlaygroundInput');
  if (input) {
    input.value = text;
    input.focus();
    window.runAiSimulation();
  }
};

// 触发 AI 自然语言模拟演练
window.runAiSimulation = async function() {
  const input = document.getElementById('aiPlaygroundInput');
  const resultBox = document.getElementById('aiSimulationOutput');
  const btn = document.getElementById('btnRunAiSim');
  if (!input || !resultBox) return;

  const prompt = input.value.trim();
  if (!prompt) {
    if (window.showToast) window.showToast("请输入测试需求或自然语言指令", "warning");
    return;
  }

  // Loading state
  btn.disabled = true;
  btn.innerHTML = `<span>⏳ 智能体思考中...</span>`;
  resultBox.innerHTML = `
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:60px 20px; color:var(--g-text-secondary); gap:12px;">
      <div style="width:32px; height:32px; border:3px solid var(--g-blue-surface); border-top-color:var(--g-blue); border-radius:50%; animation:spin 0.8s linear infinite;"></div>
      <div style="font-size:13px;">AI Agent 正在分析需求、生成思维链并调度测试工具...</div>
    </div>
  `;

  try {
    const resp = await fetch('/api/ai/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt })
    });
    const data = await resp.json();

    if (data.error) {
      resultBox.innerHTML = `
        <div class="ai-step-card" style="border-left-color:var(--g-red);">
          <div class="ai-step-title" style="color:var(--g-red);">❌ 执行异常</div>
          <div class="ai-step-content">${data.message || '调度失败'}</div>
        </div>
      `;
      return;
    }

    // Render multi-step execution timeline
    const stepsHtml = (data.reasoning_steps || []).map((step, idx) => `
      <div style="font-size:12px; margin-bottom:4px; display:flex; align-items:flex-start; gap:6px;">
        <span style="color:var(--g-blue); font-weight:600;">[步骤 ${idx + 1}]</span>
        <span>${step}</span>
      </div>
    `).join('');

    const rawResultJson = JSON.stringify(data.raw_result || {}, null, 2);

    resultBox.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:12px;">
        
        <!-- Step 1: CoT Reasoning -->
        <div class="ai-step-card" style="border-left-color:#8b5cf6;">
          <div class="ai-step-title" style="color:#7c3aed;">
            <svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            <span>🧠 智能体意图识别与思维链 (Reasoning & Decision)</span>
          </div>
          <div class="ai-step-content" style="margin-top:6px;">
            ${stepsHtml}
          </div>
        </div>

        <!-- Step 2: Tool Invocation -->
        <div class="ai-step-card" style="border-left-color:#3b82f6;">
          <div class="ai-step-title" style="color:#2563eb;">
            <svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            <span>🛠️ 决策调用工具: <code style="background:rgba(59,130,246,0.1); color:#2563eb; padding:2px 6px; border-radius:4px;">${data.selected_tool}</code></span>
          </div>
          <div class="ai-step-content" style="margin-top:4px;">
            <div style="font-size:11px; color:var(--g-text-tertiary); margin-bottom:4px;">入参 Payload:</div>
            <pre style="background:var(--g-surface); padding:8px 10px; border-radius:6px; border:1px solid var(--g-border); font-size:11.5px; margin:0; font-family:monospace; overflow-x:auto;">${JSON.stringify(data.tool_args, null, 2)}</pre>
          </div>
        </div>

        <!-- Step 3: Raw Observation -->
        <div class="ai-step-card" style="border-left-color:#10b981;">
          <div class="ai-step-title" style="color:#059669; justify-content:space-between;">
            <div style="display:flex; align-items:center; gap:6px;">
              <svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
              <span>⚡ HIS 执行引擎实时返回 (Raw System Observation)</span>
            </div>
            <span style="font-size:11px; background:rgba(16,185,129,0.12); color:#059669; padding:2px 8px; border-radius:10px;">状态: 正常</span>
          </div>
          <div class="ai-step-content" style="margin-top:6px;">
            <pre style="background:var(--g-surface); padding:8px 10px; border-radius:6px; border:1px solid var(--g-border); font-size:11.5px; margin:0; font-family:monospace; max-height:160px; overflow-y:auto;">${rawResultJson}</pre>
          </div>
        </div>

        <!-- Step 4: Final Summary Report -->
        <div style="background:var(--g-surface-variant); border:1px solid var(--g-blue); border-radius:10px; padding:14px 16px;">
          <div style="font-size:13px; font-weight:600; color:var(--g-blue); display:flex; align-items:center; gap:6px; margin-bottom:6px;">
            <svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            <span>🤖 AI 质检专家总结汇报:</span>
          </div>
          <div style="font-size:13px; color:var(--g-text-primary); line-height:1.6;">
            ${data.reply}
          </div>
        </div>

      </div>
    `;

    // If tests were triggered, notify user
    if (data.selected_tool === 'his_run_tests' && window.showToast) {
      window.showToast("已由 AI 触发自动化测试，正在后台执行！", "run");
    }

  } catch (err) {
    resultBox.innerHTML = `
      <div class="ai-step-card" style="border-left-color:var(--g-red);">
        <div class="ai-step-title" style="color:var(--g-red);">网络或接口错误</div>
        <div class="ai-step-content">${err.message || '请求失败'}</div>
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> <span>AI 智能决策与调度</span>`;
  }
};
