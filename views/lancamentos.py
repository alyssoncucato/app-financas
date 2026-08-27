import streamlit as st
import pandas as pd

def render(user, conn_fin, c_fin, todas_categorias):
    st.subheader("📋 Lançamentos e Edição")

    # Criamos sub-abas para separar visualmente Conta Corrente e Cartão de Crédito
    tab_cc, tab_cartao, tab_todos = st.tabs(["🏦 Conta Corrente / Pix", "💳 Cartão de Crédito", "📁 Todos os Registros"])

    # --- ABA 1: CONTA CORRENTE ---
    with tab_cc:
        st.markdown("### Lançamentos da Conta Corrente")
        df_cc = pd.read_sql_query("SELECT id, data, descricao, valor, categoria, status_fatura, origem FROM transacoes WHERE usuario = ? AND origem = 'EXTRATO_CONTA' ORDER BY data DESC", conn_fin, params=(user,))
        
        if not df_cc.empty:
            df_ed_cc = st.data_editor(df_cc, column_config={"id": None, "origem": None, "status_fatura": None, "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)}, hide_index=True, width="stretch", key="editor_cc")
            if st.button("💾 Salvar Edições (Conta Corrente)", type="primary", key="btn_cc"):
                ids_atuais_cc = set(df_cc['id'].tolist())
                ids_editados_cc = set(df_ed_cc['id'].tolist()) if not df_ed_cc.empty else set()
                ids_para_deletar = ids_atuais_cc - ids_editados_cc

                # Deleta do banco usando parâmetros nomeados seguros para o Supabase
                for del_id in ids_para_deletar:
                    c_fin.execute("DELETE FROM transacoes WHERE id = :id AND usuario = :usuario", {"id": int(del_id), "usuario": user})

                # Atualiza o restante
                for _, r in df_ed_cc.iterrows():
                    c_fin.execute("UPDATE transacoes SET data=?, descricao=?, valor=?, categoria=? WHERE id=? AND usuario=?", 
                                  (r['data'], r['descricao'], r['valor'], r['categoria'], r['id'], user))
                    if r['descricao'] and r['categoria'] != "Ignorar":
                        c_fin.execute("INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", (user, str(r['descricao']).strip(), r['categoria']))
                
                st.success("Alterações salvas com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum lançamento de extrato bancário encontrado.")

    # --- ABA 2: CARTÃO DE CRÉDITO ---
    with tab_cartao:
        st.markdown("### Lançamentos do Cartão de Crédito")
        df_cartao = pd.read_sql_query("SELECT id, data, descricao, valor, categoria, status_fatura, origem FROM transacoes WHERE usuario = ? AND origem = 'FATURA_CARTAO' ORDER BY data DESC", conn_fin, params=(user,))
        
        if not df_cartao.empty:
            df_ed_cartao = st.data_editor(df_cartao, column_config={"id": None, "origem": None, "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)}, hide_index=True, width="stretch", key="editor_cartao")
            if st.button("💾 Salvar Edições (Cartão)", type="primary", key="btn_cartao"):
                ids_atuais_cartao = set(df_cartao['id'].tolist())
                ids_editados_cartao = set(df_ed_cartao['id'].tolist()) if not df_ed_cartao.empty else set()
                ids_para_deletar = ids_atuais_cartao - ids_editados_cartao

                # Deleta do banco usando parâmetros nomeados seguros para o Supabase
                for del_id in ids_para_deletar:
                    c_fin.execute("DELETE FROM transacoes WHERE id = :id AND usuario = :usuario", {"id": int(del_id), "usuario": user})

                # Atualiza o restante
                for _, r in df_ed_cartao.iterrows():
                    c_fin.execute("UPDATE transacoes SET data=?, descricao=?, valor=?, categoria=?, status_fatura=? WHERE id=? AND usuario=?", 
                                  (r['data'], r['descricao'], r['valor'], r['categoria'], r['status_fatura'], r['id'], user))
                    if r['descricao'] and r['categoria'] != "Ignorar":
                        c_fin.execute("INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", (user, str(r['descricao']).strip(), r['categoria']))
                
                st.success("Alterações salvas com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum lançamento de fatura de cartão encontrado.")

    # --- ABA 3: TODOS OS REGISTROS (VISÃO GERAL) ---
    with tab_todos:
        st.markdown("### Visão Completa Consolidada")
        df_all = pd.read_sql_query("SELECT id, data, descricao, valor, categoria, status_fatura, origem FROM transacoes WHERE usuario = ? ORDER BY data DESC", conn_fin, params=(user,))
        
        if not df_all.empty:
            df_ed = st.data_editor(df_all, column_config={"id": None, "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)}, hide_index=True, width="stretch", key="editor_todos")
            if st.button("💾 Salvar Edições (Todos)", type="primary", key="btn_todos"):
                ids_atuais_all = set(df_all['id'].tolist())
                ids_editados_all = set(df_ed['id'].tolist()) if not df_ed.empty else set()
                ids_para_deletar = ids_atuais_all - ids_editados_all

                # Deleta do banco usando parâmetros nomeados seguros para o Supabase
                for del_id in ids_para_deletar:
                    c_fin.execute("DELETE FROM transacoes WHERE id = :id AND usuario = :usuario", {"id": int(del_id), "usuario": user})

                # Atualiza o restante
                for _, r in df_ed.iterrows():
                    c_fin.execute("UPDATE transacoes SET data=?, descricao=?, valor=?, categoria=?, status_fatura=? WHERE id=? AND usuario=?", 
                                  (r['data'], r['descricao'], r['valor'], r['categoria'], r['status_fatura'], r['id'], user))
                    if r['descricao'] and r['categoria'] != "Ignorar":
                        c_fin.execute("INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", (user, str(r['descricao']).strip(), r['categoria']))
                
                st.success("Salvo!")
                st.rerun()
        else:
            st.info("Nenhum lançamento cadastrado.")