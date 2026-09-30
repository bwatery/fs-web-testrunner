import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_select_opts = """(() => {
    function pickSelect(labelName, targetText) {
        const items = Array.from(document.querySelectorAll('.el-form-item'));
        const item = items.find(i => i.querySelector('.el-form-item__label')?.innerText?.replace('*', '').trim() === labelName);
        if (!item) return { label: labelName, error: 'item not found' };
        
        const selWrapper = item.querySelector('.el-select__wrapper');
        if (!selWrapper) return { label: labelName, error: 'wrapper not found' };
        selWrapper.click();
        
        const input = item.querySelector('input.el-select__input');
        const controlsId = input ? input.getAttribute('aria-controls') : null;
        const popper = controlsId ? document.getElementById(controlsId) : null;
        if (!popper) return { label: labelName, error: 'popper not found' };
        
        const opts = Array.from(popper.querySelectorAll('.el-select-dropdown__item'));
        const opt = opts.find(o => o.innerText.trim() === targetText || o.innerText.includes(targetText));
        if (opt) {
            opt.click();
            return { label: labelName, ok: true, chosen: opt.innerText.trim() };
        }
        return { label: labelName, error: 'opt not found', available: opts.map(o => o.innerText.trim()) };
    }

    const res = [];
    res.push(pickSelect('结算种类', '全自费病人'));
    res.push(pickSelect('联系人关系', '其他'));
    res.push(pickSelect('入院途径', '急诊'));
    res.push(pickSelect('入院病区', '内一科病区'));
    return res;
})()"""

print(eval_js(js_select_opts))
time.sleep(1.0)

# Check all required fields now
js_verify = """(() => {
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

res_verify = eval_js(js_verify)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\verified_required.json', 'w', encoding='utf-8') as f:
    json.dump(res_verify, f, ensure_ascii=False, indent=2)

print("Saved verified_required.json")
ws.close()
