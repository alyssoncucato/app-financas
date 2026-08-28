import streamlit as st
import json
from sqlalchemy import text
from database import inicializar_bancos, engine, conn_fin, c_fin, conn_proj, c_proj, get_param, set_param
from views import dashboard, importacao, lancamentos, dividas_casa, projetos, config_backup
import pandas as pd

st.set_page_config(page_title="Minhas Finanças", page_icon="💰", layout="wide")
inicializar_bancos()

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "SUA_CHAVE_AQUI")

CATEGORIAS_DESPESAS = [
    "Casa", "Alimentação Rua", "Alimentação Casa", "Carro", "Gasolina",
    "Saúde", "Educação", "Lazer", "Investimento", "Dívidas", "Compras", "Não sei"
]
TODAS_CATEGORIAS = CATEGORIAS_DESPESAS + ["Ganhos Fixos", "Ganhos Variáveis", "Ignorar"]

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
                            res = connection.execute(text("SELECT senha FROM usuarios WHERE username = :usr"), {"usr": usr_pesquisa}).fetchone()
                            if res and str(res[0]) == str(s_input):
                                st.session_state.usuario_logado = usr_pesquisa
                                st.success("Login efetuado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Usuário ou senha incorretos.")
                    except Exception as err:
                        st.error(f"Erro: {err}")

        with tab_cad:
            with st.form("form_cadastro"):
                c_user = st.text_input("Novo Usuário:")
                c_senha = st.text_input("Nova Senha:", type="password")
                submit_cad = st.form_submit_button("Criar Conta")
                
                if submit_cad:
                    if c_user.strip() and c_senha.strip():
                        novo_usr = c_user.strip().lower()
                        try:
                            with engine.connect() as connection:
                                with connection.begin():
                                    connection.execute(text("INSERT INTO usuarios (username, senha) VALUES (:usr, :pwd)"), {"usr": novo_usr, "pwd": c_senha})
                            st.success("Conta criada com sucesso! Tudo em branco e isolado para você.")
                        except Exception as e:
                            st.error(f"Erro ao criar conta: {e}")
                    else:
                        st.warning("Preencha todos os campos.")
    st.stop()

user = st.session_state.usuario_logado

col_topo1, col_topo2 = st.columns([6, 1])
with col_topo1:
    st.markdown(f"### 👤 Olá, **{user.upper()}**")
with col_topo2:
    if st.button("🚪 Sair / Trocar", type="secondary", use_container_width=True):
        st.session_state.usuario_logado = None
        st.rerun()

st.divider()

# Preferências de abas ativadas padrão
padrao_ativado = "1" if user == "alysson" else "0"
tem_divida = get_param(user, "ativ_divida", padrao_ativado) == "1"
tem_casa = get_param(user, "ativ_casa", padrao_ativado) == "1"
tem_extra = get_param(user, "ativ_extra", padrao_ativado) == "1"
tem_projetos = get_param(user, "ativ_projetos", padrao_ativado) == "1"

# Busca as abas geradas por IA para este usuário
try:
    with engine.connect() as conn:
        df_abas_ia = pd.read_sql_query(
            text("SELECT id, nome_aba, icone, config_colunas FROM usuario_abas_ia WHERE usuario = :u ORDER BY id ASC"),
            conn,
            params={"u": user}
        )
except Exception:
    df_abas_ia = pd.DataFrame()

# Monta o menu superior completo com as fixas e as de IA
nomes_abas = ["📊 Dashboard", "⚡ Importar com IA", "📋 Lançamentos e Edição"]
if tem_divida: nomes_abas.append("📌 Dívida Fixa")
if tem_casa: nomes_abas.append("❤️ Casa / Financiamento")
if tem_extra: nomes_abas.append("🏠 Extra Casa")
if tem_projetos: nomes_abas.append("🚗 Projetos e Reformas")

if not df_abas_ia.empty:
    for _, r in df_abas_ia.iterrows():
        nomes_abas.append(f"{r['icone']} {r['nome_aba']}")

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

# Renderiza as abas customizadas por IA
if not df_abas_ia.empty:
    for _, aba in df_abas_ia.iterrows():
        aba_id = int(aba['id'])
        colunas_config = json.loads(aba['config_colunas'])
        
        with abas_criadas[idx]:
            st.subheader(f"{aba['icone']} {aba['nome_aba']}")
            
            try:
                with engine.connect() as conn:
                    res_db = conn.execute(text("SELECT dados_json FROM dados_abas_ia WHERE aba_id = :aid AND usuario = :u"), {"aid": aba_id, "u": user}).fetchone()
                    dados_atuais = json.loads(res_db[0]) if res_db else []
            except Exception:
                dados_atuais = []

            nomes_colunas_db = [c["nome"] for c in colunas_config]
            column_config_dict = {"id": None}
            
            for c in colunas_config:
                c_nome = c["nome"]
                c_tipo = c.get("tipo", "texto")
                if c_tipo == "numero":
                    column_config_dict[c_nome] = st.column_config.NumberColumn(c_nome, format="R$ %.2f" if "valor" in c_nome.lower() or "preço" in c_nome.lower() else "%.2f")
                elif c_tipo == "status":
                    column_config_dict[c_nome] = st.column_config.SelectboxColumn(c_nome, options=["Não Pago", "Pago", "Pendente", "Concluído"], required=True)
                else:
                    column_config_dict[c_nome] = st.column_config.TextColumn(c_nome, width="large")

            df_base = pd.DataFrame(dados_atuais) if dados_atuais else pd.DataFrame(columns=["id"] + nomes_colunas_db)
            if "id" not in df_base.columns:
                df_base["id"] = None

            ed_dinamico = st.data_editor(
                df_base,
                column_config=column_config_dict,
                hide_index=True,
                width="stretch",
                num_rows="dynamic",
                key=f"editor_ia_aba_{aba_id}"
            )

            if st.button(f"💾 Salvar {aba['nome_aba']}", type="primary", key=f"btn_save_ia_{aba_id}"):
                try:
                    novos_dados = []
                    for _, r in ed_dinamico.iterrows():
                        item_dict = {}
                        for c_nome in nomes_colunas_db:
                            val = r.get(c_nome)
                            item_dict[c_nome] = val if pd.notna(val) else ("" if isinstance(val, str) else 0.0)
                        novos_dados.append(item_dict)

                    json_para_salvar = json.dumps(novos_dados)
                    with engine.connect() as connection:
                        with connection.begin():
                            existe = connection.execute(text("SELECT id FROM dados_abas_ia WHERE aba_id = :aid AND usuario = :u"), {"aid": aba_id, "u": user}).fetchone()
                            if existe:
                                connection.execute(text("UPDATE dados_abas_ia SET dados_json = :dj WHERE aba_id = :aid AND usuario = :u"), {"dj": json_para_salvar, "aid": aba_id, "u": user})
                            else:
                                connection.execute(text("INSERT INTO dados_abas_ia (aba_id, usuario, dados_json) VALUES (:aid, :u, :dj)"), {"aid": aba_id, "u": user, "dj": json_para_salvar})
                    st.success("Salvo com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
        idx += 1

with abas_criadas[idx]: config_backup.render(user, conn_fin, c_fin, get_param, set_param, GEMINI_API_KEY)