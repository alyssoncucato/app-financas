import os
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Lê a URL do banco dos segredos do Streamlit
DATABASE_URL = st.secrets.get("DATABASE_URL", "")

if not DATABASE_URL:
    st.error("Erro crítico: A variável DATABASE_URL não foi encontrada nos Secrets do Streamlit.")

# Garante que a URL use a porta 6543 (Transaction Mode) do Supabase
if "pooler.supabase.com" in DATABASE_URL and ":5432" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(":5432", ":6543")

# NullPool faz com que cada requisição abra e feche a conexão instantaneamente, 
# evitando qualquer travamento de limite de pool no Supabase.
engine = create_engine(
    DATABASE_URL, 
    poolclass=NullPool,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

conn_fin = engine
c_fin = engine
conn_proj = engine
c_proj = engine

def inicializar_bancos():
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        senha TEXT NOT NULL,
                        email TEXT,
                        foto TEXT
                    );
                """))
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
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS regras_categorias (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        termo_chave TEXT NOT NULL,
                        categoria_destino TEXT NOT NULL
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS parametros_gerais (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        chave TEXT NOT NULL,
                        valor TEXT,
                        UNIQUE(usuario, chave)
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS usuario_abas_ia (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT NOT NULL,
                        nome_aba TEXT NOT NULL,
                        icone TEXT,
                        config_colunas TEXT
                    );
                """))
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