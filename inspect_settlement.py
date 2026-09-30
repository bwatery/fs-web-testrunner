import requests
import json
import time
import websocket

tabs = requests.get('http://127.0.0.1:9222/json', proxies={'http': None, 'https': None}).json()
page = next(t for t in tabs if t.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

# Click '选择' button
click_js = """(() => {
    const btns = Array.from(document.querySelectorAll('button, .el-button'));
    const selBtn = btns.find(b => {
        const t = b.innerText ? b.innerText.trim().replace(/\\s+/g, '') : '';
        return t === '选择' || t.includes('选择');
    });
    if (selBtn) {
        selBtn.click();
        return { clicked: true, text: selBtn.innerText.trim(), class: selBtn.className };
    }
    return { clicked: false, allBtns: btns.map(b => b.innerText.trim()) };
})()"""

ws.send(json.dumps({
    "id": 1,
    "method": "Runtime.evaluate",
    "params": {"expression": click_js, "returnByValue": True}
}))
msg1 = json.loads(ws.recv())
res1 = msg1.get("result", {}).get("result", {}).get("value", {})
print("Click result:", res1)

time.sleep(2)

# Check dialog
check_js = """(() => {
    const dialogs = Array.from(document.querySelectorAll('.el-dialog')).filter(d => d.offsetHeight > 0);
    return dialogs.map(d => ({
        title: d.querySelector('.el-dialog__title') ? d.querySelector('.el-dialog__title').innerText.trim() : '',
        tableRows: d.querySelectorAll('tbody tr').length
    }));
})()"""

ws.send(json.dumps({
    "id": 2,
    "method": "Runtime.evaluate",
    "params": {"expression": check_js, "returnByValue": True}
}))
msg2 = json.loads(ws.recv())
res2 = msg2.get("result", {}).get("result", {}).get("value", {})
print("Dialog check:", res2)

ws.close()
