import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // Inspect vxe-table or parent vue component
    const vxe = document.querySelector('.vxe-table');
    let listeners = [];
    let methods = [];
    try {
        // Check vue component
        let comp = vxe.__vueParentComponent;
        if (comp) {
            listeners = Object.keys(comp.vnode.props || {});
        }
    } catch(e) {}

    // Try cell dblclick on the table
    const ouTr = Array.from(document.querySelectorAll('.vxe-body--row')).find(r => r.innerText.includes('欧伟英'));
    
    // Simulate real double click event on the TR and each TD
    let dblSuccess = false;
    if (ouTr) {
        ouTr.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
        const firstTd = ouTr.querySelector('td');
        if (firstTd) {
            firstTd.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
            const wrapper = firstTd.querySelector('.vxe-cell');
            if (wrapper) {
                wrapper.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
                dblSuccess = true;
            }
        }
    }

    return {
        hasVxe: !!vxe,
        listeners: listeners,
        dblSuccess: dblSuccess
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value')
print('Inspection:', res)
ws.close()
