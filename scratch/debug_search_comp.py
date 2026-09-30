import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Find the Vue component of the search input
js_inspect_comp = """(() => {
    const input = document.getElementById('ConditionSearchExcludedInpatient');
    if (!input) return { err: 'input not found' };
    
    // traverse up to find vue component
    let el = input;
    let comp = null;
    while (el && !comp) {
        if (el.__vueParentComponent) {
            comp = el.__vueParentComponent;
        }
        el = el.parentElement;
    }
    
    if (!comp) return { err: 'vue comp not found' };
    
    const setupState = comp.setupState || {};
    const props = comp.props || {};
    
    // Check methods and refs
    return {
        compName: comp.type?.name || comp.type?.__name,
        propsKeys: Object.keys(props),
        setupKeys: Object.keys(setupState),
        // Check if there are patient lists
        stateValues: {
            searchValue: setupState.searchValue || setupState.keyword || setupState.query || setupState.modelValue,
            selectedType: setupState.selectedType || setupState.searchType,
            hasTableData: !!(setupState.tableData || setupState.patientList || setupState.dataList),
            tableDataLength: (setupState.tableData || setupState.patientList || setupState.dataList || []).length
        }
    };
})()"""

res = eval_js(js_inspect_comp)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\search_comp_debug.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved search_comp_debug.json")
ws.close()
