import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket, time
from fs_web_testrunner.core.login_validator import LoginValidator

validator = LoginValidator()
res = validator.switch_identity_in_browser(35, 910092, '#/inpatient/doctor/workstation')
print('Switched to doctor:', res.get('message'))
time.sleep(2.5)

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // 1. Get all patient list items on the left
    const patientCards = Array.from(document.querySelectorAll('*')).filter(el => {
        return el.innerText && el.innerText.includes('欧伟英') && el.innerText.length < 150 && el.children.length >= 1;
    });

    // 2. Look for the left sidebar patient item
    let targetCard = null;
    for (let c of patientCards) {
        if (c.innerText.includes('1581001') || c.innerText.includes('401-10') || c.innerText.includes('72岁')) {
            targetCard = {
                tag: c.tagName,
                className: c.className,
                text: c.innerText.replace(/\\n+/g, ' '),
                hasClick: typeof c.click === 'function'
            };
            break;
        }
    }

    // 3. Menus and toolbars
    const menus = Array.from(document.querySelectorAll('.el-sub-menu__title, .el-menu-item')).map(m => m.innerText.trim());
    const rightItems = Array.from(document.querySelectorAll('.el-button, [class*="bar"], [class*="item"]')).filter(b => {
        return b.innerText && (b.innerText.includes('医嘱') || b.innerText.includes('工作站') || b.innerText.includes('处方'));
    }).map(b => ({ text: b.innerText.trim().replace(/\\n+/g, ' '), class: b.className }));

    return {
        url: window.location.href,
        targetCard: targetCard,
        menus: menus,
        orderElements: rightItems.slice(0, 15)
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
val = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(val, ensure_ascii=False, indent=2))
ws.close()
