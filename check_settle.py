import requests
import json
import sys

# Get token from validator
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()
session = v.get_browser_session()
token = session.get("token")
print("Has token:", bool(token))

if token:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for endpoint in ["/getRouters", "/menu", "/faith/system/menu/getRouters", "/router", "/system/menu/getRouters"]:
        try:
            r = requests.get(f"http://192.168.1.198:8081{endpoint}", headers=headers, timeout=2)
            if r.status_code == 200:
                print(f"[FOUND] {endpoint}: status={r.status_code}")
                data = r.json()
                open("menus.json", "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
                break
            else:
                print(f"[{endpoint}] status={r.status_code}")
        except Exception as e:
            print(f"[{endpoint}] error={e}")
