import requests, json, websocket, time

# 1. Login with admin/admin123
r_login = requests.post('http://192.168.1.198:8081/login', json={'username': 'admin', 'password': 'admin123'})
token = r_login.json().get('data')
print("Login token:", bool(token))

# 2. Exchange to role 34 (住院收费), dept 2 (收费处)
r_ex = requests.post('http://192.168.1.198:8081/exchangeLogin', headers={'Authorization': f'Bearer {token}'}, json={'roleId': 34, 'deptId': 2})
billing_token = r_ex.json().get('data')
print("Billing token exchanged:", bool(billing_token))

# 3. Connect to Chrome CDP and inject token, roleDeptCache, and navigate to #/inpatient/finance/leavehospitalcalculate
tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

inject_js = f"""(() => {{
    sessionStorage.setItem('shop-vite-token', '{billing_token}');
    
    let cache = {{}};
    try {{ cache = JSON.parse(localStorage.getItem('userRoleDeptCache') || '{{}}'); }} catch(e) {{}}
    cache["1"] = cache["1"] || {{}};
    cache["1"]["34"] = 2;
    localStorage.setItem('userRoleDeptCache', JSON.stringify(cache));
    localStorage.removeItem('caughtRoutes');
    
    window.location.href = 'http://192.168.1.198:8088/#/inpatient/finance/leavehospitalcalculate';
    window.location.reload();
    return 'injected and reloading';
}})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inject_js, 'returnByValue': True}}))
print("CDP inject:", json.loads(ws.recv()))

# Wait for page to load
time.sleep(3)

# Check page health and elements
check_js = """(() => {
    return {
        url: window.location.href,
        hash: window.location.hash,
        title: document.title,
        is404: window.location.hash.includes('/404') || (document.body && document.body.innerText.includes('404')),
        tables: document.querySelectorAll('.el-table').length,
        inputs: document.querySelectorAll('input').length,
        buttons: Array.from(document.querySelectorAll('.el-button')).map(b => b.innerText.trim()).filter(Boolean),
        bodySnippet: document.body ? document.body.innerText.slice(0, 300).replace(/\\n+/g, ' ') : ''
    };
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': check_js, 'returnByValue': True}}))
res = json.loads(ws.recv())['result']['result']['value']
print("\nPage inspection result:")
print(json.dumps(res, ensure_ascii=False, indent=2))

ws.close()
