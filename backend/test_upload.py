import sys
sys.path.insert(0, r'C:\yomanit\backend')

from routers.upload import parse_bezeq_universal
import glob, os

# Find the Tamar file
files = glob.glob(r'C:\Users\sharo\Downloads\TRN*.xlsx')
if not files:
    files = glob.glob(r'C:\Users\sharo\Desktop\TRN*.xlsx')
if not files:
    print("File not found!")
    sys.exit(1)

filepath = files[0]
print("Testing:", filepath)

with open(filepath, 'rb') as f:
    content = f.read()

try:
    result = parse_bezeq_universal(content)
    print("rows:", len(result['rows']))
    print("extra_lines:", len(result['extra_lines']))
    print("invoice_total:", result['invoice_total'])
    print("sum_details:", result['sum_details'])
    print("balance_ok:", result['balance_ok'])
    print("invoice_num:", result['invoice_num'])
    print("date_from:", result['date_from'])
    print("OK!")
except Exception as e:
    import traceback
    traceback.print_exc()
