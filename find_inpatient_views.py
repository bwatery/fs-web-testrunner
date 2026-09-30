import requests, re

r = requests.get('http://192.168.1.198:8088/static/js/router-vFYEsOqS.js')
matches = re.findall(r'(\.\./views/inpatient/[^"\']+)', r.text)
for m in sorted(set(matches)):
    print(m)
