FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY risk/ ./risk/
COPY src/ ./src/

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Ejecutar
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
