FROM python:3.11-slim

WORKDIR /app

# 1. Instalar dependências do sistema (essencial para psycopg2/PostgreSQL)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Copiar apenas requirements para cache otimizado
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 4. REMOVA as linhas ENV STREAMLIT_SERVER_PORT antigas
# Vamos usar apenas a porta que o Railway injeta sem forçar nomes fixos

COPY . .
CMD streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true