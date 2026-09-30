import requests

# Check routes for role 35 (住院医生) and role 36 (住院护士)
r = requests.post('http://192.168.1.198:8081/login', json={'username': 'admin', 'password': 'admin123'})
token = r.json().get('data')

for role_id, role_name, dept_id in [(35, "住院医生", 910092), (36, "住院护士", 910131)]:
    r_ex = requests.post('http://192.168.1.198:8081/exchangeLogin', headers={'Authorization': f'Bearer {token}'}, json={'roleId': role_id, 'deptId': dept_id})
    ex_token = r_ex.json().get('data')
    r_rt = requests.get('http://192.168.1.198:8081/getRouters', headers={'Authorization': f'Bearer {ex_token}'})
    print(f"\nRoutes for {role_name}:")
    for m in r_rt.json().get('data', []):
        m_path = m.get('path', '')
        for c in m.get('children', []):
            full = f"{m_path}/{c.get('path', '')}".replace('//', '/')
            print(f"  - #{full} ({c.get('component')})")
