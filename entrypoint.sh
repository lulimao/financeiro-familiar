#!/bin/bash
echo "🔄 Iniciando Financeiro Familiar no Railway..."

# Definir porta para o Railway
export PORT=${PORT:-8080}

# Remover arquivos de lock do SQLite se existirem
find . -name "*.db-*" -type f -delete 2>/dev/null || true
find . -name "*.db-wal" -type f -delete 2>/dev/null || true

# Iniciar o Streamlit
echo "🚀 Iniciando Streamlit na porta $PORT..."
streamlit run app.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.serverAddress="financeiro-familiar-production.up.railway.app" \
  --browser.gatherUsageStats=false