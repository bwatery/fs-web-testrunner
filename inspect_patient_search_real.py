import requests, sys

sys.stdout.reconfigure(encoding='utf-8')
r = requests.get("http://192.168.1.198:8088/static/js/diyPatientSearch-BsbGyHH1.js")
print("Size:", len(r.text))

# Search for event bindings on vxe-table or row selection
for kw in ["celldblclick", "cellclick", "current-change", "emit", "select"]:
    idx = 0
    while True:
        pos = r.text.lower().find(kw, idx)
        if pos == -1:
            break
        print(f"Keyword '{kw}':", r.text[max(0, pos-50):min(len(r.text), pos+100)].replace('\n', ' '))
        idx = pos + len(kw) + 1
        if idx > 10000:
            break
