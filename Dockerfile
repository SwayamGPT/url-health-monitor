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

# CPU-only torch for sentence-transformers; the default wheel pulls in GBs of CUDA libraries.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

# Apply migrations, then start the API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]

# =========================
# Frontend build
# =========================
FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci

COPY frontend/ .

# Vite inlines VITE_* variables at build time, so the API URL must be a build arg.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# =========================
# Frontend Runtime
# =========================

FROM nginx:alpine AS frontend

COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
