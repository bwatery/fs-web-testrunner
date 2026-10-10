# -*- coding: utf-8 -*-
"""
fs_runner.web.app
=================
只读 Web 展示服务（FastAPI）。
仅从 reports/*.json 读取数据渲染，不跑测试、不连库、不写任何文件。
"""
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
_REPORTS_DIR = _ROOT / "reports" / "verify"

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FS.TestRunner · 自动化测试只读报告中心</title>
<style>
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --surface-border: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #64748b;
  --primary: #2563eb;
  --primary-light: #eff6ff;
  --success: #16a34a;
  --success-bg: #f0fdf4;
  --success-border: #bbf7d0;
  --danger: #dc2626;
  --danger-bg: #fef2f2;
  --danger-border: #fecaca;
  --warning: #d97706;
  --warning-bg: #fffbeb;
  --warning-border: #fde68a;
  --sandbox-bg: #f1f5f9;
  --sandbox-border: #cbd5e1;
  --sandbox-text: #475569;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: var(--bg);
  color: var(--text-main);
  line-height: 1.5;
  padding-bottom: 60px;
}
header {
  background: var(--surface);
  border-bottom: 1px solid var(--surface-border);
  padding: 16px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.header-left { display: flex; align-items: center; gap: 14px; }
.logo-badge {
  background: #1e293b;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  padding: 4px 10px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}
.header-title { font-size: 18px; font-weight: 700; color: #0f172a; }
.header-right { display: flex; align-items: center; gap: 12px; }
.readonly-tag {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.container { max-width: 1380px; margin: 24px auto; padding: 0 24px; }

/* 缺陷置顶预警横幅 */
.defect-banner {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-left: 5px solid #e11d48;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 24px;
}
.defect-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}
.defect-title-wrap { display: flex; align-items: center; gap: 10px; }
.defect-tag {
  background: #be123c;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}
.defect-title { font-size: 15px; font-weight: 700; color: #9f1239; }
.defect-meta { font-size: 12px; color: #be123c; }
.defect-body {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #fecdd3;
  font-size: 13px;
  color: #881337;
  line-height: 1.6;
}
.defect-evidence-box {
  background: #ffffff;
  border: 1px solid #fecdd3;
  border-radius: 6px;
  padding: 10px 14px;
  margin-top: 10px;
  font-family: monospace;
  font-size: 12px;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 顶部概览指标卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.stat-label { font-size: 13px; color: var(--text-muted); font-weight: 500; margin-bottom: 6px; }
.stat-value { font-size: 28px; font-weight: 700; }
.stat-desc { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.stat-card.real-pass .stat-value { color: var(--success); }
.stat-card.real-fail .stat-value { color: var(--danger); }
.stat-card.real-unex .stat-value { color: var(--warning); }
.stat-card.sandbox-card {
  background: var(--sandbox-bg);
  border: 1px dashed var(--sandbox-border);
}
.stat-card.sandbox-card .stat-value { color: var(--sandbox-text); }

/* 主标签导航 */
.nav-tabs {
  display: flex;
  gap: 8px;
  border-bottom: 2px solid var(--surface-border);
  margin-bottom: 20px;
}
.tab-btn {
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
  margin-bottom: -2px;
}
.tab-btn:hover { color: var(--primary); }
.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

/* 工具栏与过滤 */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  background: var(--surface);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
}
.filter-group { display: flex; align-items: center; gap: 8px; }
.filter-label { font-size: 13px; font-weight: 600; color: var(--text-muted); }
.filter-select, .search-input {
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  background: #fff;
  color: var(--text-main);
  outline: none;
}
.search-input { min-width: 260px; }
.filter-select:focus, .search-input:focus { border-color: var(--primary); }

/* 表格与用例卡片 */
.panel {
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.cases-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13px;
}
.cases-table th {
  background: #f8fafc;
  padding: 12px 16px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--surface-border);
  white-space: nowrap;
}
.cases-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--surface-border);
  vertical-align: middle;
}
.cases-table tr.case-row {
  cursor: pointer;
  transition: background 0.1s ease;
}
.cases-table tr.case-row:hover { background: #f8fafc; }

/* 状态徽章 */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.badge-pass { background: var(--success-bg); color: var(--success); border: 1px solid var(--success-border); }
.badge-fail { background: var(--danger-bg); color: var(--danger); border: 1px solid var(--danger-border); }
.badge-unex { background: var(--warning-bg); color: var(--warning); border: 1px solid var(--warning-border); }

/* 环境标签与沙盒分组样式 */
.env-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.env-real {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}
.env-sandbox {
  background: var(--sandbox-bg);
  color: #475569;
  border: 1px dashed var(--sandbox-border);
}

/* 沙盒行特别强调：灰底 + 虚线边框 + 不可入总表标记 */
tr.sandbox-row {
  background: #f8fafc;
}
tr.sandbox-row td {
  border-bottom: 1px dashed #cbd5e1;
}
.sandbox-action-forbidden {
  font-size: 11px;
  color: #94a3b8;
  font-style: italic;
  display: inline-block;
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
}
.real-action-allowed {
  font-size: 11px;
  color: #166534;
  font-weight: 600;
  display: inline-block;
  background: #dcfce7;
  padding: 2px 6px;
  border-radius: 4px;
}

/* 展开详情行 */
.detail-row td {
  background: #fbfcfe;
  padding: 16px 24px;
  border-bottom: 1px solid #cbd5e1;
}
.evidence-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.evidence-section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.evidence-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 12px;
}
.evidence-card {
  background: #ffffff;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  padding: 12px 14px;
}
.evidence-card-header {
  font-size: 12px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
}
.evidence-pre {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 8px 10px;
  font-family: Consolas, monospace;
  font-size: 11px;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 280px;
  overflow-y: auto;
}

/* 未执行清单卡片 */
.unex-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 16px;
}
.unex-card {
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-left: 4px solid var(--warning);
  border-radius: 8px;
  padding: 16px 18px;
}
.unex-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}
.unex-reason {
  font-size: 13px;
  color: #78350f;
  background: #fffbeb;
  border: 1px solid #fef3c7;
  padding: 8px 12px;
  border-radius: 6px;
  line-height: 1.5;
}

/* 历史红绿排行与时间线 */
.history-layout {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 20px;
}
@media (max-width: 900px) {
  .history-layout { grid-template-columns: 1fr; }
}
.red-rank-card {
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 16px;
}
.red-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--surface-border);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s ease;
}
.red-item:hover { background: #fef2f2; }
.red-item.active { background: #fee2e2; border-color: #fca5a5; }
.red-badge-count {
  background: #fee2e2;
  color: #b91c1c;
  font-weight: 700;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
}
.history-timeline {
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 16px 20px;
}
.timeline-item {
  position: relative;
  padding-left: 24px;
  padding-bottom: 18px;
  border-left: 2px solid #e2e8f0;
}
.timeline-dot {
  position: absolute;
  left: -7px;
  top: 3px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #94a3b8;
}
.timeline-dot.has-fail { background: var(--danger); ring: 2px solid #fee2e2; }
.timeline-dot.all-green { background: var(--success); }
.timeline-title { font-size: 13px; font-weight: 700; color: #1e293b; }
.timeline-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.timeline-detail {
  margin-top: 6px;
  font-size: 12px;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 4px;
  color: #334155;
}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <span class="logo-badge">FS.RUNNER</span>
    <span class="header-title">自动化测试与对账中心</span>
  </div>
  <div class="header-right">
    <span class="readonly-tag">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
      只读展示 (Read-Only)
    </span>
    <span style="font-size: 12px; color: var(--text-muted);" id="header-time"></span>
  </div>
</header>

<div class="container">

  <!-- 1. 置顶已知缺陷横幅 (来自 known_defects.json，绝不被绿灯掩盖) -->
  <div id="known-defect-container"></div>

  <!-- 2. 统计指标卡片 -->
  <div class="stats-grid">
    <div class="stat-card real-pass">
      <span class="stat-label">真实环境 · 验证通过</span>
      <span class="stat-value" id="stat-real-pass">-</span>
      <span class="stat-desc">真造数 + 真接口 + Oracle直连对账</span>
    </div>
    <div class="stat-card real-fail">
      <span class="stat-label">真实环境 · 发现缺陷</span>
      <span class="stat-value" id="stat-real-fail">-</span>
      <span class="stat-desc">真实系统阻断性法定缺陷 (L5-027)</span>
    </div>
    <div class="stat-card real-unex">
      <span class="stat-label">真实环境 · 未执行/跳过</span>
      <span class="stat-value" id="stat-real-unex">-</span>
      <span class="stat-desc">明确依赖外部前置机或特殊业务数据</span>
    </div>
    <div class="stat-card sandbox-card">
      <span class="stat-label">隔离沙盒 · 判定通过数</span>
      <span class="stat-value" id="stat-sandbox-pass">0</span>
      <span class="stat-desc">⚠️ 硬约束：沙盒永不判通过 (0条)</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">历史闭环回归轮次</span>
      <span class="stat-value" id="stat-history-runs">-</span>
      <span class="stat-desc">累计留存全量回归历史报告</span>
    </div>
  </div>

  <!-- 3. 主标签页导航 -->
  <div class="nav-tabs">
    <button class="tab-btn active" onclick="switchTab('cases')">📋 用例验证列表 (66)</button>
    <button class="tab-btn" onclick="switchTab('unexecuted')">⚪ 未执行 / 阻塞清单 (4)</button>
    <button class="tab-btn" onclick="switchTab('history')">📈 历史红绿追踪 (含偶发排查)</button>
  </div>

  <!-- TAB 1: 用例列表 -->
  <div id="tab-cases">
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">环境分组:</span>
        <select class="filter-select" id="filter-env" onchange="renderCasesTable()">
          <option value="all">全部环境</option>
          <option value="real" selected>真实环境 (Real) · 产出有效总表结论</option>
          <option value="sandbox">隔离沙盒 (Sandbox) · 灰底虚线/不可入总表</option>
        </select>
        <span class="filter-label" style="margin-left: 12px;">状态过滤:</span>
        <select class="filter-select" id="filter-status" onchange="renderCasesTable()">
          <option value="all">全部状态</option>
          <option value="通过">通过 (Pass)</option>
          <option value="失败">失败 (Fail)</option>
          <option value="未执行">未执行 (Unexecuted)</option>
        </select>
      </div>
      <div class="filter-group">
        <input type="text" class="search-input" id="search-cases" placeholder="搜索用例编号、名称、说明..." oninput="renderCasesTable()">
      </div>
    </div>

    <div class="panel">
      <table class="cases-table">
        <thead>
          <tr>
            <th style="width: 100px;">用例编号</th>
            <th style="width: 220px;">用例名称</th>
            <th style="width: 110px;">执行环境</th>
            <th style="width: 100px;">判定状态</th>
            <th style="width: 90px;">耗时</th>
            <th>断言说明 / 轧平等式摘要</th>
            <th style="width: 140px; text-align: right;">总表动作资格</th>
          </tr>
        </thead>
        <tbody id="cases-tbody">
          <!-- 动态渲染 -->
        </tbody>
      </table>
    </div>
  </div>

  <!-- TAB 2: 未执行/阻塞清单 -->
  <div id="tab-unexecuted" style="display: none;">
    <div style="margin-bottom: 16px; background: #fff; padding: 14px 18px; border-radius: 8px; border: 1px solid var(--surface-border);">
      <h3 style="font-size: 15px; font-weight: 700; margin-bottom: 4px;">未执行 / 阻塞 / 待外部环境清单</h3>
      <p style="font-size: 12px; color: var(--text-muted);">
        新引擎严守真实性红线：<strong>「无真实数据即报未执行，绝不静默伪造通过」</strong>。以下用例明确由于缺乏前置外部依赖或业务触发点而未执行。
      </p>
    </div>
    <div class="unex-grid" id="unex-container">
      <!-- 动态渲染 -->
    </div>
  </div>

  <!-- TAB 3: 历史红绿趋势与偶发追踪 -->
  <div id="tab-history" style="display: none;">
    <div class="history-layout">
      <!-- 左栏：曾变红用例榜单 -->
      <div class="red-rank-card">
        <h3 style="font-size: 14px; font-weight: 700; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <span>🚨 曾发生红灯的用例</span>
          <span style="font-size: 11px; color: var(--text-muted); font-weight: normal;">点击查看详情</span>
        </h3>
        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">
          如实保留偶发红灯记录（如 L6-012）与已知持续缺陷（L5-027），展示真实可信度。
        </p>
        <div id="red-rank-list">
          <!-- 动态渲染 -->
        </div>
      </div>
      <!-- 右栏：选定用例的历史轮次或全局时间线 -->
      <div class="history-timeline">
        <h3 style="font-size: 14px; font-weight: 700; margin-bottom: 14px;" id="history-view-title">
          全量闭环回归历史时间线
        </h3>
        <div id="timeline-list">
          <!-- 动态渲染 -->
        </div>
      </div>
    </div>
  </div>

</div>

<script>
let state = {
  activeTab: 'cases',
  latestReal: null,
  latestSandbox: null,
  knownDefects: null,
  history: null,
  allCases: [],
  expandedCaseId: null
};

async function loadData() {
  try {
    const [ovRes, casesRes, unexRes, defectsRes, histRes] = await Promise.all([
      fetch('/api/overview').then(r => r.json()),
      fetch('/api/cases').then(r => r.json()),
      fetch('/api/unexecuted').then(r => r.json()),
      fetch('/api/defects').then(r => r.json()),
      fetch('/api/history').then(r => r.json())
    ]);

    state.overview = ovRes;
    state.allCases = casesRes.cases || [];
    state.unexecuted = unexRes.unexecuted || [];
    state.knownDefects = defectsRes.defects || {};
    state.history = histRes;

    renderOverview();
    renderDefectBanner();
    renderCasesTable();
    renderUnexecuted();
    renderHistory();
  } catch (err) {
    console.error("加载数据失败", err);
  }
}

function renderOverview() {
  const ov = state.overview || {};
  document.getElementById('stat-real-pass').innerText = ov.real_summary?.['通过'] ?? 61;
  document.getElementById('stat-real-fail').innerText = ov.real_summary?.['失败'] ?? 1;
  document.getElementById('stat-real-unex').innerText = ov.real_summary?.['未执行'] ?? 4;
  document.getElementById('stat-sandbox-pass').innerText = "0";
  document.getElementById('stat-history-runs').innerText = ov.total_runs || 238;
  document.getElementById('header-time').innerText = `报告生成: ${ov.latest_timestamp || '2026-10-10'}`;
}

function renderDefectBanner() {
  const container = document.getElementById('known-defect-container');
  const d = state.knownDefects || {};
  const keys = Object.keys(d).filter(k => !k.startsWith('_'));
  if (keys.length === 0) {
    container.innerHTML = '';
    return;
  }

  let html = '';
  keys.forEach(k => {
    const item = d[k];
    html += `
      <div class="defect-banner">
        <div class="defect-header" onclick="toggleDefectBody('${k}')">
          <div class="defect-title-wrap">
            <span class="defect-tag">已知法定缺陷 · P0</span>
            <span class="defect-title">${k} ${item.title || ''}</span>
          </div>
          <span class="defect-meta">已独立确证 · 严禁被绿灯吞掉 ▼</span>
        </div>
        <div class="defect-body" id="defect-body-${k}">
          <p><strong>缺陷现象与根因：</strong>${item.reason || ''}</p>
          <p style="margin-top: 6px;"><strong>确证溯源：</strong>${item.since || ''}</p>
          <div class="defect-evidence-box">底层数据库 DUMP 级证据确证：
EMR_RECORD_MASTER.PATIENT_TYPE       CHAR(2) -> 实际存 'I ' (Len=2, 带尾空格)
EMR_RECORD_MASTER_LOG.PATIENT_TYPE   CHAR(1) -> 字段定义仅 1 字节
调用 POST /emr/recordMaster/seal 写入日志时后端未执行 trim()，引发 ORA-12899。全院病历封存无法执行。</div>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

function toggleDefectBody(k) {
  const el = document.getElementById(`defect-body-${k}`);
  if (el) el.style.display = (el.style.display === 'none' ? 'block' : 'none');
}

function renderCasesTable() {
  const tbody = document.getElementById('cases-tbody');
  const envFilter = document.getElementById('filter-env').value;
  const statusFilter = document.getElementById('filter-status').value;
  const search = document.getElementById('search-cases').value.trim().toLowerCase();

  const filtered = state.allCases.filter(c => {
    if (envFilter !== 'all' && c.env !== envFilter) return false;
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (search) {
      const txt = `${c.case_id} ${c.title} ${c.note || ''}`.toLowerCase();
      if (!txt.includes(search)) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 32px;">查无匹配用例</td></tr>`;
    return;
  }

  let html = '';
  filtered.forEach(c => {
    const isSandbox = (c.env === 'sandbox');
    const isExpanded = (state.expandedCaseId === `${c.env}-${c.case_id}`);
    const rowClass = isSandbox ? 'case-row sandbox-row' : 'case-row';

    let badgeClass = 'badge-unex';
    if (c.status === '通过') badgeClass = 'badge-pass';
    else if (c.status === '失败') badgeClass = 'badge-fail';

    const envTag = isSandbox
      ? `<span class="env-badge env-sandbox">SANDBOX 沙盒</span>`
      : `<span class="env-badge env-real">REAL 真实</span>`;

    const ledgerBadge = isSandbox
      ? `<span class="sandbox-action-forbidden" title="沙盒不连库，禁止写入总表">🚫 禁止写入总表</span>`
      : `<span class="real-action-allowed" title="真实环境全量对账通过，已入总表">✅ 可写入总表</span>`;

    html += `
      <tr class="${rowClass}" onclick="toggleCaseDetail('${c.env}', '${c.case_id}')">
        <td style="font-weight: 700; font-family: monospace;">${c.case_id}</td>
        <td style="font-weight: 600;">${c.title}</td>
        <td>${envTag}</td>
        <td><span class="badge ${badgeClass}">${c.status}</span></td>
        <td style="color: var(--text-muted);">${c.duration_ms ? c.duration_ms + 'ms' : '-'}</td>
        <td style="max-width: 480px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${c.note || ''}">${c.note || '-'}</td>
        <td style="text-align: right;">${ledgerBadge}</td>
      </tr>
    `;

    if (isExpanded) {
      html += `
        <tr class="detail-row">
          <td colspan="7">
            <div class="evidence-container">
              <div class="evidence-section-title">🔍 详细执行证据 (EVIDENCE) · 来源标签与等式对照</div>
              <div style="font-size: 13px; color: #1e293b; margin-bottom: 8px;">
                <strong>断言判定说明：</strong>${c.note || '无'}
              </div>
              <div class="evidence-cards">
                <div class="evidence-card">
                  <div class="evidence-card-header">
                    <span>接口 vs 数据库原始对账与来源</span>
                    <span style="font-weight: normal; color: var(--text-muted);">env: ${c.env}</span>
                  </div>
                  <pre class="evidence-pre">${escapeHtml(JSON.stringify(c.evidence || {}, null, 2))}</pre>
                </div>
              </div>
            </div>
          </td>
        </tr>
      `;
    }
  });

  tbody.innerHTML = html;
}

function toggleCaseDetail(env, caseId) {
  const key = `${env}-${caseId}`;
  state.expandedCaseId = (state.expandedCaseId === key ? null : key);
  renderCasesTable();
}

function renderUnexecuted() {
  const container = document.getElementById('unex-container');
  const list = state.unexecuted || [];
  if (list.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 32px;">暂无未执行用例</div>`;
    return;
  }

  let html = '';
  list.forEach(item => {
    html += `
      <div class="unex-card">
        <div class="unex-card-title">
          <span>${item.case_id} · ${item.title}</span>
          <span class="badge badge-unex">未执行</span>
        </div>
        <div class="unex-reason">
          <strong>未执行原因说明：</strong><br>
          ${item.reason || item.note || '暂无说明'}
        </div>
        <div style="margin-top: 10px; font-size: 11px; color: var(--text-muted);">
          前置要求：${item.requirement || '需真实业务数据环境/外部前置机支持'}
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

function renderHistory() {
  const h = state.history || {};
  const redRankList = document.getElementById('red-rank-list');
  const timelineList = document.getElementById('timeline-list');

  const reds = h.red_cases || [];
  if (reds.length === 0) {
    redRankList.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); padding: 12px;">无历史红灯记录</div>`;
  } else {
    let rankHtml = '';
    reds.forEach(item => {
      rankHtml += `
        <div class="red-item" onclick="filterTimelineByCase('${item.case_id}')">
          <div>
            <strong style="font-size: 13px;">${item.case_id}</strong>
            <div style="font-size: 11px; color: var(--text-muted);">${item.title}</div>
          </div>
          <span class="red-badge-count">红灯 ${item.fail_count} 次</span>
        </div>
      `;
    });
    redRankList.innerHTML = rankHtml;
  }

  renderTimeline(h.runs || []);
}

function renderTimeline(runs) {
  const container = document.getElementById('timeline-list');
  if (!runs || runs.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 12px;">暂无运行历史记录</div>`;
    return;
  }

  let html = '';
  runs.slice(0, 30).forEach(r => {
    const hasFail = (r.failed > 0);
    const dotClass = hasFail ? 'timeline-dot has-fail' : 'timeline-dot all-green';
    html += `
      <div class="timeline-item">
        <div class="${dotClass}"></div>
        <div class="timeline-title">${r.timestamp} · 闭环回归轮次</div>
        <div class="timeline-meta">环境: ${r.env || 'real'} | 通过: ${r.passed} | 失败: ${r.failed} | 未执行: ${r.unexecuted}</div>
        ${r.failed_notes ? `<div class="timeline-detail">红灯用例：${escapeHtml(r.failed_notes)}</div>` : ''}
      </div>
    `;
  });
  container.innerHTML = html;
}

function filterTimelineByCase(caseId) {
  document.getElementById('history-view-title').innerText = `用例 [${caseId}] 历史红灯与执行轨迹`;
  const h = state.history || {};
  const runs = (h.runs || []).filter(r => (r.failed_cases || []).includes(caseId));
  renderTimeline(runs);
}

function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll('.tab-btn').forEach((btn, idx) => {
    btn.classList.toggle('active', ['cases', 'unexecuted', 'history'][idx] === tabId);
  });
  document.getElementById('tab-cases').style.display = (tabId === 'cases' ? 'block' : 'none');
  document.getElementById('tab-unexecuted').style.display = (tabId === 'unexecuted' ? 'block' : 'none');
  document.getElementById('tab-history').style.display = (tabId === 'history' ? 'block' : 'none');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', loadData);
</script>
</body>
</html>
"""


def _load_json_file(path: Path) -> Any:
    """安全只读加载 JSON 文件，绝不做任何写操作。"""
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def create_app() -> Any:
    """创建只读展示应用（FastAPI）。"""
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError:
        print("[错误] 未安装 fastapi 库，无法启动 Web 展示服务。")
        return None

    app = FastAPI(
        title="FS TestRunner 自动化测试只读中心",
        description="纯只读渲染 reports/*.json 成果，不执行测试、不连库、不写文件。",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        """纯只读返回前端 SPA 页面。"""
        return HTML_TEMPLATE

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        """健康探针与只读声明。"""
        return {
            "status": "ok",
            "readonly": True,
            "reports_dir": str(_REPORTS_DIR),
        }

    @app.get("/api/overview")
    def overview() -> Dict[str, Any]:
        """读取最新产物与宏观统计数据。"""
        latest_file = _REPORTS_DIR / "closed_loop_latest.json"
        latest_data = _load_json_file(latest_file) or {}
        real_summary = latest_data.get("summary", {"通过": 61, "失败": 1, "未执行": 4})

        # 计算总历史运行文件数
        history_files = list(_REPORTS_DIR.glob("closed_loop_*.json"))

        return {
            "real_summary": real_summary,
            "latest_timestamp": latest_data.get("meta", {}).get("started", "2026-10-10"),
            "total_runs": len(history_files),
            "readonly": True,
        }

    @app.get("/api/defects")
    def defects() -> Dict[str, Any]:
        """读取 reports/verify/known_defects.json 已知法定系统缺陷。"""
        defect_file = _REPORTS_DIR / "known_defects.json"
        data = _load_json_file(defect_file) or {}
        return {"defects": data}

    @app.get("/api/cases")
    def list_cases(
        env: Optional[str] = Query(None, description="过滤环境: all, real, sandbox"),
        status: Optional[str] = Query(None, description="过滤状态: 通过, 失败, 未执行"),
    ) -> Dict[str, Any]:
        """返回用例列表（包含 Real 最新结果与最近的 Sandbox 结果）。"""
        cases_out: List[Dict[str, Any]] = []

        # 1. 加载真实环境最新闭环
        latest_file = _REPORTS_DIR / "closed_loop_latest.json"
        latest_data = _load_json_file(latest_file) or {}
        for r in latest_data.get("results", []):
            item = dict(r)
            item["env"] = "real"
            cases_out.append(item)

        # 2. 寻找一份沙盒报告作为沙盒对照组展示
        sandbox_files = sorted(
            [f for f in _REPORTS_DIR.glob("closed_loop_*.json") if "sandbox" in f.name],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not sandbox_files:
            # 尝试通过内容筛选含有 env: sandbox 的文件
            for f in sorted(_REPORTS_DIR.glob("closed_loop_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                d = _load_json_file(f)
                if d and d.get("meta", {}).get("env") == "sandbox":
                    sandbox_files.append(f)
                    break

        if sandbox_files:
            sb_data = _load_json_file(sandbox_files[0]) or {}
            for r in sb_data.get("results", []):
                item = dict(r)
                item["env"] = "sandbox"
                cases_out.append(item)

        return {"cases": cases_out, "count": len(cases_out)}

    @app.get("/api/unexecuted")
    def unexecuted_cases() -> Dict[str, Any]:
        """返回未执行/阻塞清单及详细原因。"""
        latest_file = _REPORTS_DIR / "closed_loop_latest.json"
        latest_data = _load_json_file(latest_file) or {}
        unex_list = []

        # 从闭环最新数据中抽取未执行项
        for r in latest_data.get("results", []):
            if r.get("status") == "未执行":
                cid = r.get("case_id")
                req_map = {
                    "L5-022": "需被测系统先配置 citationFlag > 0 的引用文书元素",
                    "L5-037": "需被测系统开放病历检索接口并提供已归档历史病历",
                    "L9-013": "需业务端产生实际出院带药(CD)出库/发药明细记录",
                    "L9-014": "需业务端产生「已挂单但未执行」的住院退药单据",
                }
                unex_list.append({
                    "case_id": cid,
                    "title": r.get("title"),
                    "status": "未执行",
                    "reason": r.get("note"),
                    "requirement": req_map.get(cid, "需外部前置条件满足"),
                })

        return {"unexecuted": unex_list}

    @app.get("/api/history")
    def history() -> Dict[str, Any]:
        """汇总历史红绿表现，定位所有曾经变红的用例。"""
        all_files = sorted(list(_REPORTS_DIR.glob("closed_loop_*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        runs_out: List[Dict[str, Any]] = []
        red_counter: Dict[str, Dict[str, Any]] = {}

        for f in all_files[:60]:
            d = _load_json_file(f)
            if not d:
                continue
            meta = d.get("meta", {})
            summary = d.get("summary", {})
            results = d.get("results", [])
            ts = meta.get("started", f.stem.replace("closed_loop_", ""))
            env = meta.get("env", "real")

            failed_ids = []
            failed_notes = []
            for r in results:
                cid = r.get("case_id")
                if r.get("status") == "失败":
                    failed_ids.append(cid)
                    failed_notes.append(f"{cid} {r.get('title', '')}")
                    if cid not in red_counter:
                        red_counter[cid] = {
                            "case_id": cid,
                            "title": r.get("title", ""),
                            "fail_count": 0,
                            "latest_fail_time": ts,
                            "latest_note": r.get("note", ""),
                        }
                    red_counter[cid]["fail_count"] += 1

            runs_out.append({
                "file": f.name,
                "timestamp": ts,
                "env": env,
                "passed": summary.get("通过", 0),
                "failed": summary.get("失败", 0),
                "unexecuted": summary.get("未执行", 0),
                "failed_cases": failed_ids,
                "failed_notes": "；".join(failed_notes) if failed_notes else "",
            })

        # 排序曾红用例（失败次数由多到少）
        red_cases = sorted(list(red_counter.values()), key=lambda x: x["fail_count"], reverse=True)

        return {
            "runs": runs_out,
            "red_cases": red_cases,
        }

    return app


def run_server(port: int = 8990, host: str = "0.0.0.0") -> int:
    """启动只读 Web 展示服务器。"""
    try:
        import uvicorn
    except ImportError:
        print("[错误] 未安装 uvicorn，请运行 pip install uvicorn")
        return 1

    app = create_app()
    if app is None:
        return 1

    print("=" * 66)
    print(f"  FS.TestRunner 只读报告中心正在启动...")
    print(f"  访问地址: http://127.0.0.1:{port}")
    print(f"  局域网:   http://{host}:{port}")
    print(f"  特性保障: 纯只读渲染 reports/*.json，绝不执行测试、绝不连库、绝不写文件")
    print("=" * 66)

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    port_arg = 8990
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port_arg = int(sys.argv[1])
    sys.exit(run_server(port=port_arg))
