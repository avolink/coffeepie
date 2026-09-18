import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

path = Path('AVG_SLICE_COST.json')
with path.open() as f:
    data = json.load(f)

new_usd = Decimal('0.29') / Decimal('3500')

def fmt_decimal(value):
    d = Decimal(value).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
    return format(d, 'f')

for c in data['countries']:
    c['cost'] = fmt_decimal(Decimal(str(c['fx_rate_usd'])) * new_usd)

data['meta']['base_usd'] = fmt_decimal(new_usd)
data['meta']['exchange_rate_note'] = (
    'All costs are approximate, derived from 1 COFP = 0.29 COP ≈ 0.00008286 USD at 3,500 COP/USD. '
    'Exchange rates are indicative (2025–2026 averages). Actual Provider settlement amounts are recalculated '
    'at the time of each fiat withdrawal request using a live governance-approved rate oracle. Regional pricing '
    'may be further adjusted by local provider governance votes.'
)

# Create a JSON string with exact decimal formatting for cost and base_usd values.
# Use a manual output pass so numeric values are not written in scientific notation.
lines = []
lines.append('{\n')
lines.append('  "meta": {\n')
for key in [
    'description', 'unit', 'base_reference', 'base_usd', 'exchange_rate_note', 'tier_note', 'last_updated', 'version'
]:
    if key == 'base_reference':
        lines.append('    "base_reference": {\n')
        br = data['meta'][key]
        for br_key in ['country', 'iso2', 'iso3', 'currency_code', 'cost', 'note']:
            val = br[br_key]
            if isinstance(val, str):
                lines.append(f'      "{br_key}": "{val}",\n')
            else:
                lines.append(f'      "{br_key}": {val},\n')
        lines[-1] = lines[-1].rstrip(',\n') + '\n'
        lines.append('    },\n')
    elif key == 'base_usd':
        lines.append(f'    "base_usd": {data["meta"]["base_usd"]},\n')
    elif key == 'exchange_rate_note':
        lines.append(f'    "exchange_rate_note": "{data["meta"]["exchange_rate_note"]}",\n')
    elif key == 'description' or key == 'unit' or key == 'tier_note' or key == 'last_updated' or key == 'version':
        lines.append(f'    "{key}": "{data["meta"][key]}",\n')
lines[-1] = lines[-1].rstrip(',\n') + '\n'
lines.append('  },\n')
lines.append('  "countries": [\n')
for idx, c in enumerate(data['countries']):
    lines.append('    {\n')
    for field in ['name', 'iso2', 'iso3', 'currency_name', 'currency_code', 'symbol', 'fx_rate_usd', 'cost']:
        val = c.get(field)
        if isinstance(val, str):
            lines.append(f'      "{field}": "{val}",\n')
        elif isinstance(val, float) or isinstance(val, int):
            if field == 'fx_rate_usd':
                lines.append(f'      "{field}": {val},\n')
            else:
                lines.append(f'      "{field}": {val},\n')
        else:
            lines.append(f'      "{field}": {val},\n')
    if 'note' in c:
        lines.append(f'      "note": "{c["note"]}",\n')
    lines[-1] = lines[-1].rstrip(',\n') + '\n'
    lines.append('    }')
    if idx != len(data['countries']) - 1:
        lines.append(',\n')
    else:
        lines.append('\n')
lines.append('  ]\n')
lines.append('}\n')
path.write_text(''.join(lines))
print('Rewrote AVG_SLICE_COST.json with exact decimals')
