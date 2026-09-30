import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

inspect_tree = """(() => {
    const treeNodes = Array.from(document.querySelectorAll('.el-tree-node__content')).map(el => ({
        text: el.innerText.trim().replace(/\\n+/g, ' '),
        className: el.className
    }));
    return {
        treeNodes: treeNodes
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_tree, 'returnByValue': True}}))
print("Tree nodes:", json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

# Click the specific tree node for 欧伟英 or 测试wt
click_pat = """(() => {
    const el = Array.from(document.querySelectorAll('.el-tree-node__content')).find(e => e.innerText.includes('欧伟英') || e.innerText.includes('测试wt'));
    if (el) {
        el.click();
        return 'Clicked: ' + el.innerText.trim();
    }
    return 'Not found';
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': click_pat, 'returnByValue': True}}))
print("Click res:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(2)

# Now check tables and patient header info!
check_header = """(() => {
    const desc = document.body ? document.body.innerText.slice(0, 800).replace(/\\n+/g, ' ') : '';
    const tables = Array.from(document.querySelectorAll('.el-table')).map(t => {
        const rows = Array.from(t.querySelectorAll('.el-table__body-wrapper tbody tr')).map(tr => {
            return Array.from(tr.querySelectorAll('td .cell')).map(c => c.innerText.trim()).filter(Boolean).join(' | ');
        });
        return {
            rowCount: rows.length,
            rows: rows.slice(0, 5)
        };
    });
    return {
        desc: desc,
        tables: tables
    };
})()"""
ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': check_header, 'returnByValue': True}}))
print("Header & tables:")
print(json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
