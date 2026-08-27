import streamlit as st
import sqlite3
from sqlalchemy import text
from database import inicializar_bancos, engine, conn_fin, c_fin, conn_proj, c_proj, get_param, set_param
from views import dashboard, importacao, lancamentos, dividas_casa, projetos, config_backup

# 1. Configuração da Página
st.set_page_config(page_title="Minhas Finanças", page_icon="💰", layout="wide")

# Inicializa as tabelas nos bancos de dados separados
inicializar_bancos()

# --- CARREGA A CHAVE DA IA DOS SECRETS ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "SUA_CHAVE_AQUI")

CATEGORIAS_DESPESAS = [
    "Casa", "Alimentação Rua", "Alimentação Casa", "Carro", "Gasolina",
    "Saúde", "Educação", "Lazer", "Investimento", "Dívidas", "Compras", "Não sei"
]
TODAS_CATEGORIAS = CATEGORIAS_DESPESAS + ["Ganhos Fixos", "Ganhos Variáveis", "Ignorar"]

# --- TELA DE LOGIN ---
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

if st.session_state.usuario_logado is None:
    st.markdown("<h2 style='text-align: center;'>🔐 Login - Sistema de Finanças & Projetos</h2>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        tab_login, tab_cad = st.tabs(["Entrar", "Cadastrar Novo Usuário"])
        
        with tab_login:
            with st.form("form_login"):
                u_input = st.text_input("Usuário:")
                s_input = st.text_input("Senha:", type="password")
                submit_login = st.form_submit_button("Entrar no Sistema", type="primary")
                
                if submit_login:
                    usr_pesquisa = u_input.strip().lower()
                    try:
                        with engine.connect() as connection:
                            query = text("SELECT senha FROM usuarios WHERE username = :usr")
                            res = connection.execute(query, {"usr": usr_pesquisa}).fetchone()
                            
                            if res and str(res[0]) == str(s_input):
                                st.session_state.usuario_logado = usr_pesquisa
                                st.success("Login efetuado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Usuário ou senha incorretos.")
                    except Exception as err:
                        st.error(f"Erro de conexão com o banco: {err}")

        with tab_cad:
            with st.form("form_cadastro"):
                c_user = st.text_input("Novo Usuário:")
                c_senha = st.text_input("Nova Senha:", type="password")
                submit_cad = st.form_submit_button("Criar Conta")
                
                if submit_cad:
                    if c_user.strip() and c_senha.strip():
                        try:
                            with engine.connect() as connection:
                                with connection.begin():
                                    query_cad = text("INSERT INTO usuarios (username, senha) VALUES (:usr, :pwd)")
                                    connection.execute(query_cad, {"usr": c_user.strip().lower(), "pwd": c_senha})
                            st.success("Conta criada com sucesso! Vá na aba 'Entrar' para logar.")
                        except Exception as e:
                            st.error(f"Erro ao criar conta (usuário já existe?): {e}")
                    else:
                        st.warning("Preencha todos os campos.")
    st.stop()

# --- SISTEMA PRINCIPAL (APÓS O LOGIN) ---
user = st.session_state.usuario_logado

# Cabeçalho Superior Limpo (Sem barra lateral)
col_topo1, col_topo2 = st.columns([6, 1])
with col_topo1:
    st.markdown(f"### 👤 Olá, **{user.upper()}**")
with col_topo2:
    if st.button("🚪 Sair / Trocar", type="secondary", use_container_width=True):
        st.session_state.usuario_logado = None
        st.rerun()

st.divider()

# Preferências de abas ativadas
padrao_ativado = "1" if user == "alysson" else "0"
tem_divida = get_param(user, "ativ_divida", padrao_ativado) == "1"
tem_casa = get_param(user, "ativ_casa", padrao_ativado) == "1"
tem_extra = get_param(user, "ativ_extra", padrao_ativado) == "1"
tem_projetos = get_param(user, "ativ_projetos", padrao_ativado) == "1"

nomes_abas = ["📊 Dashboard", "⚡ Importar com IA", "📋 Lançamentos e Edição"]
if tem_divida: nomes_abas.append("📌 Dívida Fixa")
if tem_casa: nomes_abas.append("❤️ Casa / Financiamento")
if tem_extra: nomes_abas.append("🏠 Extra Casa")
if tem_projetos: nomes_abas.append("🚗 Projetos e Reformas")
nomes_abas.append("⚙️ Regras e Backup")

abas_criadas = st.tabs(nomes_abas)

idx = 0
with abas_criadas[idx]: dashboard.render(user, conn_fin, CATEGORIAS_DESPESAS); idx += 1
with abas_criadas[idx]: importacao.render(user, conn_fin, c_fin, TODAS_CATEGORIAS, GEMINI_API_KEY); idx += 1
with abas_criadas[idx]: lancamentos.render(user, conn_fin, c_fin, TODAS_CATEGORIAS); idx += 1

if tem_divida:
    with abas_criadas[idx]: dividas_casa.render_divida(user, conn_proj, c_proj, get_param, set_param); idx += 1
if tem_casa:
    with abas_criadas[idx]: dividas_casa.render_casa(user, conn_proj, c_proj, get_param); idx += 1
if tem_extra:
    with abas_criadas[idx]: dividas_casa.render_extra_casa(user, conn_proj, c_proj, get_param); idx += 1
if tem_projetos:
    with abas_criadas[idx]: projetos.render(user, conn_proj, c_proj); idx += 1

with abas_criadas[idx]: config_backup.render(user, conn_fin, c_fin, get_param, set_param)