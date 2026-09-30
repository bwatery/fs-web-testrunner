import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

js = """(() => {
    const inputs = document.querySelectorAll('input');
    return {
        inputsCount: inputs.length,
        inputs: Array.from(inputs).map(i => ({ placeholder: i.placeholder, val: i.value, type: i.type })),
        buttons: Array.from(document.querySelectorAll('button')).map(b => b.innerText)
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}))
print('Form:', json.loads(ws.recv())['result']['result']['value'])

# Try to fill form using native input setter or typing
fill_js = """(() => {
    const inputs = document.querySelectorAll('input');
    const u = inputs[0];
    const p = inputs[1];
    
    // React/Vue setter hack
    const setVal = (el, val) => {
        const valSetter = Object.getOwnPropertyDescriptor(el.__proto__, 'value') || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        valSetter.set.call(el, val);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    };
    
    setVal(u, 'admin');
    setVal(p, '123456');
    
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('录') || b.innerText.includes('登')) || document.querySelector('button');
    if (btn) {
        btn.click();
        return 'Button clicked: ' + btn.innerText;
    }
    return 'No button';
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': fill_js, 'returnByValue': True}}))
print('Fill result:', json.loads(ws.recv())['result']['result']['value'])

time.sleep(3)

ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': 'window.location.href', 'returnByValue': True}}))
print('URL after 3s:', json.loads(ws.recv())['result']['result']['value'])

ws.send(json.dumps({'id': 4, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText', 'returnByValue': True}}))
print('Body after 3s:', repr(json.loads(ws.recv())['result']['result']['value'][:100]))

ws.close()
