content = open('C:/yomanit/backend/parsers/electricity.py', encoding='utf-8').read()

# Track credits separately
old1 = '''    sum_details = Decimal("0")
    total = Decimal("0")'''
new1 = '''    sum_details = Decimal("0")
    sum_credits = Decimal("0")
    total = Decimal("0")'''

old2 = '''        sum_details += amount'''
new2 = '''        if amount < 0:
            sum_credits += abs(amount)
        sum_details += amount'''

old3 = '''    sum_f  = round(float(sum_details), 2)
    total_f = float(total) if total > 0 else sum_f
    diff   = round(abs(total_f - sum_f), 2)

    if diff > 1.00:
        raise ElectricityParserError(
            f"הקובץ לא מאוזן: שורות={sum_f:,.2f} סה\\"כ={total_f:,.2f} הפרש={diff:,.2f}"
        )'''
new3 = '''    sum_f    = round(float(sum_details), 2)
    credits_f = round(float(sum_credits), 2)
    total_f  = float(total) if total > 0 else abs(sum_f)
    # השוואה: total_f (גרוס) = sum_f (נטו) + credits (זיכויים)
    diff     = round(abs(total_f - (sum_f + credits_f)), 2)

    if diff > 1.00:
        raise ElectricityParserError(
            f"הקובץ לא מאוזן: שורות={sum_f:,.2f} זיכויים={credits_f:,.2f} סה\\"כ={total_f:,.2f} הפרש={diff:,.2f}"
        )'''

found = True
for old, new in [(old1, new1), (old2, new2), (old3, new3)]:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {old[:30]}...")
    else:
        print(f"NOT FOUND: {old[:30]}...")
        found = False

if found:
    open('C:/yomanit/backend/parsers/electricity.py', 'w', encoding='utf-8').write(content)
    print('All done!')
