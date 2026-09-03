import os
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Lê a URL do banco dos segredos do Streamlit
DATABASE_URL = st.secrets.get("DATABASE_URL", "")

if not DATABASE_URL:
    st.error("Erro crítico: A variável DATABASE_URL não foi encontrada nos Secrets do Streamlit.")

# Ajusta a URL para usar a porta de transação do Supabase (6579) se estiver usando o pooler da porta 5432
# Isso evita o erro de "max clients reached"
if "pooler.supabase.com" in DATABASE_URL and ":5432" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(":5432", ":6579")

# Engine configurada com pool_pre_ping e limite de conexões para não estourar o Supabase
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, 
    pool_size=3, 
    max_overflow=2,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Atalhos de conexão rápida compatíveis com o restante do app
conn_fin = engine
c_fin = engine

conn_proj = engine
c_proj = engine

def inicializar_bancos():
    """Cria as tabelas essenciais no Supabase caso elas ainda nao existam."""
    try:
        with engine.connect() as connection:
            with connection.begin():
                # Tabela de Usuários
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        senha TEXT NOT NULL,
                        email TEXT,
                        foto TEXT
                    );
                """))
                
                # Tabela de Transações (Extratos e Faturas)
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS transacoes (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        data TEXT NOT NULL,
                        descricao TEXT NOT NULL,
                        valor DOUBLE PRECISION NOT NULL,
                        categoria TEXT NOT NULL,
                        status_fatura TEXT,
                        origem TEXT
                    );
                """))

                # Tabela de Regras de Categorias (Aprendizado da IA)
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS regras_categorias (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        termo_chave TEXT NOT NULL,
                        categoria_destino TEXT NOT NULL
                    );
                """))

                # Tabela de Parâmetros Gerais / Configurações do Usuário
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS parametros_gerais (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        chave TEXT NOT NULL,
                        valor TEXT,
                        UNIQUE(usuario, chave)
                    );
                """))

                # Tabela de Abas Personalizadas criadas por IA
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS usuario_abas_ia (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        nome_aba TEXT NOT NULL,
                        icone TEXT,
                        config_colunas TEXT
                    );
                """))

                # Tabela de Dados das Abas Personalizadas
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS dados_abas_ia (
                        id SERIAL PRIMARY KEY,
                        aba_id INT NOT NULL,
                        usuario TEXT NOT NULL,
                        dados_json TEXT
                    );
                """))
    except Exception as e:
        st.error(f"Erro ao inicializar o banco de dados no Supabase: {e}")

def get_param(usuario, chave, padrao=""):
    """Busca um parâmetro salvo do usuário."""
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT valor FROM parametros_gerais WHERE LOWER(usuario) = LOWER(:u) AND chave = :c"),
                {"u": usuario, "c": chave}
            ).fetchone()
            if res and res[0] is not None:
                return res[0]
    except Exception:
        pass
    return padrao

def set_param(usuario, chave, valor):
    """Salva ou atualiza um parâmetro do usuário no Supabase."""
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(
                    text("""
                        INSERT INTO parametros_gerais (usuario, chave, valor) 
                        VALUES (:u, :c, :v)
                        ON CONFLICT (usuario, chave) 
                        DO UPDATE SET valor = :v
                    """),
                    {"u": usuario, "c": chave, "v": str(valor)}
                )
    except Exception as e:
        st.error(f"Erro ao salvar parâmetro: {e}")