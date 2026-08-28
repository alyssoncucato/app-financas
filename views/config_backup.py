import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text
from google import genai
import json

def render(user, conn_fin, c_fin, get_param, set_param, api_key):
    st.subheader("⚙️ Configurações e Perfil")

    # --- SEÇÃO DE PERFIL ---
    st.write("#### 👤 Meu Perfil")
    user_data = c_fin.execute(f"SELECT email, senha, foto FROM usuarios WHERE username = '{user}'").fetchone()
    email_atual = user_data[0] if user_data and user_data[0] else ""
    senha_atual = user_data[1] if user_data and user_data[1] else ""
    foto_atual = user_data[2] if user_data and user_data[2] else ""

    col_f1, col_f2 = st.columns([1, 4])
    with col_f1:
        if foto_atual:
            st.image(foto_atual, width=80)
        else:
            st.markdown("📷 *Sem foto*")
    
    with col_f2:
        with st.form("form_perfil"):
            novo_email = st.text_input("E-mail vinculado:", value=email_atual)
            nova_senha = st.text_input("Nova Senha (deixe em branco para manter):", type="password", value="")
            nova_foto_url = st.text_input("Link da Foto de Perfil (URL da imagem):", value=foto_atual)
            
            if st.form_submit_button("💾 Salvar Alterações de Perfil", type="primary"):
                s_final = nova_senha.strip() if nova_senha.strip() else senha_atual
                c_fin.execute(f"UPDATE usuarios SET email = '{novo_email.strip()}', senha = '{s_final}', foto = '{nova_foto_url.strip()}' WHERE username = '{user}'")
                st.success("Perfil atualizado com sucesso!")
                st.rerun()

    st.divider()

    # --- SEÇÃO DE ABAS VISÍVEIS PADRÃO ---
    st.write("#### 🗂️ Gerenciar Abas Visíveis")
    st.caption("Escolha quais módulos extras você deseja exibir no seu menu superior:")

    padrao_ativado = "1" if user == "alysson" else "0"
    
    ativ_divida = st.checkbox("📌 Dívida Fixa", value=get_param(user, "ativ_divida", padrao_ativado) == "1")
    ativ_casa = st.checkbox("❤️ Casa / Financiamento", value=get_param(user, "ativ_casa", padrao_ativado) == "1")
    ativ_extra = st.checkbox("🏠 Extra Casa", value=get_param(user, "ativ_extra", padrao_ativado) == "1")
    ativ_projetos = st.checkbox("🚗 Projetos e Reformas", value=get_param(user, "ativ_projetos", padrao_ativado) == "1")

    if st.button("Salvar Preferências de Abas"):
        set_param(user, "ativ_divida", "1" if ativ_divida else "0")
        set_param(user, "ativ_casa", "1" if ativ_casa else "0")
        set_param(user, "ativ_extra", "1" if ativ_extra else "0")
        set_param(user, "ativ_projetos", "1" if ativ_projetos else "0")
        st.success("Preferências salvas! Atualizando menu...")
        st.rerun()

    st.divider()

    # --- SEÇÃO DE CRIAÇÃO DE ABAS VIA IA ---
    st.write("#### 🤖 Criar Nova Aba Personalizada com Inteligência Artificial")
    st.caption("Descreva o que você quer controlar (ex: 'Quero uma aba para planejar meu casamento com fornecedor, valor e status de pagamento'). A IA criará a aba para você[cite: 5]:")

    descricao_aba_ia = st.text_area("O que você deseja gerenciar nesta aba?", placeholder="Ex: Controle de gastos do meu setup do PC com nome da peça, loja, valor e status...")

    if st.button("✨ Gerar e Criar Aba com IA", type="primary"):
        if not api_key or api_key == "SUA_CHAVE_AQUI":
            st.error("Chave da API do Gemini não configurada.")
        elif not descricao_aba_ia.strip():
            st.warning("Descreva o que deseja para a IA poder criar.")
        else:
            with st.spinner("A IA está estruturando sua nova aba...[cite: 5]"):
                try:
                    client = genai.Client(api_key=api_key)
                    prompt = f"""
                    Analise o pedido do usuário e crie a estrutura de colunas ideal para uma tabela de gerenciamento financeira/pessoal.
                    Pedido: "{descricao_aba_ia}"
                    
                    Retorne EXATAMENTE um JSON válido com o seguinte formato:
                    {{
                        "nome_aba": "Nome curto e direto para a aba",
                        "icone": "Um emoji que combine",
                        "colunas": [
                            {{"nome": "Nome da coluna 1", "tipo": "texto"}},
                            {{"nome": "Nome da coluna 2", "tipo": "numero"}},
                            {{"nome": "Nome da coluna 3", "tipo": "status"}}
                        ]
                    }}
                    O tipo de coluna pode ser apenas: "texto", "numero" ou "status". Retorne APENAS o JSON.
                    """
                    response = client.models.generate_content(model='models/gemini-2.5-flash', contents=prompt)
                    texto_resp = response.text.strip()
                    if texto_resp.startswith("```json"):
                        texto_resp = texto_resp[7:-3].strip()
                    
                    dados_ia = json.loads(texto_resp)
                    
                    with engine.connect() as connection:
                        with connection.begin():
                            connection.execute(
                                text("INSERT INTO usuario_abas_ia (usuario, nome_aba, icone, config_colunas) VALUES (:u, :n, :i, :c)"),
                                {
                                    "u": user,
                                    "n": dados_ia.get("nome_aba", "Nova Aba"),
                                    "i": dados_ia.get("icone", "📁"),
                                    "c": json.dumps(dados_ia.get("colunas", []))
                                }
                            )
                    st.success("Aba criada com sucesso pela IA! Atualizando menu...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gerar aba com IA: {e}")

    try:
        with engine.connect() as conn:
            df_minhas_abas = pd.read_sql_query(
                text("SELECT id, nome_aba, icone FROM usuario_abas_ia WHERE usuario = :u"),
                conn,
                params={"u": user}
            )
    except Exception:
        df_minhas_abas = pd.DataFrame()

    if not df_minhas_abas.empty:
        st.markdown("##### Suas Abas Personalizadas por IA:")
        for _, r in df_minhas_abas.iterrows():
            col_del1, col_del2 = st.columns([4, 1])
            with col_del1:
                st.text(f"{r['icone']} {r['nome_aba']}")
            with col_del2:
                if st.button("🗑️ Excluir", key=f"del_ia_{r['id']}"):
                    try:
                        with engine.connect() as connection:
                            with connection.begin():
                                connection.execute(text("DELETE FROM usuario_abas_ia WHERE id = :id AND usuario = :u"), {"id": int(r['id']), "u": user})
                        st.success("Aba excluída!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    st.divider()
    st.write("#### 💾 Backup dos Dados (Supabase)")
    try:
        df_transacoes = pd.read_sql_query(f"SELECT * FROM transacoes WHERE usuario = '{user}'", conn_fin)
        csv_data = df_transacoes.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Backup de Transações (.csv)", data=csv_data, file_name=f"backup_transacoes_{user}.csv", mime="text/csv", type="secondary")
    except Exception:
        st.info("Ainda não há transações para exportar.")

    st.divider()
    df_regras = pd.read_sql_query(f"SELECT id, termo_chave AS \"Termo\", categoria_destino AS \"Categoria\" FROM regras_categorias WHERE usuario = '{user}'", conn_fin)
    if not df_regras.empty:
        st.dataframe(df_regras, use_container_width=True)