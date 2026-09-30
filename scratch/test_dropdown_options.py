import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Test finding options for each select
script = """(() => {
    function getSelectOptions(labelSubstring) {
        const items = Array.from(document.querySelectorAll('.el-form-item'));
        const item = items.find(i => i.querySelector('.el-form-item__label')?.innerText?.includes(labelSubstring));
        if (!item) return { label: labelSubstring, error: 'item not found' };
        
        const selWrapper = item.querySelector('.el-select__wrapper') || item.querySelector('.el-select');
        if (!selWrapper) return { label: labelSubstring, error: 'select not found' };
        
        selWrapper.click();
        
        // Find visible poppers
        const poppers = Array.from(document.querySelectorAll('.el-select__popper:not([style*="display: none"]), .el-popper:not([style*="display: none"])'));
        let foundOpts = [];
        for (const p of poppers) {
            const items = Array.from(p.querySelectorAll('.el-select-dropdown__item'));
            if (items.length > 0) {
                foundOpts = items.map(it => it.innerText.trim()).filter(Boolean);
                break;
            }
        }
        
        // close
        document.body.click();
        return { label: labelSubstring, options: foundOpts };
    }

    const testLabels = ['病人来源', '入院情况', '入院途径', '联系人关系', '入院病区', '入院科室', '入院医生'];
    const results = {};
    for (const l of testLabels) {
        results[l] = getSelectOptions(l);
    }
    return results;
})()"""

res = eval_js(script)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\dropdown_options_result.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved dropdown_options_result.json")

ws.close()
