# ==========================================
# Stage 1: Build Frontend Assets
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Minimal Runtime Container
# ==========================================
FROM python:3.11-slim AS runtime
WORKDIR /app

# Set non-buffered python output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ ./backend/

# Copy built frontend static bundle from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Default environment configurations
ENV PORT=8080
ENV HOST=0.0.0.0
ENV HOST_PROC=/host/proc
ENV HOST_SYS=/host/sys
ENV UPDATE_INTERVAL=1.0
ENV HISTORY_POINTS=900
ENV LOG_LEVEL=info

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn backend.main:app --host ${HOST} --port ${PORT}"]
