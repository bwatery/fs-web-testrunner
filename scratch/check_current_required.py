import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js = """(() => {
    const requiredItems = Array.from(document.querySelectorAll('.el-form-item.is-required'));
    const report = [];
    for (const item of requiredItems) {
        const label = item.querySelector('.el-form-item__label')?.innerText?.replace('*', '').trim() || '';
        const input = item.querySelector('input');
        const selectText = item.querySelector('.el-select__selected-item span')?.innerText?.trim() || item.querySelector('.el-select__placeholder')?.innerText?.trim() || '';
        const val = input ? (input.value || selectText) : selectText;
        report.push({
            label,
            hasValue: !!val,
            val
        });
    }
    return report;
})()"""

res = eval_js(js)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\current_required_status.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved current_required_status.json")
ws.close()
