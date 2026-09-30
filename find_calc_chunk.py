import requests, re

# Let's search for "查询患者" in JS bundles
# Get script tags
r_index = requests.get("http://192.168.1.198:8088/")
scripts = re.findall(r'src=["\']([^"\']+\.js)["\']', r_index.text)
# Also check preload
scripts += re.findall(r'href=["\']([^"\']+\.js)["\']', r_index.text)

print("Found scripts:", len(scripts))
found_chunks = []
for s in set(scripts):
    url = f"http://192.168.1.198:8088/{s.lstrip('./')}"
    try:
        r = requests.get(url, timeout=3)
        if "查询患者" in r.text or "leavehospitalcalculate" in r.text:
            print(f"Match in {s} (size: {len(r.text)})")
            found_chunks.append((s, r.text))
    except Exception as e:
        pass

if not found_chunks:
    print("Searching router bundle...")
    r_router = requests.get("http://192.168.1.198:8088/static/js/router-vFYEsOqS.js")
    # find chunk for leavehospitalcalculate
    idx = r_router.text.find("leavehospitalcalculate")
    if idx != -1:
        print("router chunk around leavehospitalcalculate:", r_router.text[max(0, idx-100):min(len(r_router.text), idx+200)])
