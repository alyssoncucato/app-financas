import streamlit as st
import pandas as pd

def render(user, conn_proj, c_proj):
    st.subheader("🚗 Projetos e Reformas")
    p_db = pd.read_sql_query("SELECT id, nome_projeto FROM projetos_lista WHERE usuario = ?", conn_proj, params=(user,))
    p_nomes = p_db['nome_projeto'].tolist() if not p_db.empty else []
    
    col1, col2 = st.columns([3, 2])
    with col1: sel_p = st.selectbox("Projeto:", p_nomes if p_nomes else ["Nenhum"])
    with col2:
        novo_p = st.text_input("Novo Projeto:")
        if st.button("Criar Projeto") and novo_p.strip():
            c_proj.execute("INSERT INTO projetos_lista (usuario, nome_projeto) VALUES (?, ?)", (user, novo_p.strip().upper()))
            conn_proj.commit()
            st.rerun()

    if p_nomes and sel_p != "Nenhum":
        pid = p_db[p_db['nome_projeto'] == sel_p].iloc[0]['id']
        df_it = pd.read_sql_query("SELECT id, item, valor, situacao FROM projetos_itens WHERE projeto_id = ?", conn_proj, params=(pid,))
        ed_it = st.data_editor(df_it, column_config={"id": None, "projeto_id": None, "situacao": st.column_config.SelectboxColumn("Situação", options=["PAGO", "A PAGAR", "PAGANDO"])}, hide_index=True, width="stretch")
        if st.button("💾 Salvar Projeto", type="primary"):
            for _, r in ed_it.iterrows():
                if pd.notna(r['id']):
                    if r['item']: c_proj.execute("UPDATE projetos_itens SET item=?, valor=?, situacao=? WHERE id=?", (r['item'], r['valor'], r['situacao'], r['id']))
                    else: c_proj.execute("DELETE FROM projetos_itens WHERE id=?", (r['id'],))
                else:
                    if r['item'] and r['valor'] > 0: c_proj.execute("INSERT INTO projetos_itens (projeto_id, item, valor, situacao) VALUES (?, ?, ?, ?)", (pid, r['item'], r['valor'], r['situacao']))
            conn_proj.commit()
            st.success("Salvo!")
            st.rerun()