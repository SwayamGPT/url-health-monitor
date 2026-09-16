# =========================
# Backend
# =========================
FROM python:3.12-slim AS backend

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*  

COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# =========================
# Frontend build
# =========================
FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci

COPY frontend/ .

RUN npm run build

# =========================
# Frontend Runtime
# =========================

FROM nginx:alpine AS frontend

COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
