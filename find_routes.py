import requests, re

js_url = "http://192.168.1.198:8088/static/js/router-vFYEsOqS.js"
r = requests.get(js_url)
print("router len:", len(r.text))

# Let's search for "inpatient" or "charge" or "pay" or "settle"
matches = re.findall(r'["\'](/[^"\']+)["\']', r.text)
routes = set()
for m in matches:
    if any(k in m for k in ['inpatient', 'outpatient', 'charge', 'settle', 'pay', 'confirm', 'fee', 'doctor', 'nurse', 'pharmacy', 'emr']):
        routes.add(m)

print("Found routes in router bundle:")
for rt in sorted(routes):
    print(" -", rt)
