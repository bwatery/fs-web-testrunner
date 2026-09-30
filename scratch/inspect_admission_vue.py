import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 检查入院登记表单组件的内部数据结构 (通过 Vue 组件实例)
res = eval_js("""(() => {
    // 寻找表单内部的 Vue component
    const formEl = document.querySelector('.el-form');
    if (!formEl) return { err: 'no form' };
    
    // 抓取所有的 el-select
    const selects = Array.from(document.querySelectorAll('.el-form-item')).map(item => {
        const label = item.querySelector('.el-form-item__label') ? item.querySelector('.el-form-item__label').innerText.trim() : '';
        const select = item.querySelector('.el-select');
        const input = item.querySelector('input');
        return {
            label,
            hasSelect: !!select,
            placeholder: input ? input.placeholder : '',
            value: input ? input.value : ''
        };
    }).filter(x => x.label);

    return { selects: selects.slice(0, 20) };
})()""")

print("Form inspection:", json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
