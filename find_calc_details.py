import requests

r_router = requests.get("http://192.168.1.198:8088/static/js/router-vFYEsOqS.js")
idx = 0
while True:
    idx = r_router.text.find("leavehospitalcalculate", idx)
    if idx == -1:
        break
    print(f"Index {idx}:", r_router.text[max(0, idx-150):min(len(r_router.text), idx+250)])
    idx += len("leavehospitalcalculate") + 1
