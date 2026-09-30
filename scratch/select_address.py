import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_city = """(() => {
    const addr = document.querySelector('.address-select');
    if (!addr) return { err: 'no address select' };
    const selects = Array.from(addr.querySelectorAll('.el-select'));
    if (selects.length < 2) return { err: 'less than 2 selects' };
    
    // Click City select
    const cityWrapper = selects[1].querySelector('.el-select__wrapper');
    cityWrapper.click();
    
    const input = selects[1].querySelector('input.el-select__input');
    const controlsId = input ? input.getAttribute('aria-controls') : null;
    const popper = controlsId ? document.getElementById(controlsId) : null;
    const opts = popper ? Array.from(popper.querySelectorAll('.el-select-dropdown__item')).map(o => o.innerText.trim()).filter(Boolean) : [];
    
    // Pick 广州市 if available, or first option
    let chosen = null;
    if (popper) {
        const gz = Array.from(popper.querySelectorAll('.el-select-dropdown__item')).find(o => o.innerText.includes('广州') || o.innerText.includes('市'));
        const opt = gz || popper.querySelector('.el-select-dropdown__item');
        if (opt) {
            chosen = opt.innerText.trim();
            opt.click();
        }
    }
    return { controlsId, opts, chosen };
})()"""

print("City select:", eval_js(js_city))
time.sleep(1.0)

# Now inspect and select district
js_dist = """(() => {
    const addr = document.querySelector('.address-select');
    const selects = Array.from(addr.querySelectorAll('.el-select'));
    if (selects.length < 3) return { err: 'less than 3 selects' };
    
    // Click District select
    const distWrapper = selects[2].querySelector('.el-select__wrapper');
    distWrapper.click();
    
    const input = selects[2].querySelector('input.el-select__input');
    const controlsId = input ? input.getAttribute('aria-controls') : null;
    const popper = controlsId ? document.getElementById(controlsId) : null;
    const opts = popper ? Array.from(popper.querySelectorAll('.el-select-dropdown__item')).map(o => o.innerText.trim()).filter(Boolean) : [];
    
    let chosen = null;
    if (popper) {
        const opt = Array.from(popper.querySelectorAll('.el-select-dropdown__item')).find(o => o.innerText.includes('越秀') || o.innerText.includes('区')) || popper.querySelector('.el-select-dropdown__item');
        if (opt) {
            chosen = opt.innerText.trim();
            opt.click();
        }
    }
    return { controlsId, opts, chosen };
})()"""

print("District select:", eval_js(js_dist))
ws.close()
