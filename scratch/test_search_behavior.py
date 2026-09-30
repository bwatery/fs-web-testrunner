import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Test:
# 1. Click '全部' tab on top-left of the dialog
# 2. Click '骨二科' in the tree
# 3. What does the table show?
# 4. Then click search button with '陈新强' in input
# 5. Does it find 陈新强 or not?
js_test = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    
    const logs = [];
    
    // Check search button in append slot
    const searchBtn = d.querySelector('.el-input-group__append button');
    logs.push({ hasSearchBtn: !!searchBtn, searchBtnVisible: searchBtn ? searchBtn.offsetWidth > 0 : false });
    
    // Click '骨二科'
    const gu2 = Array.from(d.querySelectorAll('.el-tree-node')).find(n => n.innerText && n.innerText.includes('骨二科'));
    if (gu2) {
        gu2.click();
        logs.push({ clickedGu2: true });
    }
    
    return logs;
})()"""

print("Test 1:", eval_js(js_test))
time.sleep(2.0)

# Check table rows now
js_check1 = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    const rows = Array.from(d.querySelectorAll('.el-table__row, tr, .vxe-body--row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    return {
        tableRowsUnderGu2: rows
    };
})()"""
print("Rows under 骨二科:", eval_js(js_check1))

# Now click the search button with '陈新强'
js_click_search_btn = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    const searchBtn = d.querySelector('.el-input-group__append button');
    if (searchBtn) searchBtn.click();
    return { clickedSearch: !!searchBtn };
})()"""
print("Click search button:", eval_js(js_click_search_btn))
time.sleep(2.0)

# Check table rows after search
print("Rows after search under 骨二科:", eval_js(js_check1))

ws.close()
