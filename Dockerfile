FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    python3-dev \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Copiar entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expor porta
EXPOSE 8080

# Usar entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Garanta que o pip não use cache para evitar erros de espaço
RUN pip install --no-cache-dir -r requirements.txt

# Expor a porta que o Railway fornece (variável dinâmica)
EXPOSE ${PORT}

# Comando de inicialização direto (mais seguro que entrypoint.sh em alguns casos)
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0"]