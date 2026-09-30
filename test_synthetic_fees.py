import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

# Navigate to syntheticfquery
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': "window.location.href = 'http://192.168.1.198:8088/#/inpatient/finance/syntheticfquery';", 'returnByValue': True}}))
ws.recv()
time.sleep(2)

# Click patient in tree/list
click_pat_js = """(() => {
    // Find node with 欧伟英 or 测试wt
    const nodes = Array.from(document.querySelectorAll('.el-tree-node__label, span, div')).filter(el => {
        return el.innerText && (el.innerText.includes('欧伟英') || el.innerText.includes('测试wt'));
    });
    if (nodes.length > 0) {
        nodes[0].click();
        return 'Clicked patient: ' + nodes[0].innerText.trim();
    }
    return 'Patient not found in DOM';
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': click_pat_js, 'returnByValue': True}}))
print("Click res:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(2)

# Inspect tables and fees
inspect_fees = """(() => {
    const tables = Array.from(document.querySelectorAll('.el-table'));
    const tableData = tables.map((t, idx) => {
        const headers = Array.from(t.querySelectorAll('th .cell')).map(th => th.innerText.trim()).filter(Boolean);
        const rows = Array.from(t.querySelectorAll('.el-table__body-wrapper tbody tr')).map(tr => {
            return Array.from(tr.querySelectorAll('td .cell')).map(c => c.innerText.trim()).filter(Boolean).join(' | ');
        });
        return {
            tableIdx: idx,
            headers: headers,
            rowCount: rows.length,
            rows: rows.slice(0, 5)
        };
    });
    
    // Find total money summaries
    const summaryText = Array.from(document.querySelectorAll('.el-statistic, .el-descriptions, .fee-summary, div')).filter(d => {
        return d.innerText && (d.innerText.includes('总金额') || d.innerText.includes('自费') || d.innerText.includes('费用合计'));
    }).map(d => d.innerText.trim()).slice(0, 3);
    
    return {
        tableData: tableData,
        summaryText: summaryText
    };
})()"""
ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_fees, 'returnByValue': True}}))
res = json.loads(ws.recv())['result']['result']['value']
print("Fee details:")
print(json.dumps(res, ensure_ascii=False, indent=2))

ws.close()
