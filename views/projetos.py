import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text

def render(user, conn_proj, c_proj):
    st.subheader("🚗 Projetos e Reformas")

    # --- 1. CRIAÇÃO DE NOVO PROJETO ---
    col1, col2 = st.columns([2, 1])
    with col1:
        novo_proj_nome = st.text_input("Novo Projeto:", placeholder="Ex: GOLZERA BOLADO, MOTO...")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_criar = st.button("Criar Projeto", type="primary")

    if btn_criar and novo_proj_nome.strip():
        try:
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(
                        text("INSERT INTO projetos_lista (usuario, nome_projeto) VALUES (:usuario, :nome)"),
                        {"usuario": user, "nome": novo_proj_nome.strip()}
                    )
            st.success(f"Projeto '{novo_proj_nome}' criado com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao criar projeto: {e}")

    st.divider()

    # --- 2. SELEÇÃO DE PROJETOS EXISTENTES ---
    try:
        with engine.connect() as conn:
            df_projetos = pd.read_sql_query(
                text("SELECT id, nome_projeto FROM projetos_lista WHERE usuario = :usuario"),
                conn,
                params={"usuario": user}
            )
    except Exception:
        df_projetos = pd.DataFrame()

    if df_projetos.empty:
        st.info("Nenhum projeto cadastrado ainda. Crie o seu primeiro projeto acima!")
        return

    # Cria um dicionário de nomes para IDs
    projetos_dict = {row['nome_projeto']: row['id'] for _, row in df_projetos.iterrows()}
    nomes_projetos = list(projetos_dict.keys())

    projeto_selecionado = st.selectbox("Selecione o Projeto:", nomes_projetos)
    proj_id = projetos_dict[projeto_selecionado]

    st.divider()
    st.markdown(f"### 🛠️ Gerenciamento do Projeto: **{projeto_selecionado}**")

    # --- 3. ITENS / GASTOS DO PROJETO SELECIONADO ---
    try:
        with engine.connect() as conn:
            df_itens = pd.read_sql_query(
                text("SELECT id, projeto_id, descricao, valor, categoria FROM projetos_itens WHERE usuario = :usuario AND projeto_id = :proj_id"),
                conn,
                params={"usuario": user, "proj_id": int(proj_id)}
            )
    except Exception:
        df_itens = pd.DataFrame()

    # Se não houver itens, cria um dataframe vazio padrão para o editor
    if df_itens.empty:
        df_edit_base = pd.DataFrame(columns=["id", "projeto_id", "descricao", "valor", "categoria"])
    else:
        df_edit_base = df_itens

    st.markdown("#### Lançamentos e Peças do Projeto")
    ed_itens = st.data_editor(
        df_edit_base,
        column_config={
            "id": None,
            "projeto_id": None,
            "descricao": st.column_config.TextColumn("Descrição da Peça / Serviço", width="large"),
            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "categoria": st.column_config.TextColumn("Categoria / Oferecimento")
        },
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=f"editor_projeto_{proj_id}"
    )

    # Exibe o total gasto no projeto em destaque
    total_projeto = ed_itens['valor'].sum() if not ed_itens.empty and 'valor' in ed_itens.columns else 0.0
    st.metric("💰 Custo Total deste Projeto", f"R$ {total_projeto:,.2f}")

    if st.button("💾 Salvar Alterações do Projeto", type="primary"):
        try:
            with engine.connect() as connection:
                with connection.begin():
                    ids_atuais = [int(r['id']) for _, r in ed_itens.iterrows() if pd.notna(r.get('id'))]
                    
                    # Remove itens deletados na tela
                    if ids_atuais:
                        connection.execute(
                            text("DELETE FROM projetos_itens WHERE usuario = :usuario AND projeto_id = :proj_id AND id NOT IN :ids"),
                            {"usuario": user, "proj_id": int(proj_id), "ids": tuple(ids_atuais)}
                        )
                    else:
                        connection.execute(
                            text("DELETE FROM projetos_itens WHERE usuario = :usuario AND projeto_id = :proj_id"),
                            {"usuario": user, "proj_id": int(proj_id)}
                        )

                    # Insere ou atualiza os itens
                    for _, r in ed_itens.iterrows():
                        desc = str(r['descricao']) if pd.notna(r['descricao']) else ""
                        val = float(r['valor']) if pd.notna(r['valor']) else 0.0
                        cat = str(r['categoria']) if pd.notna(r['categoria']) else ""
                        
                        if pd.notna(r.get('id')):
                            connection.execute(
                                text("UPDATE projetos_itens SET descricao = :desc, valor = :val, categoria = :cat WHERE id = :id AND usuario = :usuario"),
                                {"desc": desc, "val": val, "cat": cat, "id": int(r['id']), "usuario": user}
                            )
                        else:
                            if desc.strip() or val > 0:
                                connection.execute(
                                    text("INSERT INTO projetos_itens (usuario, projeto_id, descricao, valor, categoria) VALUES (:usuario, :proj_id, :desc, :val, :cat)"),
                                    {"usuario": user, "proj_id": int(proj_id), "desc": desc, "val": val, "cat": cat}
                                />
            st.success("Projeto salvo com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar itens do projeto:[cite: 1] {e}")