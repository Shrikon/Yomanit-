# fonts/

תיקייה זו מכילה פונט TTF עם תמיכה בעברית לשימוש ב-PDF.

## הוראות לפרודקשן

הקובץ `arial.ttf` הוא פונט Windows ואינו ברישיון להפצה.
יש להחליף אותו בפונט חינמי לפני העלאה לפרודקשן:

1. הורד [Noto Sans Hebrew](https://fonts.google.com/noto/specimen/Noto+Sans+Hebrew) מ-Google Fonts
2. שמור את הקובץ כ-`arial.ttf` בתיקייה זו (או עדכן את `FONT_PATH` ב-`welfare_report_analyzer.py`)
3. קבצי `.ttf` לא נכללים ב-git — יש להעתיק ידנית או להוסיף לשלב build ב-Dockerfile
