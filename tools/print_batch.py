import os
import json
import sys

for step in sys.argv[1:]:
    path = rfos.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
    print(f'================ STEP {step} ================')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    for item in d['normalized_result']['items']:
        print(f"--- {item.get('address')} ({item.get('procedure')}) ---")
        print((item.get('pseudocode') or '').strip())
