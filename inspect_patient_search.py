import requests, sys

sys.stdout.reconfigure(encoding='utf-8')

r = requests.get("http://192.168.1.198:8088/static/js/diyPatientSearch-DSTFz60J.js")
print("diyPatientSearch size:", len(r.text))

# Search for cellDBLClick or row click or emit
for keyword in ["emit", "select", "dblclick", "cell-dblclick", "row-click", "click"]:
    idx = 0
    while True:
        pos = r.text.lower().find(keyword, idx)
        if pos == -1:
            break
        snippet = r.text[max(0, pos-40):min(len(r.text), pos+80)]
        print(f"Keyword '{keyword}':", snippet.replace('\n', ' '))
        idx = pos + len(keyword) + 1
        if idx > 3000:
            break
