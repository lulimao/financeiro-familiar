FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro para cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código
COPY . .

# Criar diretório para dados
RUN mkdir -p /app/data

# Expor porta
EXPOSE 10000

# Comando de inicialização
CMD ["streamlit", "run", "app.py", "--server.port=10000", "--server.address=0.0.0.0"]