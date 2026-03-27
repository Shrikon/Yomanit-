# יומנית – מערכת ניהול פקודות יומן
## Production Backend v0.1

---

## מבנה הפרויקט

```
yomanit/
├── backend/
│   ├── main.py              ← FastAPI app + CORS + DB connection
│   ├── schema.sql           ← PostgreSQL schema מלא (Multi-Tenant)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── routers/
│       ├── auth.py          ← login → token + municipalities
│       ├── municipalities.py← רשימת רשויות + stats
│       ├── upload.py        ← CSV upload + Bezeq parser + index lookup
│       ├── indexes.py       ← CRUD אינדקסים + ייבוא Excel
│       └── journal.py       ← יצירת פקודה + עדכון + יצוא Excel
├── frontend/
│   └── src/
│       └── api.ts           ← כל הקריאות ל-API (TypeScript)
└── docker-compose.yml       ← DB + API + Frontend
```

---

## הרצה מהירה (Docker)

```bash
# 1. שכפל את הפרויקט
git clone https://github.com/your-org/yomanit
cd yomanit

# 2. הרץ הכל
docker-compose up --build

# 3. API זמין ב:
#    http://localhost:8000
#    http://localhost:8000/docs  ← Swagger UI

# 4. Frontend ב:
#    http://localhost:3000
```

---

## הרצה ידנית (פיתוח)

```bash
# PostgreSQL
psql -U postgres -c "CREATE USER yomanit WITH PASSWORD 'secret';"
psql -U postgres -c "CREATE DATABASE yomanit OWNER yomanit;"
psql -U yomanit -d yomanit -f backend/schema.sql

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## API Endpoints

| Method | Path                              | תיאור                        |
|--------|-----------------------------------|------------------------------|
| POST   | /auth/login                       | התחברות → token + רשויות    |
| GET    | /municipalities                   | רשימת רשויות                |
| GET    | /municipalities/{id}/stats        | סטטיסטיקות רשות             |
| POST   | /upload                           | העלאת קובץ CSV/Excel         |
| GET    | /indexes                          | חיפוש אינדקסים               |
| POST   | /indexes                          | הוספת אינדקס בודד            |
| POST   | /indexes/bulk                     | הוספת אינדקסים מרובים        |
| POST   | /indexes/import                   | ייבוא אינדקסים מ-Excel       |
| DELETE | /indexes/{id}                     | מחיקת אינדקס                 |
| GET    | /journal-entries                  | רשימת פקודות לרשות           |
| POST   | /journal-entries                  | יצירת פקודת יומן             |
| GET    | /journal-entries/{id}             | פקודה + שורות                |
| PATCH  | /journal-entries/{id}             | עדכון סטטוס / שורות          |
| GET    | /journal-entries/{id}/export      | יצוא Excel                   |

---

## זרימת עבודה (Bezeq)

```
POST /auth/login
  → token, municipalities[]

POST /upload  (file + municipality_id + template=bezeq)
  → rows[] { phone, amount, has_index, account }

POST /indexes/bulk  (למספרים חסרים)
  → { created: N }

POST /journal-entries  (header + lines[])
  → { id, reference_num }

PATCH /journal-entries/{id}  (status: "approved")
GET   /journal-entries/{id}/export  → Excel file
```

---

## פרסר בזק – עמודות נתמכות

הפרסר מזהה עמודות אוטומטית:
- **טלפון**: phone, טלפון, מספר טלפון, tel, telephone
- **שם**: name, שם, שם מנוי, subscriber  
- **סכום**: amount, סכום, סה"כ, total, חיוב, לתשלום
- **תאריך**: date, תאריך, invoice_date
- **חשבונית**: invoice, חשבונית, מספר חשבונית

---

## השלבים הבאים (Roadmap)

- [ ] JWT authentication מלא
- [ ] פרסר חשמל (לפי מונה)
- [ ] פרסר רווחה (לפי זכאי/סעיף)
- [ ] דוחות: לפי רשות / תקופה / חריגים
- [ ] Email notifications
- [ ] Audit log מלא
