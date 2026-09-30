import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js = """(() => {
    // Look for tabs, submenus, or action buttons in the current page
    const items = Array.from(document.querySelectorAll('.el-menu-item, .el-tabs__item, .el-button, a')).map(el => ({
        tag: el.tagName,
        text: el.innerText.trim(),
        href: el.getAttribute('href'),
        cls: el.className
    })).filter(i => i.text && !i.text.includes('\\n'));
    
    return items;
})()"""

items = eval_js(js)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\doctor_nav_items.json', 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
print("Saved doctor_nav_items.json, count:", len(items) if isinstance(items, list) else 0)
ws.close()
