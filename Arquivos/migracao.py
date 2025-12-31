import sqlite3
import streamlit as st

def corrigir_banco_dados():
    """Corrige os problemas no banco de dados"""
    
    db_file = "financeiro.db"
    
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    try:
        # 1. Verificar e adicionar colunas na tabela transacoes
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN usuario_id INTEGER")
            print("✓ Coluna usuario_id adicionada")
        except:
            print("Coluna usuario_id já existe")
        
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN grupo TEXT DEFAULT 'padrao'")
            print("✓ Coluna grupo adicionada")
        except:
            print("Coluna grupo já existe")
        
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN compartilhado INTEGER DEFAULT 0")
            print("✓ Coluna compartilhado adicionada")
        except:
            print("Coluna compartilhado já existe")
        
        # 2. Atualizar dados existentes
        cur.execute("UPDATE transacoes SET usuario_id = 1 WHERE usuario_id IS NULL")
        cur.execute("UPDATE transacoes SET grupo = 'padrao' WHERE grupo IS NULL")
        cur.execute("UPDATE transacoes SET compartilhado = 1 WHERE compartilhado IS NULL")
        
        conn.commit()
        print("✅ Banco de dados corrigido com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir banco: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    st.set_page_config(page_title="Correção Banco de Dados")
    st.title("🔧 Correção do Banco de Dados")
    
    if st.button("Corrigir Banco de Dados", type="primary"):
        with st.spinner("Corrigindo banco de dados..."):
            sucesso = corrigir_banco_dados()
        if sucesso:
            st.success("✅ Banco de dados corrigido com sucesso!")
            st.info("Agora reinicie o aplicativo principal.")
        else:
            st.error("❌ Erro ao corrigir banco de dados.")