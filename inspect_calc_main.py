import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

# Inspect how to close the current dialog and see what buttons exist on leavehospitalcalculate
close_dialog = """(() => {
    const closeBtns = Array.from(document.querySelectorAll('.el-dialog__close, .el-dialog__headerbtn'));
    if (closeBtns.length > 0) {
        closeBtns[closeBtns.length - 1].click();
        return 'Closed top dialog';
    }
    return 'No close btn';
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': close_dialog, 'returnByValue': True}}))
print("Close dialog:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(1)

# Check all buttons and inputs now
inspect_main = """(() => {
    const btns = Array.from(document.querySelectorAll('.el-button')).map(b => ({
        text: b.innerText.trim(),
        visible: b.offsetParent !== null,
        className: b.className
    }));
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item')).map(t => t.innerText.trim());
    return {
        tabs: tabs,
        buttons: btns.filter(b => b.visible)
    };
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_main, 'returnByValue': True}}))
print("Main page tabs & buttons:", json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
