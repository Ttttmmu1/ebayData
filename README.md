# eBay Live Search (FastAPI + Browse API)

Перехід на **live eBay Browse API** (легально, без парсингу).

## ENV (обов'язково)
- EBAY_ENV=sandbox  (або production)
- EBAY_CLIENT_ID=...        (App ID / Client ID)
- EBAY_CLIENT_SECRET=...    (Cert ID / Client Secret)
- EBAY_MARKETPLACE_ID=EBAY_US

## Запуск локально
```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8001
```

UI: http://127.0.0.1:8001/
API: /api/search?q=iphone&limit=20&page=1
Docs: /docs
Health: /health

## Примітка
Token кешується в пам'яті і автооновлюється за ~60с до завершення.
