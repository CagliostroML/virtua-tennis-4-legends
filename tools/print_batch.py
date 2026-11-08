import json
import sys

for step in sys.argv[1:]:
    path = rf'C:\Users\acorr\.gemini\antigravity\brain\870ede98-2986-4047-bf85-9d8d3fdf8f4d\.system_generated\steps\{step}\output.txt'
    print(f'================ STEP {step} ================')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    for item in d['normalized_result']['items']:
        print(f"--- {item.get('address')} ({item.get('procedure')}) ---")
        print((item.get('pseudocode') or '').strip())
