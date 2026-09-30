import requests, re

# Let's inspect router-vFYEsOqS.js for routes
r = requests.get("http://192.168.1.198:8088/static/js/router-vFYEsOqS.js")
text = r.text

# In vue-router with dynamic imports, routes often look like:
# path: "/..." or path: '...'
# or component: () => import(...)
routes_raw = re.findall(r'path:\s*["\']([^"\']+)["\']', text)
print("Routes found via 'path:':", len(routes_raw))
for rt in sorted(set(routes_raw)):
    print(" -", rt)

# Also let's check index-DosD0Tqj.js
r2 = requests.get("http://192.168.1.198:8088/static/js/index-DosD0Tqj.js")
routes_idx = re.findall(r'path:\s*["\']([^"\']+)["\']', r2.text)
print("\nRoutes found in index.js via 'path:':", len(routes_idx))
for rt in sorted(set(routes_idx)):
    print(" -", rt)
