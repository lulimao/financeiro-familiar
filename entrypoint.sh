#!/bin/bash

# Configurar porta
PORT=${PORT:-8080}

echo "========================================"
echo "🚀 INICIANDO FINANCEIRO FAMILIAR"
echo "🌐 Porta: $PORT"
echo "🏥 Healthcheck: / (raiz)"
echo "========================================"

# Iniciar Streamlit
streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --server.headless=true \
    --browser.serverAddress="0.0.0.0" \
    --browser.gatherUsageStats=false