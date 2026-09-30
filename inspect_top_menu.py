import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // 1. Look for top menu items
    const topMenuItems = Array.from(document.querySelectorAll('.el-menu-item, .el-sub-menu, [role="menuitem"], .nav-menu li, .header-menu *'));
    const workItems = topMenuItems.filter(i => i.innerText && i.innerText.trim() === '住院工作站');
    
    // 2. Also check Vue router routes from window
    let routerRoutes = [];
    try {
        const app = document.querySelector('#app') || document.body;
        // Check router if accessible
    } catch(e) {}

    return {
        workItems: workItems.map(w => ({
            tag: w.tagName,
            class: w.className,
            text: w.innerText.trim(),
            parentClass: w.parentElement ? w.parentElement.className : ''
        })),
        allTopText: Array.from(document.querySelectorAll('.el-sub-menu__title, .el-menu--horizontal .el-menu-item')).map(e => e.innerText.trim())
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
