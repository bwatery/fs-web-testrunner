import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

def inspect_field(label):
    js = f"""(() => {{
        const items = Array.from(document.querySelectorAll('.el-form-item'));
        const item = items.find(i => i.querySelector('.el-form-item__label')?.innerText?.replace('*', '').trim() === '{label}');
        if (!item) return {{ err: 'no item' }};
        const sel = item.querySelector('.el-select__wrapper');
        if (!sel) return {{ err: 'no wrapper' }};
        sel.click();
        const input = item.querySelector('input.el-select__input');
        const controlsId = input ? input.getAttribute('aria-controls') : null;
        const popper = controlsId ? document.getElementById(controlsId) : null;
        const opts = popper ? Array.from(popper.querySelectorAll('.el-select-dropdown__item')).map(o => o.innerText.trim()).filter(Boolean) : [];
        return {{ label: '{label}', controlsId, opts }};
    }})()"""
    return eval_js(js)

fields = ['结算种类', '联系人关系', '入院途径', '入院病区']
results = {}
for f in fields:
    results[f] = inspect_field(f)
    time.sleep(0.5)

with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\inspect_missing_opts.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Saved inspect_missing_opts.json")
ws.close()
