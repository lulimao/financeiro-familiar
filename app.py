import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
import json
import plotly.express as px
import plotly.graph_objects as go
import calendar
import hashlib
import re
import os
import traceback
from sqlalchemy import create_engine, text, inspect, MetaData, Table, Column, Integer, String, Float, Date, Boolean, TIMESTAMP
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import urllib.parse as urlparse

# ---------- CONFIGURAÇÃO SQLALCHEMY ----------
Base = declarative_base()

# ---------- DETECTAR AMBIENTE ----------
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') in ['true', 'production'] or 'DATABASE_URL' in os.environ
IS_STREAMLIT_CLOUD = 'STREAMLIT_CLOUD' in os.environ or 'STREAMLIT_SERVER_PORT' in os.environ
IS_LOCAL = not (IS_RAILWAY or IS_STREAMLIT_CLOUD)

print("=" * 60)
print(f"INICIANDO FINANCEIRO FAMILIAR")
print(f"Porta: {os.environ.get('PORT', '8080')}")
print(f"Railway Environment: {'Sim' if IS_RAILWAY else 'Não'}")
print(f"Streamlit Cloud: {'Sim' if IS_STREAMLIT_CLOUD else 'Não'}")
print(f"Database URL: {'Sim' if os.environ.get('DATABASE_URL') else 'Não'}")
print(f"Ambiente: {'Railway' if IS_RAILWAY else 'Streamlit Cloud' if IS_STREAMLIT_CLOUD else 'Local'}")
print("=" * 60)

# ---------- CONFIGURAÇÃO DA PÁGINA ----------
st.set_page_config(page_title="💰 Financeiro Familiar", layout="wide")

# ---------- CONFIGURAR BANCO BASEADO NO AMBIENTE ----------
if IS_RAILWAY:
    print("🟢 Usando PostgreSQL (Railway)")
    
    # CORREÇÃO DA URL (postgres:// -> postgresql://)
    raw_url = os.environ.get('DATABASE_URL')
    if raw_url and raw_url.startswith("postgres://"):
        DATABASE_URL = raw_url.replace("postgres://", "postgresql://", 1)
    else:
        DATABASE_URL = raw_url
else:
    print("🟡 Usando PostgreSQL (Local/Streamlit Cloud)")
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/financeiro"

# ---------- DEFINIR ARQUIVOS ----------
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
DB_FILE = BASE_DIR / "financeiro.db"
EXCEL_APOIO = BASE_DIR / "planilha_apoio.xlsx"
APOIO_SHEET = "Planilha apoio"

# ---------- CRIAR ENGINE SQLALCHEMY ----------
def create_sqlalchemy_engine():
    """Cria engine SQLAlchemy com configuração apropriada"""
    try:
        if DATABASE_URL:
            engine = create_engine(
                DATABASE_URL,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False
            )
            print("✅ Engine SQLAlchemy criado")
            return engine
        else:
            print("❌ DATABASE_URL não configurada")
            return None
    except Exception as e:
        print(f"❌ Erro ao criar engine SQLAlchemy: {e}")
        return None

# Criar engine global
engine = create_sqlalchemy_engine()

# ---------- MODELOS SQLALCHEMY ----------
class Usuario(Base):
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    tipo = Column(String(10), nullable=False, default='COMUM')
    nome = Column(String(100))
    email = Column(String(100))
    ativo = Column(Boolean, default=True)
    grupo = Column(String(50), default='padrao')
    compartilhado = Column(Integer, default=1)
    pode_compartilhar = Column(Integer, default=0)
    data_criacao = Column(TIMESTAMP, default=datetime.utcnow)
    data_ultimo_login = Column(TIMESTAMP)

class Transacao(Base):
    __tablename__ = 'transacoes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data_registro = Column(Date)
    data_pagamento = Column(Date)
    pessoa = Column(String)
    categoria = Column(String)
    tipo = Column(String)
    valor = Column(Float)
    descricao = Column(String)
    recorrente = Column(Integer, default=0)
    dia_fixo = Column(Integer)
    pessoa_responsavel = Column(String, default='Ambos')
    no_cartao = Column(Integer, default=0)
    investimento = Column(Integer, default=0)
    vr = Column(Integer, default=0)
    forma_pagamento = Column(String, default='Dinheiro')
    parcelas = Column(Integer, default=1)
    parcela_atual = Column(Integer, default=1)
    status = Column(String, default='Ativa')
    usuario_id = Column(Integer)
    grupo = Column(String, default='padrao')
    compartilhado = Column(Integer, default=0)

class LogAcesso(Base):
    __tablename__ = 'logs_acesso'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer)
    acao = Column(String(50))
    descricao = Column(String)
    data_hora = Column(TIMESTAMP, default=datetime.utcnow)

# ---------- FUNÇÕES DE BANCO DE DADOS ----------
def init_db():
    """Inicializa o banco de dados e cria tabelas se não existirem"""
    if engine is None:
        print("❌ Engine não disponível para inicializar banco")
        return False
    
    try:
        # Criar todas as tabelas
        Base.metadata.create_all(engine)
        print("✅ Tabelas criadas/verificadas com sucesso")
        
        # Verificar e adicionar colunas faltantes
        with engine.connect() as conn:
            inspector = inspect(engine)
            
            # Verificar colunas da tabela usuarios
            if 'usuarios' in inspector.get_table_names():
                colunas_usuarios = [col['name'] for col in inspector.get_columns('usuarios')]
                
                colunas_necessarias = [
                    ('grupo', 'VARCHAR(50)', "'padrao'"),
                    ('compartilhado', 'INTEGER', '1'),
                    ('pode_compartilhar', 'INTEGER', '0'),
                    ('data_criacao', 'TIMESTAMP', 'CURRENT_TIMESTAMP'),
                    ('data_ultimo_login', 'TIMESTAMP', 'NULL')
                ]
                
                for coluna, tipo, padrao in colunas_necessarias:
                    if coluna not in colunas_usuarios:
                        try:
                            conn.execute(text(f"ALTER TABLE usuarios ADD COLUMN {coluna} {tipo} DEFAULT {padrao}"))
                            print(f"✅ Coluna {coluna} adicionada à tabela usuarios")
                        except Exception as e:
                            print(f"⚠️ Erro ao adicionar coluna {coluna}: {e}")
            
            # Verificar colunas da tabela transacoes
            if 'transacoes' in inspector.get_table_names():
                colunas_transacoes = [col['name'] for col in inspector.get_columns('transacoes')]
                
                colunas_necessarias_transacoes = [
                    ('usuario_id', 'INTEGER', 'NULL'),
                    ('grupo', 'VARCHAR(50)', "'padrao'"),
                    ('compartilhado', 'INTEGER', '0'),
                    ('status', 'VARCHAR(50)', "'Ativa'")
                ]
                
                for coluna, tipo, padrao in colunas_necessarias_transacoes:
                    if coluna not in colunas_transacoes:
                        try:
                            conn.execute(text(f"ALTER TABLE transacoes ADD COLUMN {coluna} {tipo} DEFAULT {padrao}"))
                            print(f"✅ Coluna {coluna} adicionada à tabela transacoes")
                        except Exception as e:
                            print(f"⚠️ Erro ao adicionar coluna {coluna}: {e}")
            
            conn.commit()
        
        return True
    except Exception as e:
        print(f"❌ Erro ao inicializar banco de dados: {e}")
        return False

def get_session():
    """Retorna uma sessão do SQLAlchemy"""
    if engine is None:
        return None
    
    Session = sessionmaker(bind=engine)
    return Session()

# ---------- Inicialização dos arquivos no Cloud ----------
def inicializar_arquivos_cloud():
    """Criar arquivos necessários se não existirem no cloud"""
    print(f"🔄 Inicializando arquivos para ambiente cloud")
    
    # Criar config.json se não existir
    if not CONFIG_FILE.exists():
        config_default = {"dia_fatura": 10}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_default, f, indent=2)
        print(f"✅ config.json criado")
    
    # Criar planilha exemplo se não existir
    if not EXCEL_APOIO.exists():
        try:
            # Listas de exemplo com mesmo tamanho
            categorias_list = ['Alimentação', 'Aluguel', 'Bebidas', 'Estética', 'Cabeleireiro', 'Calçados', 'Combustível', 'Contas', 'Crédito Ca', 'Delivery', 'Educação', 'Emergenciais', 'Entretenimento',
                               'Estacionamento', 'Estudos', 'Fatura', 'Gasolina', 'Imprevistos', 'Hobbies', 'Impostos', 'Internet', 'Investimento', 'Jogos', 'Lazer', 'Luz', 'Mercado', 'Moradia', 'Narguile',
                               'Outros', 'Pessoal', 'Pet', 'Presentes', 'Rendimentos', 'Roupas', 'Salario', 'Saúde', 'Serviços', 'Streaming', 'Supermercado', 'Transporte', 'Viagens']
            formas_list = ['Boleto', 'Crédito', 'Conta', 'Débito', 'Dinheiro', 'Pix', 'Transferência' 'VA/VR']
            
            df_exemplo = pd.DataFrame({
                'Categorias': categorias_list,
                'Formas_Pagamento': formas_list
            })
            df_exemplo.to_excel(EXCEL_APOIO, sheet_name='Planilha apoio', index=False)
            print(f"✅ Planilha exemplo criada")
        except Exception as e:
            print(f"⚠️ Não foi possível criar planilha exemplo: {e}")
    
    print(f"✅ Inicialização de arquivos concluída")

# ---------- Sistema de Autenticação ----------
class SistemaAutenticacao:
    def __init__(self):
        self._verificar_e_atualizar_estrutura_banco()
        self._criar_admin_padrao()
    
    def _verificar_e_atualizar_estrutura_banco(self):
        """Verifica e atualiza a estrutura do banco de dados"""
        init_db()
    
    def _criar_admin_padrao(self):
        """Cria usuário administrador padrão se não existir"""
        session = get_session()
        if session is None:
            print("❌ Não foi possível obter sessão do banco")
            return
        
        try:
            # Verificar se admin já existe
            admin = session.query(Usuario).filter_by(username='admin').first()
            
            if not admin:
                # Senha padrão: admin123
                senha_hash = self._hash_senha("admin123")
                
                novo_admin = Usuario(
                    username='admin',
                    senha_hash=senha_hash,
                    tipo='ADM',
                    nome='Administrador',
                    email='admin@financeiro.com',
                    grupo='admin',
                    compartilhado=1,
                    pode_compartilhar=1
                )
                
                session.add(novo_admin)
                session.commit()
                print("✅ Usuário administrador padrão criado: admin / admin123")
            else:
                # Verificar se o admin tem senha atualizada
                senha_padrao_hash = self._hash_senha("admin123")
                if admin.senha_hash == senha_padrao_hash:
                    print("⚠️ ATENÇÃO: Usuário admin ainda está com senha padrão 'admin123'")
        
        except Exception as e:
            print(f"❌ Erro ao criar admin padrão: {e}")
            session.rollback()
        finally:
            session.close()
    
    def _hash_senha(self, senha):
        """Gera hash da senha usando SHA-256 com salt"""
        salt = "financeiro_familiar_2025"
        return hashlib.sha256((senha + salt).encode()).hexdigest()
    
    def validar_senha(self, senha):
        """Valida força da senha"""
        if len(senha) < 8:
            return False, "A senha deve ter pelo menos 8 caracteres"
        
        if not re.search(r"[A-Z]", senha):
            return False, "A senha deve conter pelo menos uma letra maiúscula"
        
        if not re.search(r"[a-z]", senha):
            return False, "A senha deve conter pelo menos uma letra minúscula"
        
        if not re.search(r"\d", senha):
            return False, "A senha deve conter pelo menos um número"
        
        return True, "Senha válida"
    
    def autenticar(self, username, senha):
        """Autentica usuário e retorna dados se válido"""
        session = get_session()
        if session is None:
            return False, None, "Erro de conexão com o banco"
        
        try:
            # Buscar usuário
            usuario = session.query(Usuario).filter(
                Usuario.username == username,
                Usuario.ativo == True
            ).first()
            
            if not usuario:
                return False, None, "Usuário não encontrado ou inativo"
            
            # Verificar senha
            senha_hash = self._hash_senha(senha)
            if usuario.senha_hash != senha_hash:
                return False, None, "Senha incorreta"
            
            # Atualizar data do último login
            usuario.data_ultimo_login = datetime.utcnow()
            
            # Log de acesso
            log = LogAcesso(
                usuario_id=usuario.id,
                acao='LOGIN',
                descricao='Login realizado com sucesso'
            )
            session.add(log)
            
            session.commit()
            
            # Dados do usuário
            user_data = {
                'id': usuario.id,
                'username': usuario.username,
                'tipo': usuario.tipo,
                'nome': usuario.nome,
                'grupo': usuario.grupo or 'padrao',
                'compartilhado': usuario.compartilhado or 0
            }
            
            return True, user_data, "Login realizado com sucesso"
            
        except Exception as e:
            return False, None, f"Erro na autenticação: {str(e)}"
        finally:
            session.close()
    
    def alterar_senha(self, username, senha_atual, nova_senha):
        """Altera a senha do usuário"""
        session = get_session()
        if session is None:
            return False, "Erro de conexão com o banco"
        
        try:
            # Verificar senha atual
            usuario = session.query(Usuario).filter_by(username=username).first()
            
            if not usuario:
                return False, "Usuário não encontrado"
            
            senha_hash_atual = self._hash_senha(senha_atual)
            if usuario.senha_hash != senha_hash_atual:
                return False, "Senha atual incorreta"
            
            # Validar nova senha
            valido, mensagem = self.validar_senha(nova_senha)
            if not valido:
                return False, mensagem
            
            # Atualizar senha
            nova_senha_hash = self._hash_senha(nova_senha)
            usuario.senha_hash = nova_senha_hash
            
            # Log
            log = LogAcesso(
                usuario_id=usuario.id,
                acao='ALTERACAO_SENHA',
                descricao='Senha alterada com sucesso'
            )
            session.add(log)
            
            session.commit()
            return True, "Senha alterada com sucesso"
            
        except Exception as e:
            session.rollback()
            return False, f"Erro ao alterar senha: {str(e)}"
        finally:
            session.close()
    
    def listar_usuarios(self):
        """Lista todos os usuários"""
        session = get_session()
        if session is None:
            return [], []
        
        try:
            usuarios = session.query(Usuario).order_by(
                Usuario.tipo.desc(),
                Usuario.username
            ).all()
            
            # Converter para lista de dicionários
            usuarios_list = []
            for usuario in usuarios:
                usuarios_list.append({
                    'id': usuario.id,
                    'username': usuario.username,
                    'tipo': usuario.tipo,
                    'nome': usuario.nome,
                    'email': usuario.email,
                    'ativo': usuario.ativo,
                    'grupo': usuario.grupo,
                    'compartilhado': usuario.compartilhado,
                    'data_criacao': usuario.data_criacao,
                    'data_ultimo_login': usuario.data_ultimo_login
                })
            
            return usuarios_list, list(usuarios_list[0].keys()) if usuarios_list else []
        except Exception as e:
            print(f"Erro ao listar usuários: {e}")
            return [], []
        finally:
            session.close()
    
    def alterar_status_usuario(self, usuario_id, ativo):
        """Ativa/desativa um usuário"""
        session = get_session()
        if session is None:
            return False, "Erro de conexão com o banco"
        
        try:
            usuario = session.query(Usuario).filter_by(id=usuario_id).first()
            
            if not usuario:
                return False, "Usuário não encontrado"
            
            usuario.ativo = bool(ativo)
            
            # Log
            status = "ativado" if ativo else "desativado"
            log = LogAcesso(
                usuario_id=usuario_id,
                acao='ALTERACAO_STATUS',
                descricao=f'Usuário {status}'
            )
            session.add(log)
            
            session.commit()
            return True, f"Usuário {status} com sucesso"
            
        except Exception as e:
            session.rollback()
            return False, f"Erro ao alterar status: {str(e)}"
        finally:
            session.close()
    
    def alterar_tipo_usuario(self, usuario_id, novo_tipo):
        """Altera o tipo de usuário (ADM/COMUM)"""
        session = get_session()
        if session is None:
            return False, "Erro de conexão com o banco"
        
        try:
            usuario = session.query(Usuario).filter_by(id=usuario_id).first()
            
            if not usuario:
                return False, "Usuário não encontrado"
            
            usuario.tipo = novo_tipo
            
            # Log
            log = LogAcesso(
                usuario_id=usuario_id,
                acao='ALTERACAO_TIPO',
                descricao=f'Tipo alterado para {novo_tipo}'
            )
            session.add(log)
            
            session.commit()
            return True, f"Tipo de usuário alterado para {novo_tipo}"
            
        except Exception as e:
            session.rollback()
            return False, f"Erro ao alterar tipo: {str(e)}"
        finally:
            session.close()
    
    def alterar_grupo_usuario(self, usuario_id, novo_grupo, novo_compartilhado):
        """Altera o grupo e status de compartilhamento do usuário"""
        session = get_session()
        if session is None:
            return False, "Erro de conexão com o banco"
        
        try:
            usuario = session.query(Usuario).filter_by(id=usuario_id).first()
            
            if not usuario:
                return False, "Usuário não encontrado"
            
            usuario.grupo = novo_grupo
            usuario.compartilhado = novo_compartilhado
            
            # Log
            compartilhado_str = "compartilhado" if novo_compartilhado else "separado"
            log = LogAcesso(
                usuario_id=usuario_id,
                acao='ALTERACAO_GRUPO',
                descricao=f'Grupo alterado para {novo_grupo} ({compartilhado_str})'
            )
            session.add(log)
            
            session.commit()
            return True, f"Grupo alterado para {novo_grupo} ({compartilhado_str})"
            
        except Exception as e:
            session.rollback()
            return False, f"Erro ao alterar grupo: {str(e)}"
        finally:
            session.close()

    def criar_usuario(self, username, senha, tipo="COMUM", nome=None, email=None, grupo="padrao", compartilhado=0):
        """Cria um novo usuário no sistema"""
        session = get_session()
        if session is None:
            return False, "Erro de conexão com o banco", None
        
        try:
            # Validar força da senha
            valido, mensagem = self.validar_senha(senha)
            if not valido:
                return False, mensagem, None
            
            # Verificar se usuário já existe
            existing_user = session.query(Usuario).filter_by(username=username).first()
            if existing_user:
                return False, "Usuário já existe", None
            
            # Criar hash da senha
            senha_hash = self._hash_senha(senha)
            
            # Inserir novo usuário
            novo_usuario = Usuario(
                username=username,
                senha_hash=senha_hash,
                tipo=tipo,
                nome=nome,
                email=email,
                grupo=grupo,
                compartilhado=compartilhado
            )
            
            session.add(novo_usuario)
            session.flush()  # Para obter o ID
            
            # Log
            log = LogAcesso(
                usuario_id=novo_usuario.id,
                acao='CRIACAO_USUARIO',
                descricao=f'Novo usuário criado: {username}'
            )
            session.add(log)
            
            session.commit()
            return True, "Usuário criado com sucesso", novo_usuario.id
            
        except Exception as e:
            session.rollback()
            return False, f"Erro ao criar usuário: {str(e)}", None
        finally:
            session.close()

# ---------- Inicialização do Sistema ----------
def inicializar_sistema_completo():
    """Inicializa todo o sistema com tratamento de erros"""
    try:
        # Inicializar arquivos cloud se necessário
        if IS_RAILWAY or IS_STREAMLIT_CLOUD:
            inicializar_arquivos_cloud()
        
        # Inicializar sistema de autenticação
        auth_system = SistemaAutenticacao()
        
        print("=" * 50)
        print(f"Sistema Financeiro Familiar")
        print(f"Ambiente: {'Railway' if IS_RAILWAY else 'Streamlit Cloud' if IS_STREAMLIT_CLOUD else 'Local'}")
        print(f"Banco: PostgreSQL (SQLAlchemy)")
        print("=" * 50)
        
        return auth_system
    except Exception as e:
        st.error(f"❌ Erro crítico na inicialização do sistema: {e}")
        return SistemaAutenticacao()

# Inicializar auth
auth = None
try:
    auth = inicializar_sistema_completo()
except Exception as e:
    st.error(f"⚠️ Erro ao inicializar: {e}. Tentando continuar...")
    auth = SistemaAutenticacao()

# ---------- Funções auxiliares ----------
def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"dia_fatura": 10}

def save_config(conf: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)

config = load_config()

# ---------- Datas ----------
def ajustar_para_fatura(data_compra, dia_fatura=10):
    if data_compra.month == 12:
        return date(data_compra.year + 1, 1, dia_fatura)
    else:
        return date(data_compra.year, data_compra.month + 1, dia_fatura)

def inserir_transacao(tipo, data_registro, data_pagamento, descricao, valor, categoria, forma, extra_fields=None, usuario_id=None):
    """Insere uma transação no banco usando SQLAlchemy"""
    session = get_session()
    if session is None:
        return False
    
    try:
        pessoa = "Ambos"
        recorrente = 0
        dia_fixo = None
        pessoa_responsavel = "Ambos"
        no_cartao = 1 if ("cred" in forma.lower() or "cart" in forma.lower()) else 0
        investimento = 0
        vr = 0
        parcelas = 1
        parcela_atual = 1

        if extra_fields:
            recorrente = int(extra_fields.get("recorrente", recorrente))
            dia_fixo = extra_fields.get("dia_fixo", dia_fixo)
            pessoa_responsavel = extra_fields.get("pessoa_responsavel", pessoa_responsavel)
            no_cartao = int(extra_fields.get("no_cartao", no_cartao))
            investimento = int(extra_fields.get("investimento", investimento))
            vr = int(extra_fields.get("vr", vr))
            parcelas = int(extra_fields.get("parcelas", parcelas))
            parcela_atual = int(extra_fields.get("parcela_atual", parcela_atual))
        
        # Buscar informações do usuário
        grupo_usuario = "padrao"
        compartilhado_usuario = 0
        
        if usuario_id:
            usuario = session.query(Usuario).filter_by(id=usuario_id).first()
            if usuario:
                grupo_usuario = usuario.grupo if usuario.grupo else "padrao"
                compartilhado_usuario = usuario.compartilhado if usuario.compartilhado else 0
        
        # Determinar compartilhamento baseado no usuário
        compartilhado = compartilhado_usuario

        nova_transacao = Transacao(
            data_registro=data_registro,
            data_pagamento=data_pagamento,
            pessoa=pessoa,
            categoria=categoria,
            tipo=tipo,
            valor=float(valor),
            descricao=descricao,
            recorrente=recorrente,
            dia_fixo=dia_fixo,
            pessoa_responsavel=pessoa_responsavel,
            no_cartao=no_cartao,
            investimento=investimento,
            vr=vr,
            forma_pagamento=forma,
            parcelas=parcelas,
            parcela_atual=parcela_atual,
            status='Ativa',
            usuario_id=usuario_id,
            grupo=grupo_usuario,
            compartilhado=compartilhado
        )
        
        session.add(nova_transacao)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Erro ao inserir transação: {e}")
        return False
    finally:
        session.close()

def carregar_transacoes(usuario_id=None):
    """Carrega transações usando SQLAlchemy"""
    session = get_session()
    if session is None:
        return pd.DataFrame()
    
    try:
        # Buscar informações do usuário
        usuario_tipo = None
        usuario_grupo = None
        usuario_compartilhado = None
        
        if usuario_id:
            usuario = session.query(Usuario).filter_by(id=usuario_id).first()
            if usuario:
                usuario_tipo = usuario.tipo
                usuario_grupo = usuario.grupo if usuario.grupo else "padrao"
                usuario_compartilhado = usuario.compartilhado
        
        # Construir query base
        query = session.query(
            Transacao,
            Usuario.username.label('usuario_nome')
        ).outerjoin(
            Usuario, Transacao.usuario_id == Usuario.id
        ).filter(
            (Transacao.status != 'Excluída') | (Transacao.status.is_(None))
        )
        
        # Se não for ADM, aplicar filtros
        if usuario_tipo != "ADM":
            if usuario_compartilhado == 1:
                # Usuário com base compartilhada: ver transações do mesmo grupo
                query = query.filter(Transacao.grupo == usuario_grupo)
            else:
                # Usuário com base separada: ver apenas suas transações
                query = query.filter(Transacao.usuario_id == usuario_id)
        
        # Executar query
        resultados = query.order_by(
            Transacao.data_pagamento.desc(),
            Transacao.id.desc()
        ).all()
        
        if resultados:
            # Converter para lista de dicionários
            transacoes_list = []
            for transacao, usuario_nome in resultados:
                trans_dict = {c.name: getattr(transacao, c.name) for c in transacao.__table__.columns}
                trans_dict['usuario_nome'] = usuario_nome
                transacoes_list.append(trans_dict)
            
            df = pd.DataFrame(transacoes_list)
            
            # Converter colunas de data
            date_columns = ['data_registro', 'data_pagamento']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar transações: {e}")
        return pd.DataFrame()
    finally:
        session.close()

def processar_recorrencias_automaticas(usuario_id=None):
    """Processa transações recorrentes automaticamente"""
    session = get_session()
    if session is None:
        return 0
    
    try:
        hoje = date.today()
        novas_transacoes = 0
        
        # Buscar transações recorrentes
        query = session.query(Transacao).filter(
            Transacao.recorrente == 1,
            (Transacao.status != 'Excluída') | (Transacao.status.is_(None))
        )
        
        if usuario_id:
            query = query.filter(Transacao.usuario_id == usuario_id)
        
        transacoes_recorrentes = query.all()
        
        for transacao in transacoes_recorrentes:
            data_pagamento_original = transacao.data_pagamento
            descricao_original = transacao.descricao
            dia_fixo = transacao.dia_fixo
            valor = transacao.valor
            categoria = transacao.categoria
            tipo = transacao.tipo
            forma_pagamento = transacao.forma_pagamento
            no_cartao = transacao.no_cartao
            usuario_id_trans = transacao.usuario_id
            grupo_usuario = transacao.grupo if transacao.grupo else "padrao"
            compartilhado_usuario = transacao.compartilhado
            
            if not dia_fixo:
                dia_fixo = data_pagamento_original.day if data_pagamento_original else 1
            
            try:
                meses_passados = (hoje.year - data_pagamento_original.year) * 12 + (hoje.month - data_pagamento_original.month)
            except:
                meses_passados = 0
            
            for meses in range(1, meses_passados + 1):
                ano = data_pagamento_original.year + (data_pagamento_original.month + meses - 1) // 12
                mes_num = (data_pagamento_original.month + meses - 1) % 12 + 1
                
                try:
                    ultimo_dia_mes = calendar.monthrange(ano, mes_num)[1]
                    dia = min(int(dia_fixo), ultimo_dia_mes)
                    
                    data_pagamento_virtual = date(ano, mes_num, dia)
                    
                    if data_pagamento_virtual <= hoje and data_pagamento_virtual > data_pagamento_original:
                        # Verificar se já existe transação para este mês
                        existe = session.query(Transacao).filter(
                            Transacao.descricao.like(f"%{descricao_original}%"),
                            Transacao.data_pagamento >= date(data_pagamento_virtual.year, data_pagamento_virtual.month, 1),
                            Transacao.data_pagamento <= date(data_pagamento_virtual.year, data_pagamento_virtual.month, ultimo_dia_mes),
                            Transacao.recorrente == 1,
                            Transacao.usuario_id == usuario_id_trans
                        ).first()
                        
                        if not existe:
                            nova_descricao = f"{descricao_original} ({data_pagamento_virtual.strftime('%m/%Y')})"
                            data_registro_nova = hoje
                            
                            if no_cartao:
                                data_pagamento_final = ajustar_para_fatura(data_pagamento_virtual, dia_fatura=config.get("dia_fatura", 10))
                            else:
                                data_pagamento_final = data_pagamento_virtual
                            
                            nova_transacao = Transacao(
                                data_registro=data_registro_nova,
                                data_pagamento=data_pagamento_final,
                                pessoa=transacao.pessoa,
                                categoria=categoria,
                                tipo=tipo,
                                valor=valor,
                                descricao=nova_descricao,
                                recorrente=1,
                                dia_fixo=dia_fixo,
                                pessoa_responsavel=transacao.pessoa_responsavel,
                                no_cartao=no_cartao,
                                investimento=transacao.investimento,
                                vr=transacao.vr,
                                forma_pagamento=forma_pagamento,
                                parcelas=transacao.parcelas,
                                parcela_atual=transacao.parcela_atual,
                                status='Ativa',
                                usuario_id=usuario_id_trans,
                                grupo=grupo_usuario,
                                compartilhado=compartilhado_usuario
                            )
                            
                            session.add(nova_transacao)
                            novas_transacoes += 1
                except Exception as e:
                    st.error(f"Erro ao processar recorrência: {e}")
                    continue
        
        session.commit()
        return novas_transacoes
    except Exception as e:
        session.rollback()
        st.error(f"Erro ao processar recorrências: {e}")
        return 0
    finally:
        session.close()

def excluir_transacao(transacao_id, usuario_id=None):
    """Exclui uma transação (marca como excluída)"""
    session = get_session()
    if session is None:
        return False
    
    try:
        query = session.query(Transacao).filter_by(id=transacao_id)
        
        if usuario_id:
            query = query.filter_by(usuario_id=usuario_id)
        
        transacao = query.first()
        
        if transacao:
            transacao.status = 'Excluída'
            session.commit()
            return True
        else:
            return False
    except Exception as e:
        session.rollback()
        st.error(f"Erro ao excluir transação: {e}")
        return False
    finally:
        session.close()

def editar_transacao(transacao_id, novos_dados, usuario_id=None):
    """Edita uma transação existente"""
    session = get_session()
    if session is None:
        return False, "Erro de conexão com o banco"
    
    try:
        query = session.query(Transacao).filter_by(id=transacao_id)
        
        if usuario_id:
            query = query.filter_by(usuario_id=usuario_id)
        
        transacao = query.first()
        
        if not transacao:
            return False, "Transação não encontrada"
        
        # Atualizar campos
        for campo, valor in novos_dados.items():
            if valor is not None and valor != '':
                setattr(transacao, campo, valor)
        
        session.commit()
        return True, "Transação atualizada com sucesso"
    except Exception as e:
        session.rollback()
        return False, f"Erro ao editar transação: {str(e)}"
    finally:
        session.close()

def ler_categorias_formas():
    """Lê categorias e formas de pagamento do arquivo Excel"""
    categorias_default = ["Alimentação", "Aluguel", "Bebidas", "Estética", "Cabeleireiro", "Calçados", "Combustível", "Contas", "Delivery", "Educação", "Emergenciais", "Entretenimento", "Estacionamento",
                          "Estudos", "Fatura", "Gasolina", "Imprevistos", "Hobbies", "Impostos", "Internet", "Investimento", "Jogos", "Lazer", "Luz", "Mercado", "Moradia", "Narguile", "Outros", "Pessoal",
                          "Pet", "Presentes", "Rendimentos", "Roupas", "Salario", "Saúde", "Serviços", "Streaming", "Supermercado", "Transporte", "Viagens"]
    formas_default = ['Boleto', 'Crédito', 'Conta', 'Débito', 'Dinheiro', 'Pix', 'Transferência' 'VA/VR']
    
    if not EXCEL_APOIO.exists():
        return categorias_default, formas_default
    
    try:
        df = pd.read_excel(EXCEL_APOIO, sheet_name=APOIO_SHEET)
        categorias = df.iloc[:, 0].dropna().astype(str).unique().tolist()
        formas = df.iloc[:, 1].dropna().astype(str).unique().tolist()
        return categorias, formas
    except Exception:
        return categorias_default, formas_default

def validar_transacao(data_registro, data_pagamento, descricao, valor, categoria):
    """Valida os dados de uma transação"""
    erros = []
    
    if not descricao or descricao.strip() == "":
        erros.append("Descrição não pode estar vazia")
    
    if valor <= 0:
        erros.append("Valor deve ser maior que zero")
    
    if not categoria or categoria.strip() == "":
        erros.append("Categoria é obrigatória")
    
    return erros

# ---------- Gerenciamento de Sessão ----------
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.tipo_usuario = None
    st.session_state.usuario_id = None
    st.session_state.usuario_grupo = None
    st.session_state.usuario_compartilhado = None

if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = "login"

if 'form_criar_usuario_submitted' not in st.session_state:
    st.session_state.form_criar_usuario_submitted = False

# ---------- Páginas da Aplicação ----------
def pagina_login():
    st.title("🔐 Login - Financeiro Familiar")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container():
            st.markdown("### Acesse sua conta")
            
            if auth is None:
                st.error("❌ Sistema não inicializado. Recarregue a página.")
                if st.button("🔄 Recarregar"):
                    st.rerun()
                return
            
            with st.expander("ℹ️ Informações de acesso"):
                st.info("""                
                **⚠️ Importante:**
                1. Altere a senha padrão após o primeiro acesso
                2. A senha deve ter pelo menos 8 caracteres
                3. Deve conter letras maiúsculas, minúsculas e números
                """)
            
            username = st.text_input("Usuário", key="login_username", 
                                    placeholder="Digite seu usuário")
            senha = st.text_input("Senha", type="password", key="login_senha",
                                 placeholder="Digite sua senha")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("🚪 Entrar", type="primary", use_container_width=True):
                    if username and senha:
                        with st.spinner("Autenticando..."):
                            sucesso, user_data, mensagem = auth.autenticar(username, senha)
                            
                            if sucesso:
                                st.session_state.autenticado = True
                                st.session_state.usuario = user_data['username']
                                st.session_state.tipo_usuario = user_data['tipo']
                                st.session_state.usuario_id = user_data['id']
                                st.session_state.usuario_grupo = user_data['grupo']
                                st.session_state.usuario_compartilhado = user_data['compartilhado']
                                st.session_state.pagina_atual = "home"
                                st.success(mensagem)
                                st.rerun()
                            else:
                                st.error(f"❌ {mensagem}")
                    else:
                        st.error("⚠️ Preencha usuário e senha")
            
            with col_btn2:
                if st.button("🔑 Alterar Senha", use_container_width=True):
                    st.session_state.pagina_atual = "alterar_senha"
                    st.rerun()
            
            with col_btn3:
                if st.button("📞 Suporte", use_container_width=True):
                    st.info("""
                    **Problemas de acesso?**
                    - Verifique se o usuário está correto
                    - Use a opção 'Alterar Senha'
                    - Contate o administrador do sistema
                    """)
            
            st.markdown("---")

def pagina_alterar_senha():
    st.title("🔑 Alterar Senha")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container():
            st.markdown("### Redefinir Senha")
            
            if auth is None:
                st.error("❌ Sistema não inicializado. Volte para o login.")
                if st.button("↩️ Voltar para Login"):
                    st.session_state.pagina_atual = "login"
                    st.rerun()
                return
            
            username = st.text_input("Usuário", key="alterar_username")
            senha_atual = st.text_input("Senha Atual", type="password", key="alterar_senha_atual")
            nova_senha = st.text_input("Nova Senha", type="password", key="alterar_nova_senha")
            confirmar_senha = st.text_input("Confirmar Nova Senha", type="password", key="alterar_confirmar_senha")
            
            if nova_senha:
                valida, msg = auth.validar_senha(nova_senha)
                if valida:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("💾 Salvar Nova Senha", type="primary", use_container_width=True):
                    if not all([username, senha_atual, nova_senha, confirmar_senha]):
                        st.error("⚠️ Preencha todos os campos")
                    elif nova_senha != confirmar_senha:
                        st.error("⚠️ As senhas não coincidem")
                    else:
                        valida, msg = auth.validar_senha(nova_senha)
                        if not valida:
                            st.error(f"❌ {msg}")
                        else:
                            sucesso, mensagem = auth.alterar_senha(username, senha_atual, nova_senha)
                            if sucesso:
                                st.success(f"✅ {mensagem}")
                                st.info("🔑 Senha alterada com sucesso! Use a nova senha para fazer login.")
                                st.session_state.pagina_atual = "login"
                                st.rerun()
                            else:
                                st.error(f"❌ {mensagem}")
            
            with col_btn2:
                if st.button("↩️ Voltar para Login", use_container_width=True):
                    st.session_state.pagina_atual = "login"
                    st.rerun()

def pagina_principal():
    if auth is None:
        st.error("❌ Sistema não inicializado. Faça login novamente.")
        if st.button("🚪 Voltar para Login"):
            st.session_state.autenticado = False
            st.session_state.usuario = None
            st.session_state.tipo_usuario = None
            st.session_state.usuario_id = None
            st.session_state.pagina_atual = "login"
            st.rerun()
        return
    
    # Barra lateral
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.usuario}")
        st.markdown(f"**Tipo:** {st.session_state.tipo_usuario}")
        st.markdown(f"**Grupo:** {st.session_state.usuario_grupo}")
        st.markdown(f"**Base:** {'Compartilhada' if st.session_state.usuario_compartilhado == 1 else 'Separada'}")
        
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario = None
            st.session_state.tipo_usuario = None
            st.session_state.usuario_id = None
            st.session_state.pagina_atual = "login"
            st.rerun()
        
        st.markdown("---")
        
        # Menu baseado no tipo de usuário
        if st.session_state.tipo_usuario == "ADM":
            menu_opcoes = ["📊 Dashboard", "➕ Novo Registro", "📋 Consultar Finanças", 
                          "🛠️ Gerenciar Transações", "👥 Gerenciar Usuários", "⚙️ Configurações"]
        else:
            menu_opcoes = ["📊 Dashboard", "➕ Novo Registro", "📋 Consultar Finanças", 
                          "🛠️ Gerenciar Transações", "🔧 Minha Conta"]
        
        menu = st.radio("Menu", menu_opcoes)
        
        # Processar recorrências automáticas
        try:
            novas_transacoes = processar_recorrencias_automaticas(st.session_state.usuario_id)
            if novas_transacoes > 0:
                st.success(f"🔄 {novas_transacoes} transações recorrentes criadas!")
        except Exception as e:
            st.error(f"⚠️ Erro ao processar recorrências: {e}")
    
    # Conteúdo principal
    if menu == "📊 Dashboard":
        pagina_dashboard()
    elif menu == "➕ Novo Registro":
        pagina_novo_registro()
    elif menu == "📋 Consultar Finanças":
        pagina_consultar_financas()
    elif menu == "🛠️ Gerenciar Transações":
        pagina_gerenciar_transacoes()
    elif menu == "👥 Gerenciar Usuários" and st.session_state.tipo_usuario == "ADM":
        pagina_gerenciar_usuarios()
    elif menu == "🔧 Minha Conta":
        pagina_minha_conta()
    elif menu == "⚙️ Configurações" and st.session_state.tipo_usuario == "ADM":
        pagina_configuracoes()

def pagina_dashboard():
    st.title("📊 Dashboard Financeiro")
    
    df = carregar_transacoes(st.session_state.usuario_id)
    
    if df.empty:
        st.info("📝 Nenhuma transação cadastrada ainda.")
        return
    
    hoje = datetime.now()
    mes_atual = hoje.month
    ano_atual = hoje.year
    
    df_mes = df.copy()
    if 'data_pagamento' in df_mes.columns and pd.api.types.is_datetime64_any_dtype(df_mes['data_pagamento']):
        df_mes = df_mes[
            (df_mes['data_pagamento'].dt.month == mes_atual) &
            (df_mes['data_pagamento'].dt.year == ano_atual)
        ]
    
    if not df_mes.empty:
        total_receitas = df_mes[df_mes['tipo'] == 'Receita']['valor'].sum()
        total_despesas = df_mes[df_mes['tipo'] == 'Despesa']['valor'].sum()
        saldo_mes = total_receitas - total_despesas
        
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Receitas do Mês", f"R$ {total_receitas:,.2f}")
        col2.metric("💸 Despesas do Mês", f"R$ {total_despesas:,.2f}")
        
        cor_saldo = "normal" if saldo_mes >= 0 else "inverse"
        col3.metric("📊 Saldo do Mês", f"R$ {saldo_mes:,.2f}", delta_color=cor_saldo)
        
        st.subheader("📈 Distribuição de Despesas por Categoria")
        
        df_despesas = df_mes[df_mes['tipo'] == 'Despesa']
        if not df_despesas.empty:
            despesas_categoria = df_despesas.groupby('categoria')['valor'].sum().reset_index()
            if len(despesas_categoria) > 0:
                fig = px.pie(despesas_categoria, names='categoria', values='valor',
                            title='Despesas por Categoria')
                st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🔄 Últimas Transações")
        df_ultimas = df.head(10).copy()
        
        if 'data_pagamento' in df_ultimas.columns and pd.api.types.is_datetime64_any_dtype(df_ultimas['data_pagamento']):
            df_ultimas['data_pagamento'] = df_ultimas['data_pagamento'].dt.strftime('%d/%m/%Y')
        
        if 'data_registro' in df_ultimas.columns and pd.api.types.is_datetime64_any_dtype(df_ultimas['data_registro']):
            df_ultimas['data_registro'] = df_ultimas['data_registro'].dt.strftime('%d/%m/%Y')
        
        colunas_mostrar = []
        for col in ['data_pagamento', 'data_registro', 'descricao', 'categoria', 'tipo', 'valor', 'usuario_nome']:
            if col in df_ultimas.columns:
                colunas_mostrar.append(col)
        
        if colunas_mostrar:
            st.dataframe(df_ultimas[colunas_mostrar], use_container_width=True)
    else:
        st.info("📅 Nenhuma transação registrada para este mês.")

def pagina_novo_registro():
    st.header("➕ Novo Registro")
    
    if 'success_message' not in st.session_state:
        st.session_state.success_message = None
    
    if st.session_state.success_message:
        st.success(st.session_state.success_message)
        st.session_state.success_message = None
    
    col1, col2 = st.columns(2)
    
    with col1:
        tipo = st.radio("Tipo", ["Receita", "Despesa"], index=1, horizontal=True, key="novo_tipo")
        descricao = st.text_input("Descrição", value="", key="novo_descricao")
        valor = st.number_input("Valor (R$)", min_value=0.01, value=0.01, format="%.2f", step=0.01, key="novo_valor")
        categorias, formas = ler_categorias_formas()
        categoria = st.selectbox("Categoria", categorias, key="novo_categoria")
    
    with col2:
        forma = st.selectbox("Forma de pagamento", formas, key="novo_forma")
        no_cartao = forma.lower() in ["crédito", "credito", "cartão", "cartao"]
        
        st.markdown("**Data do Registro**")
        st.info("Data em que você está registrando esta transação no sistema")
        data_registro = st.date_input("Data do Registro", value=date.today(), key="data_registro_novo")
        
        st.markdown("**Data do Pagamento**")
        
        if no_cartao:
            st.info("Data em que a compra foi realizada no cartão")
            data_compra = st.date_input("Data da Compra", value=date.today(), key="data_compra_novo")
            data_pagamento = ajustar_para_fatura(data_compra, dia_fatura=config.get("dia_fatura", 10))
            st.success(f"**Fatura:** {data_pagamento.strftime('%d/%m/%Y')}")
        else:
            st.info("Data em que o pagamento foi/será realizado")
            data_pagamento = st.date_input("Data do Pagamento", value=date.today(), key="data_pagamento_novo")
    
    st.markdown("---")
    st.subheader("🔁 Opções de Pagamento")
    
    opcao_pagamento = st.radio("Selecione o tipo:", 
                              ["À Vista", "Parcelado", "Recorrente"],
                              horizontal=True,
                              index=0,
                              key="novo_opcao")
    
    parcelas = 1
    dia_fixo = None
    
    if opcao_pagamento == "Parcelado":
        parcelas = st.number_input("Número de parcelas", min_value=2, max_value=24, value=2, key="novo_parcelas")
        valor_parcela = valor / parcelas
        st.info(f"💸 **Valor por parcela:** R$ {valor_parcela:,.2f}")
    
    elif opcao_pagamento == "Recorrente":
        st.info("🔄 **Recorrente:** Será cobrada automaticamente todo mês")
        if no_cartao:
            dia_fixo = data_compra.day
        else:
            dia_fixo = data_pagamento.day
        st.info(f"📅 **Dia fixo:** {dia_fixo}º dia do mês")
    
    if st.button("💾 Salvar Registro", type="primary", key="novo_salvar"):
        erros = validar_transacao(data_registro, data_pagamento, descricao, valor, categoria)
        if erros:
            for erro in erros:
                st.error(f"❌ {erro}")
        else:
            try:
                mensagem = ""
                
                if opcao_pagamento == "Parcelado":
                    valor_parcela = valor / parcelas
                    
                    for i in range(parcelas):
                        if no_cartao:
                            ano_compra = data_compra.year + (data_compra.month + i - 1) // 12
                            mes_compra = (data_compra.month + i - 1) % 12 + 1
                            dia_compra = min(data_compra.day, calendar.monthrange(ano_compra, mes_compra)[1])
                            data_compra_parcela = date(ano_compra, mes_compra, dia_compra)
                            data_pagamento_parcela = ajustar_para_fatura(data_compra_parcela, dia_fatura=config.get("dia_fatura", 10))
                        else:
                            ano_pag = data_pagamento.year + (data_pagamento.month + i - 1) // 12
                            mes_pag = (data_pagamento.month + i - 1) % 12 + 1
                            dia_pag = min(data_pagamento.day, calendar.monthrange(ano_pag, mes_pag)[1])
                            data_pagamento_parcela = date(ano_pag, mes_pag, dia_pag)
                        
                        desc_parcela = f"{descricao} ({i+1}/{parcelas})"
                        
                        extra_fields = {
                            "no_cartao": 1 if no_cartao else 0,
                            "parcelas": parcelas,
                            "parcela_atual": i + 1
                        }
                        
                        inserir_transacao(tipo, data_registro, data_pagamento_parcela, 
                                        desc_parcela, valor_parcela, categoria, forma, 
                                        extra_fields, st.session_state.usuario_id)
                    
                    mensagem = f"✅ {parcelas} parcelas de R$ {valor_parcela:,.2f} registradas com sucesso!"
                
                elif opcao_pagamento == "Recorrente":
                    extra_fields = {
                        "recorrente": 1,
                        "dia_fixo": dia_fixo,
                        "no_cartao": 1 if no_cartao else 0
                    }
                    
                    inserir_transacao(tipo, data_registro, data_pagamento, 
                                    descricao, valor, categoria, forma, 
                                    extra_fields, st.session_state.usuario_id)
                    mensagem = "✅ Transação recorrente registrada com sucesso!"
                    st.info("🔄 As recorrências futuras serão criadas automaticamente!")
                
                else:
                    extra_fields = {
                        "no_cartao": 1 if no_cartao else 0
                    }
                    
                    inserir_transacao(tipo, data_registro, data_pagamento, 
                                    descricao, valor, categoria, forma, 
                                    extra_fields, st.session_state.usuario_id)
                    mensagem = f"✅ {tipo} registrada com sucesso!"
                
                st.session_state.success_message = mensagem
                st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {str(e)}")

def pagina_consultar_financas():
    st.header("📊 Consultar Finanças")
    
    df = carregar_transacoes(st.session_state.usuario_id)
    
    if df.empty:
        st.info("📝 Nenhuma transação cadastrada ainda.")
        return
    
    st.subheader("📅 Filtros")
    filtro_tipo = st.radio(
        "Filtrar por:",
        ["Data de Pagamento", "Data de Registro"],
        horizontal=True,
        key="filtro_tipo_consulta"
    )
    
    coluna_filtro = 'data_pagamento' if filtro_tipo == "Data de Pagamento" else 'data_registro'
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        meses = ["Todos"] + [f"{m:02d}" for m in range(1, 13)]
        hoje = datetime.now()
        mes_sel = st.selectbox("Mês", meses, index=hoje.month, key="mes_filtro")
    
    with col2:
        if pd.api.types.is_datetime64_any_dtype(df[coluna_filtro]):
            anos = sorted(df[coluna_filtro].dt.year.dropna().unique(), reverse=True)
        else:
            anos = [hoje.year]
        
        anos_lista = ["Todos"] + [str(int(ano)) for ano in anos]
        ano_sel = st.selectbox("Ano", anos_lista, index=0, key="ano_filtro")
    
    with col3:
        tipo_sel = st.selectbox("Tipo", ["Todos", "Receita", "Despesa"], key="tipo_filtro")
    
    with col4:
        _, formas = ler_categorias_formas()
        forma_sel = st.selectbox("Forma", ["Todas"] + formas, key="forma_filtro")
    
    df_filtrado = df.copy()
    
    if mes_sel != "Todos" and pd.api.types.is_datetime64_any_dtype(df_filtrado[coluna_filtro]):
        df_filtrado = df_filtrado[df_filtrado[coluna_filtro].dt.month == int(mes_sel)]
    
    if ano_sel != "Todos" and pd.api.types.is_datetime64_any_dtype(df_filtrado[coluna_filtro]):
        df_filtrado = df_filtrado[df_filtrado[coluna_filtro].dt.year == int(ano_sel)]
    
    if tipo_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado['tipo'] == tipo_sel]
    
    if forma_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado['forma_pagamento'] == forma_sel]
    
    if df_filtrado.empty:
        st.warning("🔍 Nenhum registro encontrado com os filtros selecionados.")
    else:
        total_receitas = df_filtrado[df_filtrado['tipo'] == 'Receita']['valor'].sum()
        total_despesas = df_filtrado[df_filtrado['tipo'] == 'Despesa']['valor'].sum()
        saldo = total_receitas - total_despesas
        
        col_metrica1, col_metrica2, col_metrica3 = st.columns(3)
        col_metrica1.metric("💰 Receitas", f"R$ {total_receitas:,.2f}")
        col_metrica2.metric("💸 Despesas", f"R$ {total_despesas:,.2f}")
        
        cor_saldo = "normal" if saldo >= 0 else "inverse"
        col_metrica3.metric("📊 Saldo", f"R$ {saldo:,.2f}", delta_color=cor_saldo)
        
        if not df_filtrado.empty:
            col_graf1, col_graf2 = st.columns(2)
            
            with col_graf1:
                graf_categoria = df_filtrado.groupby("categoria")['valor'].sum().reset_index()
                if not graf_categoria.empty and len(graf_categoria) > 0:
                    fig = px.pie(graf_categoria, names='categoria', values='valor', 
                                title='📈 Distribuição por Categoria')
                    st.plotly_chart(fig, use_container_width=True)
            
            with col_graf2:
                graf_forma = df_filtrado.groupby("forma_pagamento")['valor'].sum().reset_index()
                if not graf_forma.empty and len(graf_forma) > 0:
                    fig2 = px.pie(graf_forma, names='forma_pagamento', values='valor',
                                 title='💳 Distribuição por Forma de Pagamento')
                    st.plotly_chart(fig2, use_container_width=True)
        
        st.subheader("📋 Registros Detalhados")
        
        df_display = df_filtrado.copy()
        
        date_columns = ['data_registro', 'data_pagamento']
        for col in date_columns:
            if col in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display[col]):
                df_display[col] = df_display[col].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                )
        
        df_display['valor'] = df_display['valor'].apply(lambda x: f"R$ {x:,.2f}")
        
        colunas = ['id', 'data_registro', 'data_pagamento', 'categoria', 
                  'tipo', 'forma_pagamento', 'valor', 'descricao', 'usuario_nome']
        
        colunas_existentes = [col for col in colunas if col in df_display.columns]
        st.dataframe(df_display[colunas_existentes], use_container_width=True, height=400)

def pagina_gerenciar_transacoes():
    st.header("🛠️ Gerenciar Transações")
    
    if 'editando_id' not in st.session_state:
        st.session_state.editando_id = None
        st.session_state.editando_dados = {}
    
    df = carregar_transacoes(st.session_state.usuario_id)
    
    if 'status' in df.columns:
        df_ativas = df[df['status'] != 'Excluída']
    else:
        df_ativas = df
    
    if df_ativas.empty:
        st.info("📝 Nenhuma transação cadastrada ainda.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            busca_descricao = st.text_input("🔍 Buscar por descrição", key="busca_descricao")
        with col2:
            categorias, _ = ler_categorias_formas()
            categoria_filtro = st.selectbox("Filtrar por categoria", ["Todas"] + categorias, key="filtro_categoria")
        
        df_filtrado = df_ativas.copy()
        if busca_descricao:
            df_filtrado = df_filtrado[df_filtrado['descricao'].str.contains(busca_descricao, case=False, na=False)]
        if categoria_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filtro]
        
        if df_filtrado.empty:
            st.warning("🔍 Nenhuma transação encontrada com os filtros selecionados.")
        else:
            st.subheader(f"📋 Transações Encontradas ({len(df_filtrado)})")
            
            if st.session_state.editando_id is not None:
                transacao_editar = df_filtrado[df_filtrado['id'] == st.session_state.editando_id]
                
                if not transacao_editar.empty:
                    transacao = transacao_editar.iloc[0]
                    st.subheader(f"✏️ Editando: {transacao['descricao']}")
                    
                    if not st.session_state.editando_dados:
                        date_fields = ['data_registro', 'data_pagamento']
                        for field in date_fields:
                            if field in transacao:
                                valor_campo = transacao[field]
                                if isinstance(valor_campo, pd.Timestamp):
                                    st.session_state.editando_dados[field] = valor_campo.date()
                                elif isinstance(valor_campo, datetime):
                                    st.session_state.editando_dados[field] = valor_campo.date()
                                elif isinstance(valor_campo, date):
                                    st.session_state.editando_dados[field] = valor_campo
                                elif isinstance(valor_campo, str):
                                    try:
                                        st.session_state.editando_dados[field] = datetime.strptime(valor_campo, '%Y-%m-%d').date()
                                    except:
                                        st.session_state.editando_dados[field] = date.today()
                                else:
                                    st.session_state.editando_dados[field] = date.today()
                            else:
                                st.session_state.editando_dados[field] = date.today()
                        
                        st.session_state.editando_dados.update({
                            'descricao': transacao['descricao'],
                            'valor': float(transacao['valor']),
                            'categoria': transacao['categoria'],
                            'forma_pagamento': transacao['forma_pagamento'],
                            'tipo': transacao['tipo'],
                            'no_cartao': transacao.get('no_cartao', 0)
                        })
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nova_descricao = st.text_input(
                            "Descrição", 
                            value=st.session_state.editando_dados['descricao'],
                            key=f"edit_desc_{transacao['id']}"
                        )
                        
                        novo_valor = st.number_input(
                            "Valor (R$)", 
                            value=st.session_state.editando_dados['valor'],
                            min_value=0.01, 
                            format="%.2f",
                            key=f"edit_valor_{transacao['id']}"
                        )
                        
                        categorias, formas = ler_categorias_formas()
                        cat_index = 0
                        if st.session_state.editando_dados['categoria'] in categorias:
                            cat_index = categorias.index(st.session_state.editando_dados['categoria'])
                        nova_categoria = st.selectbox(
                            "Categoria", 
                            categorias, 
                            index=cat_index,
                            key=f"edit_cat_{transacao['id']}"
                        )
                    
                    with col2:
                        nova_data_registro = st.date_input(
                            "Data de Registro", 
                            value=st.session_state.editando_dados.get('data_registro', date.today()),
                            key=f"edit_data_reg_{transacao['id']}"
                        )
                        
                        nova_data_pagamento = st.date_input(
                            "Data de Pagamento", 
                            value=st.session_state.editando_dados.get('data_pagamento', date.today()),
                            key=f"edit_data_pag_{transacao['id']}"
                        )
                        
                        forma_index = 0
                        if st.session_state.editando_dados['forma_pagamento'] in formas:
                            forma_index = formas.index(st.session_state.editando_dados['forma_pagamento'])
                        nova_forma = st.selectbox(
                            "Forma de Pagamento", 
                            formas, 
                            index=forma_index,
                            key=f"edit_forma_{transacao['id']}"
                        )
                        
                        tipo_index = 0 if st.session_state.editando_dados['tipo'] == "Receita" else 1
                        novo_tipo = st.radio(
                            "Tipo", 
                            ["Receita", "Despesa"], 
                            index=tipo_index,
                            horizontal=True,
                            key=f"edit_tipo_{transacao['id']}"
                        )
                    
                    col_salvar, col_cancelar, col_espaco = st.columns([1, 1, 2])
                    
                    with col_salvar:
                        if st.button("💾 Salvar Alterações", key=f"save_{transacao['id']}"):
                            erros = []
                            if not nova_descricao or nova_descricao.strip() == "":
                                erros.append("Descrição não pode estar vazia")
                            if novo_valor <= 0:
                                erros.append("Valor deve ser maior que zero")
                            
                            if erros:
                                for erro in erros:
                                    st.error(f"❌ {erro}")
                            else:
                                dados_atualizados = {
                                    'descricao': str(nova_descricao),
                                    'valor': float(novo_valor),
                                    'categoria': str(nova_categoria),
                                    'data_registro': nova_data_registro,
                                    'data_pagamento': nova_data_pagamento,
                                    'forma_pagamento': str(nova_forma),
                                    'tipo': str(novo_tipo)
                                }
                                
                                sucesso, mensagem = editar_transacao(
                                    transacao['id'], 
                                    dados_atualizados, 
                                    st.session_state.usuario_id
                                )
                                if sucesso:
                                    st.success(f"✅ {mensagem}")
                                    st.session_state.editando_id = None
                                    st.session_state.editando_dados = {}
                                    st.rerun()
                                else:
                                    st.error(f"❌ {mensagem}")
                    
                    with col_cancelar:
                        if st.button("❌ Cancelar", key=f"cancel_{transacao['id']}"):
                            st.session_state.editando_id = None
                            st.session_state.editando_dados = {}
                            st.rerun()
                    
                    if st.button("⬅️ Voltar para a lista", key=f"back_{transacao['id']}"):
                        st.session_state.editando_id = None
                        st.session_state.editando_dados = {}
                        st.rerun()
            
            else:
                for idx, transacao in df_filtrado.iterrows():
                    data_registro = transacao.get('data_registro')
                    data_pagamento = transacao.get('data_pagamento')
                    
                    data_registro_str = ''
                    data_pagamento_str = ''
                    
                    if isinstance(data_registro, (date, datetime, pd.Timestamp)):
                        if pd.notna(data_registro):
                            if isinstance(data_registro, pd.Timestamp):
                                data_registro_str = data_registro.strftime('%d/%m/%Y')
                            elif isinstance(data_registro, (date, datetime)):
                                data_registro_str = data_registro.strftime('%d/%m/%Y')
                    elif data_registro is not None:
                        data_registro_str = str(data_registro)
                    
                    if isinstance(data_pagamento, (date, datetime, pd.Timestamp)):
                        if pd.notna(data_pagamento):
                            if isinstance(data_pagamento, pd.Timestamp):
                                data_pagamento_str = data_pagamento.strftime('%d/%m/%Y')
                            elif isinstance(data_pagamento, (date, datetime)):
                                data_pagamento_str = data_pagamento.strftime('%d/%m/%Y')
                    elif data_pagamento is not None:
                        data_pagamento_str = str(data_pagamento)
                    
                    is_credito = transacao.get('no_cartao', 0) == 1 or 'crédito' in str(transacao.get('forma_pagamento', '')).lower()
                    
                    with st.expander(f"{transacao['descricao']} - R$ {transacao['valor']:,.2f} (Pagamento: {data_pagamento_str})"):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.write(f"**ID:** {transacao['id']}")
                            st.write(f"**Registro:** {data_registro_str}")
                            st.write(f"**Pagamento:** {data_pagamento_str}")
                            if is_credito:
                                st.write("💳 **Cartão de Crédito**")
                            st.write(f"**Categoria:** {transacao['categoria']}")
                            st.write(f"**Tipo:** {transacao['tipo']}")
                            st.write(f"**Forma:** {transacao['forma_pagamento']}")
                            if transacao.get('parcelas', 1) > 1:
                                st.write(f"**Parcela:** {transacao.get('parcela_atual', 1)}/{transacao.get('parcelas', 1)}")
                            if transacao.get('recorrente', 0) == 1:
                                st.write("🔄 **Recorrente**")
                            if 'usuario_nome' in transacao:
                                st.write(f"**Usuário:** {transacao['usuario_nome']}")
                        
                        with col2:
                            if st.button("✏️ Editar", key=f"edit_btn_{transacao['id']}_{idx}"):
                                st.session_state.editando_id = transacao['id']
                                st.session_state.editando_dados = {}
                                st.rerun()
                        
                        with col3:
                            if st.button("🗑️ Excluir", key=f"del_btn_{transacao['id']}_{idx}"):
                                if excluir_transacao(transacao['id'], st.session_state.usuario_id):
                                    st.success("✅ Transação marcada como excluída!")
                                    st.rerun()

def pagina_gerenciar_usuarios():
    st.header("👥 Gerenciar Usuários")
    
    if st.session_state.tipo_usuario != "ADM":
        st.error("❌ Acesso restrito a administradores.")
        return
    
    if auth is None:
        st.error("❌ Sistema não inicializado.")
        return
    
    tab1, tab2 = st.tabs(["📋 Lista de Usuários", "➕ Criar Novo Usuário"])
    
    with tab1:
        usuarios, colunas = auth.listar_usuarios()
        
        if not usuarios:
            st.info("📝 Nenhum usuário cadastrado.")
        else:
            st.subheader("📊 Usuários do Sistema")
            
            for idx, usuario in enumerate(usuarios):
                user_key = f"user_{usuario['id']}_{idx}"
                
                with st.expander(f"{usuario['username']} ({usuario['tipo']})"):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**ID:** {usuario['id']}")
                        st.write(f"**Nome:** {usuario['nome'] or 'Não informado'}")
                        st.write(f"**Email:** {usuario['email'] or 'Não informado'}")
                        st.write(f"**Tipo:** {usuario['tipo']}")
                        st.write(f"**Grupo:** {usuario['grupo'] or 'padrao'}")
                        st.write(f"**Base:** {'Compartilhada' if usuario['compartilhado'] == 1 else 'Separada'}")
                        st.write(f"**Status:** {'✅ Ativo' if usuario['ativo'] else '❌ Inativo'}")
                        st.write(f"**Criado em:** {usuario['data_criacao']}")
                        st.write(f"**Último login:** {usuario['data_ultimo_login'] or 'Nunca'}")
                    
                    with col2:
                        if usuario['username'] != st.session_state.usuario:
                            col_status, col_tipo = st.columns(2)
                            
                            with col_status:
                                status_key = f"status_{user_key}"
                                novo_status = st.checkbox(
                                    "Ativo", 
                                    value=bool(usuario['ativo']),
                                    key=status_key
                                )
                                if novo_status != bool(usuario['ativo']):
                                    sucesso, msg = auth.alterar_status_usuario(usuario['id'], novo_status)
                                    if sucesso:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            with col_tipo:
                                tipo_key = f"tipo_{user_key}"
                                novotipo = st.selectbox(
                                    "Tipo",
                                    ["COMUM", "ADM"],
                                    index=0 if usuario['tipo'] == "COMUM" else 1,
                                    key=tipo_key
                                )
                                if novotipo != usuario['tipo']:
                                    sucesso, msg = auth.alterar_tipo_usuario(usuario['id'], novotipo)
                                    if sucesso:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                    
                    with col3:
                        if usuario['username'] != st.session_state.usuario:
                            st.subheader("Grupo/Base")
                            
                            grupo_key = f"grupo_{user_key}"
                            novo_grupo = st.text_input(
                                "Grupo",
                                value=usuario['grupo'] or 'padrao',
                                key=grupo_key
                            )
                            
                            compart_key = f"compart_{user_key}"
                            novo_compartilhado = st.selectbox(
                                "Base de dados",
                                ["Separada", "Compartilhada"],
                                index=0 if usuario['compartilhado'] == 0 else 1,
                                key=compart_key
                            )
                            
                            upd_key = f"upd_grupo_{user_key}"
                            if st.button("Atualizar Grupo", key=upd_key):
                                compartilhado_int = 1 if novo_compartilhado == "Compartilhada" else 0
                                sucesso, msg = auth.alterar_grupo_usuario(
                                    usuario['id'], novo_grupo, compartilhado_int
                                )
                                if sucesso:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        
                        st.write("")
    
    with tab2:
        st.subheader("➕ Criar Novo Usuário")
        
        if st.button("🔄 Limpar formulário"):
            st.session_state.form_criar_usuario_submitted = False
            st.rerun()
        
        with st.form("form_criar_usuario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("Nome de usuário *")
                senha = st.text_input("Senha *", type="password")
                confirmar_senha = st.text_input("Confirmar senha *", type="password")
            
            with col2:
                nome = st.text_input("Nome completo")
                email = st.text_input("Email")
                tipo = st.selectbox("Tipo de usuário", ["COMUM", "ADM"])
                grupo = st.text_input("Grupo", value="padrao", 
                                    help="Usuários no mesmo grupo compartilham dados")
                compartilhado = st.selectbox(
                    "Base de dados", 
                    ["Compartilhada (vê dados do grupo)", "Separada (só vê seus dados)"],
                    index=0
                )
            
            submitted = st.form_submit_button("Criar Usuário", type="primary")
            
            if submitted:
                if not all([username, senha, confirmar_senha]):
                    st.error("Preencha todos os campos obrigatórios (*)")
                elif senha != confirmar_senha:
                    st.error("As senhas não coincidem")
                else:
                    compartilhado_int = 1 if compartilhado.startswith("Compartilhada") else 0
                    
                    sucesso, mensagem, usuario_id = auth.criar_usuario(
                        username, senha, tipo, nome, email, grupo, compartilhado_int
                    )
                    if sucesso:
                        st.success(f"✅ {mensagem} - ID: {usuario_id}")
                        st.session_state.form_criar_usuario_submitted = True
                    else:
                        st.error(f"❌ {mensagem}")
        
        if st.session_state.form_criar_usuario_submitted:
            st.info("Usuário criado com sucesso! O formulário foi limpo.")
            if st.button("➕ Criar outro usuário"):
                st.session_state.form_criar_usuario_submitted = False
                st.rerun()

def pagina_minha_conta():
    st.header("🔧 Minha Conta")
    
    if auth is None:
        st.error("❌ Sistema não inicializado.")
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.info(f"""
        **Informações da conta:**
        - **Usuário:** {st.session_state.usuario}
        - **Tipo:** {st.session_state.tipo_usuario}
        - **ID:** {st.session_state.usuario_id}
        - **Grupo:** {st.session_state.usuario_grupo}
        - **Base:** {'Compartilhada' if st.session_state.usuario_compartilhado == 1 else 'Separada'}
        """)
    
    with col2:
        st.subheader("🔐 Alterar Senha")
        
        with st.form("form_alterar_senha"):
            senha_atual = st.text_input("Senha atual", type="password")
            nova_senha = st.text_input("Nova senha", type="password")
            confirmar_senha = st.text_input("Confirmar nova senha", type="password")
            
            if st.form_submit_button("Alterar Senha", type="primary"):
                if not all([senha_atual, nova_senha, confirmar_senha]):
                    st.error("Preencha todos os campos")
                elif nova_senha != confirmar_senha:
                    st.error("As novas senhas não coincidem")
                else:
                    sucesso, mensagem = auth.alterar_senha(st.session_state.usuario, senha_atual, nova_senha)
                    if sucesso:
                        st.success(mensagem)
                    else:
                        st.error(mensagem)

def pagina_configuracoes():
    st.header("⚙️ Configurações do Sistema")
    
    if st.session_state.tipo_usuario != "ADM":
        st.error("❌ Acesso restrito a administradores.")
        return
    
    tab1, tab2 = st.tabs(["🔄 Configurações Gerais", "📊 Estatísticas"])
    
    with tab1:
        st.subheader("Configurações da Fatura")
        
        dia_fatura = st.number_input("Dia de vencimento da fatura (1-31)", 
                                    min_value=1, max_value=31, 
                                    value=int(config.get("dia_fatura", 10)),
                                    help="Dia que a fatura vence (normalmente dia 10)")
        
        if st.button("Salvar configuração", type="primary"):
            config["dia_fatura"] = int(dia_fatura)
            save_config(config)
            st.success(f"✅ Configuração salva: Fatura dia {dia_fatura}")
        
        st.info(f"""
        **📋 REGRA DO CARTÃO DE CRÉDITO:**
        - **Compras em qualquer dia do mês → Fatura no dia {dia_fatura:02d} do PRÓXIMO mês**
        
        **Exemplos:**
        - Compra em 15/11 → Fatura em {dia_fatura:02d}/12
        - Compra em 20/12 → Fatura em {dia_fatura:02d}/01
        """)
    
    with tab2:
        st.subheader("📊 Estatísticas do Sistema")
        
        session = get_session()
        if session is None:
            st.error("❌ Não foi possível conectar ao banco de dados")
            return
        
        try:
            # Contar usuários
            total_usuarios = session.query(Usuario).count()
            admins = session.query(Usuario).filter_by(tipo='ADM').count()
            comuns = session.query(Usuario).filter_by(tipo='COMUM').count()
            
            # Contar transações
            total_transacoes = session.query(Transacao).count()
            receitas = session.query(Transacao).filter_by(tipo='Receita').count()
            despesas = session.query(Transacao).filter_by(tipo='Despesa').count()
            
            # Contar grupos
            total_grupos = session.query(Usuario.grupo).distinct().count()
            
            # Usuários por tipo de base
            compartilhados = session.query(Usuario).filter_by(compartilhado=1).count()
            separados = session.query(Usuario).filter_by(compartilhado=0).count()
            
        except Exception as e:
            st.error(f"Erro ao obter estatísticas: {e}")
            total_usuarios = admins = comuns = total_transacoes = receitas = despesas = total_grupos = compartilhados = separados = 0
        finally:
            session.close()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("👥 Total de Usuários", total_usuarios)
            st.metric("👑 Administradores", admins)
            st.metric("👤 Usuários Comuns", comuns)
            st.metric("🏷️ Grupos Distintos", total_grupos)
        
        with col2:
            st.metric("💰 Total de Transações", total_transacoes)
            st.metric("📈 Receitas Registradas", receitas)
            st.metric("📉 Despesas Registradas", despesas)
            st.metric("🔄 Bases Compartilhadas", compartilhados)
            st.metric("🔒 Bases Separadas", separados)

# ---------- Roteamento Principal ----------
def main():
    try:
        # Inicializar autenticação
        global auth
        if auth is None:
            auth = inicializar_sistema_completo()
        
        if auth is None:
            st.error("❌ Falha crítica: Sistema de autenticação não inicializado.")
            st.info("Recarregue a página ou verifique os logs para mais detalhes.")
            return
        
        if not st.session_state.autenticado:
            if st.session_state.pagina_atual == "login":
                pagina_login()
            elif st.session_state.pagina_atual == "alterar_senha":
                pagina_alterar_senha()
        else:
            pagina_principal()
            
    except Exception as e:
        st.error(f"❌ Erro crítico no aplicativo: {e}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Tentar Reiniciar"):
                try:
                    st.cache_data.clear()
                    st.session_state.clear()
                except:
                    pass
                st.rerun()
        
        with col2:
            if st.button("📋 Ver Detalhes do Erro"):
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main()