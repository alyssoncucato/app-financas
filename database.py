import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- LEITURA DOS SECRETS DO STREAMLIT CLOUD ---
DB_URL = st.secrets["DB_URL"]

# Engine de conexão otimizada
engine = create_engine(
    DB_URL, 
    connect_args={
        "connect_timeout": 20
    }
)

class Psycopg2CursorProxy:
    """Proxy universal para o cursor que substitui qualquer '?' por '%s'"""
    def __init__(self, real_cursor):
        self._cursor = real_cursor

    def execute(self, query, vars=None):
        if isinstance(query, str):
            query = query.replace("?", "%s")
        return self._cursor.execute(query, vars)

    def executemany(self, query, seq_of_parameters):
        if isinstance(query, str):
            query = query.replace("?", "%s")
        return self._cursor.executemany(query, seq_of_parameters)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class EngineCompatWrapper:
    """Wrapper para a engine para suportar métodos legados e interceptar o cursor do Pandas"""
    def __init__(self, eng):
        self._engine = eng

    def __getattr__(self, name):
        return getattr(self._engine, name)

    def rollback(self):
        pass

    def commit(self):
        pass

    def cursor(self):
        raw_conn = self._engine.raw_connection()
        real_cur = raw_conn.cursor()
        return Psycopg2CursorProxy(real_cur)

conn_fin = EngineCompatWrapper(engine)
conn_proj = EngineCompatWrapper(engine)

class CursorAdapter:
    def execute(self, query, params=None):
        try:
            with engine.connect() as conn:
                with conn.begin():
                    q_str = str(query).replace("?", "%s")
                    q = text(q_str)
                    
                    if params:
                        result = conn.execute(q, params)
                    else:
                        result = conn.execute(q)
                    
                    try:
                        self.last_rows = result.fetchall()
                    except Exception:
                        self.last_rows = []
        except Exception as e:
            print(f"Erro no execute do banco: {e}")
            self.last_rows = []
        return self

    def fetchone(self):
        return self.last_rows[0] if self.last_rows else None

    def fetchall(self):
        return self.last_rows

c_fin = CursorAdapter()
c_proj = CursorAdapter()

def inicializar_bancos():
    try:
        with engine.connect() as conn:
            with conn.begin():
                # Tabela de Usuários
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE,
                        senha TEXT,
                        email TEXT DEFAULT '',
                        foto TEXT DEFAULT ''
                    )
                '''))
                
                # Tabela de Transações isoladas por usuário[cite: 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS transacoes (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        data TEXT,
                        descricao TEXT,
                        valor DOUBLE PRECISION,
                        categoria TEXT,
                        status_fatura TEXT,
                        origem TEXT DEFAULT 'FATURA_CARTAO'
                    )
                '''))

                # Regras por usuário[cite: 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS regras_categorias (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        termo_chave TEXT,
                        categoria_destino TEXT,
                        UNIQUE(usuario, termo_chave)
                    )
                '''))

                # Parâmetros gerais por usuário[cite: 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS parametros_gerais (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        chave TEXT,
                        valor TEXT,
                        UNIQUE(usuario, chave)
                    )
                '''))

                # Projetos isolados por usuário[cite: 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS projetos_lista (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        nome_projeto TEXT,
                        UNIQUE(usuario, nome_projeto)
                    )
                '''))

                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS projetos_itens (
                        id SERIAL PRIMARY KEY,
                        projeto_id INTEGER REFERENCES projetos_lista(id) ON DELETE CASCADE,
                        item TEXT,
                        valor DOUBLE PRECISION,
                        status TEXT
                    )
                '''))

                # Dívida fixa
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS controle_divida (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        ano INTEGER,
                        mes TEXT,
                        valor DOUBLE PRECISION,
                        destino TEXT,
                        gasto TEXT,
                        descricao TEXT,
                        valor_total DOUBLE PRECISION,
                        val_p1 DOUBLE PRECISION,
                        val_p2 DOUBLE PRECISION,
                        iva DOUBLE PRECISION
                    )
                '''))

                # Casa despesas
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS casa_despesas (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        ano INTEGER,
                        mes TEXT,
                        col1 DOUBLE PRECISION,
                        col2 DOUBLE PRECISION,
                        col3 DOUBLE PRECISION,
                        col4 DOUBLE PRECISION,
                        val_p1 DOUBLE PRECISION,
                        val_p2 DOUBLE PRECISION
                    )
                '''))

                # Extra casa
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS extra_casa (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        item TEXT,
                        val_p1 DOUBLE PRECISION,
                        val_p2 DOUBLE PRECISION
                    )
                '''))

                # Abas Dinâmicas criadas por IA por usuário[cite: 5, 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS usuario_abas_ia (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        nome_aba TEXT,
                        icone TEXT,
                        config_colunas TEXT
                    )
                '''))

                # Dados genéricos para as abas criadas por IA[cite: 5, 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS dados_abas_ia (
                        id SERIAL PRIMARY KEY,
                        aba_id INTEGER REFERENCES usuario_abas_ia(id) ON DELETE CASCADE,
                        usuario TEXT,
                        dados_json TEXT
                    )
                '''))

                # Tabela de Metas de Economia[cite: 8]
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS metas_economia (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        nome_meta TEXT,
                        valor_alvo DOUBLE PRECISION,
                        valor_atual DOUBLE PRECISION
                    )
                '''))
    except Exception as e:
        print(f"Aviso de inicializacao: {e}")

def get_param(user, chave, padrao):
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT valor FROM parametros_gerais WHERE usuario = :u AND chave = :c"),
                {"u": user, "c": chave}
            ).fetchone()
            return res[0] if res else padrao
    except Exception:
        return padrao

def set_param(user, chave, valor):
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    text("""
                        INSERT INTO parametros_gerais (usuario, chave, valor) 
                        VALUES (:u, :c, :v)
                        ON CONFLICT (usuario, chave) 
                        DO UPDATE SET valor = EXCLUDED.valor
                    """),
                    {"u": user, "c": chave, "v": str(valor)}
                )
    except Exception:
        pass