import requests, json

r = requests.post('http://192.168.1.198:8081/login', json={'username': 'admin', 'password': 'admin123'}, timeout=3)
token = r.json().get('data')
headers = {'Authorization': f'Bearer {token}'}

# Try getRouters
r_routes = requests.get('http://192.168.1.198:8081/getRouters', headers=headers)
print("getRouters status:", r_routes.status_code)
if r_routes.status_code == 200:
    data = r_routes.json().get('data', [])
    print("Total routes:", len(data))
    
    def dump_menu(menus, depth=0):
        for m in menus:
            title = m.get('meta', {}).get('title', m.get('name', ''))
            path = m.get('path', '')
            comp = m.get('component', '')
            print("  " * depth + f"- {title} (path: {path}, comp: {comp})")
            if 'children' in m and m['children']:
                dump_menu(m['children'], depth + 1)
                
    dump_menu(data)
else:
    print(r_routes.text[:500])
