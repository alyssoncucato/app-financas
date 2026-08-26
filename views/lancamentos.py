import streamlit as st
import pandas as pd

def render(user, conn_fin, c_fin, todas_categorias):
    st.subheader("Todos os Registros")
    df_all = pd.read_sql_query("SELECT id, data, descricao, valor, categoria, status_fatura, origem FROM transacoes WHERE usuario = ? ORDER BY data DESC", conn_fin, params=(user,))
    if not df_all.empty:
        df_ed = st.data_editor(df_all, column_config={"id": None, "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)}, hide_index=True, width="stretch")
        if st.button("💾 Salvar Edições", type="primary"):
            for _, r in df_ed.iterrows():
                c_fin.execute("UPDATE transacoes SET data=?, descricao=?, valor=?, categoria=?, status_fatura=? WHERE id=? AND usuario=?", 
                              (r['data'], r['descricao'], r['valor'], r['categoria'], r['status_fatura'], r['id'], user))
                if r['descricao'] and r['categoria'] != "Ignorar":
                    c_fin.execute("INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", (user, str(r['descricao']).strip(), r['categoria']))
            conn_fin.commit()
            st.success("Salvo!")
            st.rerun()
    else:
        st.info("Nenhum lançamento.")