import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 1. Close dialog and reopen fresh
js_reopen = """(() => {
    // Click close/cancel on dialog
    const cancelBtn = Array.from(document.querySelectorAll('.el-dialog button')).find(b => b.innerText.trim() === '取消');
    if (cancelBtn) cancelBtn.click();
    
    // Or close icon
    const closeBtn = document.querySelector('.el-dialog__headerbtn');
    if (closeBtn) closeBtn.click();
    
    return 'closed';
})()"""
print("Close dialog:", eval_js(js_reopen))
time.sleep(1.0)

# Re-open dialog via '选择' button
js_click_open = """(() => {
    const sel = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === '选择');
    if (sel) sel.click();
    return 'reopened';
})()"""
print("Reopen dialog:", eval_js(js_click_open))
time.sleep(1.5)

# In fresh dialog: type '陈新强' into search box, DO NOT click any tree department!
js_search_fresh = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    
    const input = Array.from(d.querySelectorAll('input')).find(i => i.placeholder === '请输入');
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, '陈新强');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Click search button
    const searchBtn = d.querySelector('.el-input-group__append button');
    if (searchBtn) searchBtn.click();
    
    return {
        inputVal: input.value,
        hasSearchBtn: !!searchBtn
    };
})()"""

print("Fresh search without tree click:", eval_js(js_search_fresh))
time.sleep(2.0)

# Check table rows now
js_check_fresh = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    const rows = Array.from(d.querySelectorAll('.el-table__row, tr, .vxe-body--row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    const emptyBlock = d.querySelector('.el-table__empty-block, .el-empty')?.innerText;
    return {
        count: rows.length,
        rows,
        emptyBlock
    };
})()"""

res_fresh = eval_js(js_check_fresh)
print("Fresh search result rows:", res_fresh)

ws.close()
