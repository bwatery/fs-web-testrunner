import requests, time

r = requests.post('http://127.0.0.1:8989/api/run', json={'test_ids': ['cpoe_01_closed_loop_e2e_invasive']}, timeout=5)
print('Run started:', r.json())

for _ in range(30):
    time.sleep(2.0)
    st = requests.get('http://127.0.0.1:8989/api/status', timeout=3).json()
    print('Engine running:', st.get('is_running'))
    if not st.get('is_running'):
        break

rep = requests.get('http://127.0.0.1:8989/api/results', timeout=3).json()
for t in rep.get('results', []):
    if t.get('test_id') == 'cpoe_01_closed_loop_e2e_invasive':
        print(f"Result: {t.get('name')} -> {t.get('status')}")
        for l in t.get('logs', []):
            print("  ", l)
