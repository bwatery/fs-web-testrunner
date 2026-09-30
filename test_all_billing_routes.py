import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

routes = [
    ("#/inpatient/finance/leavehospitalcalculate", "出院结算"),
    ("#/inpatient/finance/calculateList", "结算清单"),
    ("#/inpatient/finance/prepaycharge", "预交金收费"),
    ("#/inpatient/finance/inpatientdaliy", "住院日结"),
    ("#/inpatient/finance/prepaymoneydaily", "预交金日结"),
    ("#/inpatient/finance/syntheticfquery", "费用明细综合查询"),
]

for route, name in routes:
    nav_js = f"window.location.href = 'http://192.168.1.198:8088/{route}';"
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': nav_js}}))
    ws.recv()
    time.sleep(2)
    
    inspect_js = """(() => {
        const title = document.title;
        const is404 = window.location.hash.includes('/404');
        const vxeTables = document.querySelectorAll('.vxe-table').length;
        const elTables = document.querySelectorAll('.el-table').length;
        const inputs = document.querySelectorAll('input').length;
        const buttons = Array.from(document.querySelectorAll('.el-button')).map(b => b.innerText.trim()).filter(Boolean);
        const snippet = document.body ? document.body.innerText.slice(0, 200).replace(/\\n+/g, ' ') : '';
        return {
            title, is404, vxeTables, elTables, inputs, buttons: buttons.slice(0, 10), snippet
        };
    })()"""
    ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_js, 'returnByValue': True}}))
    res = json.loads(ws.recv())['result']['result']['value']
    print(f"\n[{name}] -> {route}")
    print(json.dumps(res, ensure_ascii=False, indent=2))

ws.close()
