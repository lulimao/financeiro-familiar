#!/usr/bin/env python3
"""
Script para verificar se o sistema está funcionando
"""
import sqlite3
import os

def verificar_sistema():
    print("🔍 Verificando sistema...")
    
    # 1. Verificar arquivos
    arquivos_necessarios = ['app.py', 'requirements.txt', 'runtime.txt']
    for arquivo in arquivos_necessarios:
        if os.path.exists(arquivo):
            print(f"✅ {arquivo} - OK")
        else:
            print(f"❌ {arquivo} - FALTANDO")
    
    # 2. Verificar banco de dados
    try:
        conn = sqlite3.connect('financeiro.db')
        cur = conn.cursor()
        
        # Verificar tabelas
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = cur.fetchall()
        
        print(f"\n📊 Banco de dados:")
        print(f"   - Tabelas encontradas: {len(tabelas)}")
        for tabela in tabelas:
            print(f"     • {tabela[0]}")
        
        # Verificar usuário admin
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE username='admin'")
        admin_count = cur.fetchone()[0]
        
        if admin_count > 0:
            print("✅ Usuário admin - OK")
        else:
            print("⚠️  Usuário admin - NÃO ENCONTRADO")
            print("   Execute: python -c \"from app import auth; auth._criar_admin_padrao()\"")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")
    
    # 3. Verificar dependências
    print("\n📦 Dependências:")
    try:
        import streamlit
        print(f"✅ Streamlit {streamlit.__version__}")
    except:
        print("❌ Streamlit - NÃO INSTALADO")
    
    try:
        import pandas
        print(f"✅ Pandas {pandas.__version__}")
    except:
        print("❌ Pandas - NÃO INSTALADO")
    
    print("\n🎯 Próximos passos:")
    print("1. Execute: streamlit run app.py")
    print("2. Acesse: http://localhost:8501")
    print("3. Login: admin / admin123")

if __name__ == "__main__":
    verificar_sistema()