import requests, json

r = requests.post('http://192.168.1.198:8081/login', json={'username': 'admin', 'password': 'admin123'}, timeout=3)
token = r.json().get('data')

# Check role 34 (住院收费) and role 14 (门诊收费)
for role_id, role_name in [
    (34, "住院收费"),
    (14, "门诊收费"),
    (38, "终端确认"),
    (35, "住院医生"),
]:
    # find depts for this role
    r_dept = requests.get(f'http://192.168.1.198:8081/dept?roleId={role_id}', headers={'Authorization': f'Bearer {token}'})
    depts = r_dept.json().get('data', [])
    dept_id = depts[0]['deptId'] if depts else 2
    dept_name = depts[0]['deptName'] if depts else "默认"
    
    # exchangeLogin
    r_ex = requests.post('http://192.168.1.198:8081/exchangeLogin', headers={'Authorization': f'Bearer {token}'}, json={'roleId': role_id, 'deptId': dept_id})
    ex_token = r_ex.json().get('data')
    if not ex_token:
        print(f"Failed to exchange to {role_name}:", r_ex.text)
        continue
    
    # getRouters for this role
    r_rt = requests.get('http://192.168.1.198:8081/getRouters', headers={'Authorization': f'Bearer {ex_token}'})
    routes_data = r_rt.json().get('data', [])
    print(f"\n=================== 角色: {role_name} (roleId: {role_id}, dept: {dept_name}-{dept_id}) ===================")
    for m in routes_data:
        m_path = m.get('path', '')
        for c in m.get('children', []):
            title = c.get('meta', {}).get('title', c.get('name', ''))
            c_path = c.get('path', '')
            comp = c.get('component', '')
            full = f"{m_path}/{c_path}".replace('//', '/')
            print(f"  * [{title}] -> #{full} ({comp})")
