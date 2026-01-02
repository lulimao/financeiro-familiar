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

# 3. Copiar o resto do código
COPY . .

# 4. Configurações do Streamlit para o Railway
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

# O Railway usará a variável $PORT automaticamente
CMD sh -c "streamlit run app.py --server.port=${PORT:-8080}"