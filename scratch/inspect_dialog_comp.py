import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Inspect the dialog component in Vue
js = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    
    // Find Vue instance of this dialog
    let vnode = d.__vueParentComponent;
    let comp = null;
    let curr = d;
    while (curr && !comp) {
        if (curr.__vueParentComponent) {
            comp = curr.__vueParentComponent;
        }
        curr = curr.parentElement;
    }
    
    const state = comp ? comp.setupState : null;
    return {
        hasComp: !!comp,
        keys: state ? Object.keys(state) : null,
        // Check event listeners or methods on search
        inputHtml: d.querySelector('.el-input')?.outerHTML,
        searchWrapper: d.querySelector('.el-select')?.parentElement?.outerHTML
    };
})()"""

res = eval_js(js)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\dialog_comp_info.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved dialog_comp_info.json")
ws.close()
