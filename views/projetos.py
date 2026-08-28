import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text

def render(user, conn_proj, c_proj):
    st.subheader("🚗 Projetos e Reformas")

    # --- 1. CRIAÇÃO DE NOVO PROJETO (Isolado por usuário) ---
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

    # --- 2. SELEÇÃO DE PROJETOS DO USUÁRIO ATUAL ---
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

    projetos_dict = {row['nome_projeto']: row['id'] for _, row in df_projetos.iterrows()}
    nomes_projetos = list(projetos_dict.keys())

    projeto_selecionado = st.selectbox("Selecione o Projeto:", nomes_projetos)
    proj_id = projetos_dict[projeto_selecionado]

    st.divider()
    st.markdown(f"### 🛠️ Gerenciamento do Projeto: **{projeto_selecionado}**")

    # Campo interativo para definir o Custo Previsto do Projeto
    if f"custo_prev_{proj_id}" not in st.session_state:
        st.session_state[f"custo_prev_{proj_id}"] = 0.0

    novo_custo_previsto = st.number_input("Custo Previsto Total do Projeto (R$):", value=st.session_state[f"custo_prev_{proj_id}"], format="%.2f", key=f"input_custo_{proj_id}")
    st.session_state[f"custo_prev_{proj_id}"] = novo_custo_previsto

    # --- 3. ITENS / GASTOS DO PROJETO SELECIONADO ---
    try:
        with engine.connect() as conn:
            df_itens = pd.read_sql_query(
                text("SELECT id, projeto_id, descricao, valor, status FROM projetos_itens WHERE projeto_id = :proj_id"),
                conn,
                params={"proj_id": int(proj_id)}
            )
    except Exception:
        df_itens = pd.DataFrame()

    if df_itens.empty:
        df_edit_base = pd.DataFrame(columns=["id", "projeto_id", "descricao", "valor", "status"])
    else:
        df_itens['status'] = df_itens['status'].apply(lambda x: "Pago" if str(x).strip().capitalize() == "Pago" else "Não Pago")
        df_edit_base = df_itens

    st.markdown("#### Lançamentos e Peças do Projeto")
    ed_itens = st.data_editor(
        df_edit_base,
        column_config={
            "id": None,
            "projeto_id": None,
            "descricao": st.column_config.TextColumn("Descrição da Peça / Serviço", width="large"),
            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "status": st.column_config.SelectboxColumn("Status", options=["Não Pago", "Pago"], required=True)
        },
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=f"editor_projeto_{proj_id}"
    )

    # --- 4. CÁLCULOS E MÉTRICAS ---
    if not ed_itens.empty and 'valor' in ed_itens.columns and 'status' in ed_itens.columns:
        val_gasto = ed_itens[ed_itens['status'].astype(str).str.strip().str.capitalize() == 'Pago']['valor'].sum()
        custo_total_itens = ed_itens['valor'].sum()
    else:
        val_gasto = 0.0
        custo_total_itens = 0.0

    val_a_gastar = novo_custo_previsto - val_gasto

    st.markdown("")
    m1, m2, m3 = st.columns(3)
    m1.metric("🎯 Custo Previsto", f"R$ {novo_custo_previsto:,.2f}")
    m2.metric("🟢 Valor Gasto (Pago)", f"R$ {val_gasto:,.2f}")
    m3.metric("⏳ Valor a Gastar (Saldo)", f"R$ {val_a_gastar:,.2f}", delta=f"Total Itens: R$ {custo_total_itens:,.2f}")
    st.markdown("")

    if st.button("💾 Salvar Alterações do Projeto", type="primary"):
        try:
            with engine.connect() as connection:
                with connection.begin():
                    ids_atuais = [int(r['id']) for _, r in ed_itens.iterrows() if pd.notna(r.get('id'))]
                    
                    if ids_atuais:
                        connection.execute(
                            text("DELETE FROM projetos_itens WHERE projeto_id = :proj_id AND id NOT IN :ids"),
                            {"proj_id": int(proj_id), "ids": tuple(ids_atuais)}
                        )
                    else:
                        connection.execute(
                            text("DELETE FROM projetos_itens WHERE projeto_id = :proj_id"),
                            {"proj_id": int(proj_id)}
                        )

                    for _, r in ed_itens.iterrows():
                        desc = str(r['descricao']) if pd.notna(r['descricao']) else ""
                        val = float(r['valor']) if pd.notna(r['valor']) else 0.0
                        st_val = str(r['status']) if pd.notna(r['status']) else "Não Pago"
                        
                        if pd.notna(r.get('id')):
                            connection.execute(
                                text("UPDATE projetos_itens SET descricao = :desc, valor = :val, status = :status WHERE id = :id"),
                                {"desc": desc, "val": val, "status": st_val, "id": int(r['id'])}
                            )
                        else:
                            if desc.strip() or val > 0:
                                connection.execute(
                                    text("INSERT INTO projetos_itens (projeto_id, descricao, valor, status) VALUES (:proj_id, :desc, :val, :status)"),
                                    {"proj_id": int(proj_id), "desc": desc, "val": val, "status": st_val}
                                )
            st.success("Projeto salvo com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar itens do projeto: {e}")