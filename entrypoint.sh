#!/bin/bash

# Configurar porta (Railway usa $PORT)
PORT=${PORT:-8080}

echo "🚀 Iniciando Financeiro Familiar na porta: $PORT"

# Executar Streamlit
exec streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --server.headless=true \
    --browser.serverAddress="0.0.0.0" \
    --browser.gatherUsageStats=false