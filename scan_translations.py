import json
from pathlib import Path
import re

path = Path('/home/avolink/DEV/coffeepie/coffeepie_website/public/translations.json')
obj = json.loads(path.read_text(encoding='utf-8'))

# Find user-readable keys where some non-es translations are identical to es
candidates = []
for k,v in obj.items():
    if len(k) < 20:
        continue
    if '"' in k or ':' in k:
        continue
    es = v.get('es')
    if not es:
        continue
    langs = [lang for lang,val in v.items() if lang != 'es' and val.strip() == es.strip()]
    if langs:
        candidates.append((len(langs), len(k), k, langs))

candidates.sort(key=lambda x:(-x[0], -x[1], x[2]))
for cnt,length,k,langs in candidates[:100]:
    print(cnt, length, k)
    print(langs)
    print()
