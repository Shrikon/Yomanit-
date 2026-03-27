content = open('C:/yomanit/backend/parsers/electricity.py', encoding='utf-8').read()
old = '    if val < 0:\n        raise ElectricityRowError(row_num, contract, f"סכום שלילי: {val}")\n'
new = '    # סכום שלילי = זיכוי לגיטימי\n'
if old in content:
    content = content.replace(old, new)
    open('C:/yomanit/backend/parsers/electricity.py', 'w', encoding='utf-8').write(content)
    print('Done! Fixed.')
else:
    print('NOT FOUND - checking line 38...')
    lines = content.splitlines()
    print(repr(lines[37]))
    print(repr(lines[38]))
