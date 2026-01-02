FROM python:3.11-slim

WORKDIR /app

# 1. Instala dependências do sistema necessárias para o psycopg2 e outros
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalação das dependências do Python
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copia o código do seu app
COPY . .

# 4. Configurações do Streamlit para Cloud
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

# O segredo: Usamos o comando sem os colchetes [] para que o Shell
# do Linux possa converter a variável $PORT no número correto.
CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0