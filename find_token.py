import json, re

with open(r'C:\Users\94870\.gemini\antigravity-cli\brain\7b4b2295-459b-417f-982c-6a139b2569b3\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        matches = re.findall(r'eyJhbGciOiJIUzUxMiJ9\.[A-Za-z0-9_\-\.]+', line)
        if matches:
            for m in matches:
                print("FOUND TOKEN:", m)
