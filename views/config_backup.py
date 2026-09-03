import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text
from google import genai
import json
import time

def render(user, conn_fin, c_fin, get_param, set_param, api_key):
    st.subheader("⚙️ Configurações e Perfil")

    # --- SEÇÃO DE EDITAR PERFIL ---
    st.write("#### 👤 Meu Perfil")
    try:
        with engine.connect() as conn:
            res_user = conn.execute(
                text("SELECT email, senha, foto FROM usuarios WHERE LOWER(username) = LOWER(:u)"),
                {"u": user}
            ).fetchone()
        email_atual = res_user[0] if res_user and res_user[0] else ""
        senha_atual = res_user[1] if res_user and res_user[1] else ""
        foto_atual = res_user[2] if res_user and res_user[2] else ""
    except Exception:
        email_atual, senha_atual, foto_atual = "", "", ""

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
                try:
                    with engine.connect() as connection:
                        with connection.begin():
                            connection.execute(
                                text("UPDATE usuarios SET email = :e, senha = :s, foto = :f WHERE LOWER(username) = LOWER(:u)"),
                                {"e": novo_email.strip(), "s": s_final, "f": nova_foto_url.strip(), "u": user}
                            )
                    st.success("Perfil atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar perfil: {e}")

    st.divider()

    # --- SEÇÃO DE ABAS VISÍVEIS ---
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

    # --- SEÇÃO DE GERENCIAR TODAS AS CATEGORIAS DE DESPESAS ---
    st.write("#### 🏷️ Gerenciar Categorias de Despesas")
    st.caption("Aqui você tem controle total: adicione, renomeie ou exclua qualquer categoria (padrão ou personalizadas).")

    categorias_base_sistema = [
        "Casa", "Alimentação Rua", "Alimentação Casa", "Carro", "Gasolina",
        "Saúde", "Educação", "Lazer", "Investimento", "Dívidas", "Compras", "Não sei"
    ]

    cats_salvas_str = get_param(user, "categorias_personalizadas", "")
    if cats_salvas_str:
        salvas = [c.strip() for c in cats_salvas_str.split(",") if c.strip()]
        lista_atual_cats = sorted(list(set(categorias_base_sistema + salvas)), key=lambda x: (x not in categorias_base_sistema, x))
    else:
        lista_atual_cats = categorias_base_sistema.copy()

    with st.form("form_nova_categoria"):
        st.markdown("##### ➕ Adicionar Nova Categoria")
        nova_cat_input = st.text_input("Nome da Nova Categoria:")
        if st.form_submit_button("Criar Categoria", type="primary"):
            if nova_cat_input.strip():
                nome_novo = nova_cat_input.strip()
                if nome_novo.lower() not in [c.lower() for c in lista_atual_cats]:
                    lista_atual_cats.append(nome_novo)
                    set_param(user, "categorias_personalizadas", ", ".join(lista_atual_cats))
                    st.success(f"Categoria '{nome_novo}' criada com sucesso! Atualizando...")
                    st.rerun()
                else:
                    st.warning("Essa categoria já existe na sua lista.")
            else:
                st.warning("Digite o nome da categoria.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### ✏️ Editar ou Excluir Categorias Existentes")
    st.caption("Modifique os nomes diretamente na tabela abaixo ou apague a linha inteira para excluir a categoria:")

    df_cats = pd.DataFrame({"Categoria": lista_atual_cats})
    
    ed_cats = st.data_editor(
        df_cats,
        column_config={
            "Categoria": st.column_config.TextColumn("Nome da Categoria", width="large", required=True)
        },
        hide_index=True,
        num_rows="dynamic",
        key="editor_todas_categorias"
    )

    if st.button("💾 Salvar Alterações na Lista de Categorias", type="primary"):
        novas_categorias = [str(r['Categoria']).strip() for _, r in ed_cats.iterrows() if pd.notna(r['Categoria']) and str(r['Categoria']).strip()]
        
        novas_unicas = []
        for c in novas_categorias:
            if c not in novas_unicas:
                novas_unicas.append(c)

        set_param(user, "categorias_personalizadas", ", ".join(novas_unicas))
        st.success("Lista de categorias atualizada com sucesso!")
        st.rerun()

    st.divider()

    # --- SEÇÃO DE CRIAÇÃO DE ABAS VIA IA ---
    st.write("#### 🤖 Criar Nova Aba Personalizada com Inteligência Artificial")
    st.caption("Descreva o que você quer controlar. A IA criará a aba para você:")

    descricao_aba_ia = st.text_area("O que você deseja gerenciar nesta aba?", placeholder="Ex: Controle de recebimentos do patrão com mês, tipo, valor e status...")

    if st.button("✨ Gerar e Criar Aba com IA", type="primary"):
        if not api_key or api_key == "SUA_CHAVE_AQUI":
            st.error("Chave da API do Gemini não configurada.")
        elif not descricao_aba_ia.strip():
            st.warning("Descreva o que deseja para a IA poder criar.")
        else:
            with st.spinner("A IA está estruturando sua nova aba..."):
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
                    
                    response = None
                    for tentativa in range(4):
                        try:
                            response = client.models.generate_content(model='models/gemini-3.6-flash', contents=prompt)
                            break
                        except Exception as ex:
                            if ("503" in str(ex) or "UNAVAILABLE" in str(ex)) and tentativa < 3:
                                time.sleep(3)
                                continue
                            raise ex

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
                text("SELECT id, nome_aba, icone FROM usuario_abas_ia WHERE LOWER(usuario) = LOWER(:u)"),
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
                                connection.execute(text("DELETE FROM usuario_abas_ia WHERE id = :id AND LOWER(usuario) = LOWER(:u)"), {"id": int(r['id']), "u": user})
                        st.success("Aba excluída!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    st.divider()
    st.write("#### 💾 Backup dos Dados (Supabase)")
    try:
        df_transacoes = pd.read_sql_query(text("SELECT * FROM transacoes WHERE LOWER(usuario) = LOWER(:u)"), engine, params={"u": user})
        csv_data = df_transacoes.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Backup de Transações (.csv)", data=csv_data, file_name=f"backup_transacoes_{user}.csv", mime="text/csv", type="secondary")
    except Exception:
        st.info("Ainda não há transações para exportar.")

    st.divider()
    try:
        df_regras = pd.read_sql_query(text("SELECT id, termo_chave AS \"Termo\", categoria_destino AS \"Categoria\" FROM regras_categorias WHERE LOWER(usuario) = LOWER(:u)"), engine, params={"u": user})
        if not df_regras.empty:
            st.dataframe(df_regras, use_container_width=True)
    except Exception:
        pass