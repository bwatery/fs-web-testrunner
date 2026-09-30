import requests, re

js_url = "http://192.168.1.198:8088/static/js/router-vFYEsOqS.js"
r = requests.get(js_url)

for m in ["settle", "charge", "inpatient", "outpatient", "doctor", "nurse"]:
    idx = 0
    found = 0
    while True:
        pos = r.text.lower().find(m, idx)
        if pos == -1 or found > 3:
            break
        print(f"Keyword '{m}' at {pos}:")
        print(repr(r.text[max(0, pos-80):min(len(r.text), pos+120)]))
        idx = pos + len(m) + 1
        found += 1
