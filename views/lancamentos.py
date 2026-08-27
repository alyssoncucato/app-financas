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
            df_cc["Excluir"] = False
            
            df_ed_cc = st.data_editor(
                df_cc, 
                column_config={
                    "id": None, 
                    "origem": None, 
                    "status_fatura": None, 
                    "Excluir": st.column_config.CheckboxColumn("❌ Excluir?", help="Marque para apagar este lançamento"),
                    "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)
                }, 
                hide_index=True, 
                width="stretch", 
                key="editor_cc"
            )
            
            if st.button("💾 Salvar Edições (Conta Corrente)", type="primary", key="btn_cc"):
                for _, r in df_ed_cc.iterrows():
                    if r["Excluir"]:
                        c_fin.execute("DELETE FROM transacoes WHERE id = ? AND usuario = ?", (int(r['id']), user))
                    else:
                        c_fin.execute(
                            "UPDATE transacoes SET data = ?, descricao = ?, valor = ?, categoria = ? WHERE id = ? AND usuario = ?", 
                            (r['data'], r['descricao'], r['valor'], r['categoria'], int(r['id']), user)
                        )
                        if r['descricao'] and r['categoria'] != "Ignorar":
                            c_fin.execute(
                                "INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", 
                                (user, str(r['descricao']).strip(), r['categoria'])
                            )
                
                st.success("Alterações salvas com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum lançamento de extrato bancário encontrado.")

    # --- ABA 2: CARTÃO DE CRÉDITO ---
    with tab_cartao:
        st.markdown("### Lançamentos do Cartão de Crédito")
        df_cartao = pd.read_sql_query("SELECT id, data, descricao, valor, categoria, status_fatura, origem FROM transacoes WHERE usuario = ? AND origem = 'FATURA_CARTAO' ORDER BY data DESC", conn_fin, params=(user,))
        
        if not df_cartao.empty:
            df_cartao["Excluir"] = False
            
            df_ed_cartao = st.data_editor(
                df_cartao, 
                column_config={
                    "id": None, 
                    "origem": None, 
                    "Excluir": st.column_config.CheckboxColumn("❌ Excluir?", help="Marque para apagar este lançamento"),
                    "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)
                }, 
                hide_index=True, 
                width="stretch", 
                key="editor_cartao"
            )
            
            if st.button("💾 Salvar Edições (Cartão)", type="primary", key="btn_cartao"):
                for _, r in df_ed_cartao.iterrows():
                    if r["Excluir"]:
                        c_fin.execute("DELETE FROM transacoes WHERE id = ? AND usuario = ?", (int(r['id']), user))
                    else:
                        c_fin.execute(
                            "UPDATE transacoes SET data = ?, descricao = ?, valor = ?, categoria = ?, status_fatura = ? WHERE id = ? AND usuario = ?", 
                            (r['data'], r['descricao'], r['valor'], r['categoria'], r['status_fatura'], int(r['id']), user)
                        )
                        if r['descricao'] and r['categoria'] != "Ignorar":
                            c_fin.execute(
                                "INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", 
                                (user, str(r['descricao']).strip(), r['categoria'])
                            )
                
                st.success("Alterações salvas com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum lançamento de fatura de cartão encontrado.")

    # --- ABA 3: TODOS OS REGISTROS (VISÃO GERAL) ---
    with tab_todos:
        st.markdown("### Visão Completa Consolidada")
        df_all = pd.read_sql_query("SELECT id, data, descricao, valor, categoria, status_fatura, origem FROM transacoes WHERE usuario = ? ORDER BY data DESC", conn_fin, params=(user,))
        
        if not df_all.empty:
            df_all["Excluir"] = False
            
            df_ed = st.data_editor(
                df_all, 
                column_config={
                    "id": None, 
                    "Excluir": st.column_config.CheckboxColumn("❌ Excluir?", help="Marque para apagar este lançamento"),
                    "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_categorias)
                }, 
                hide_index=True, 
                width="stretch", 
                key="editor_todos"
            )
            
            if st.button("💾 Salvar Edições (Todos)", type="primary", key="btn_todos"):
                for _, r in df_ed.iterrows():
                    if r["Excluir"]:
                        c_fin.execute("DELETE FROM transacoes WHERE id = ? AND usuario = ?", (int(r['id']), user))
                    else:
                        c_fin.execute(
                            "UPDATE transacoes SET data = ?, descricao = ?, valor = ?, categoria = ?, status_fatura = ? WHERE id = ? AND usuario = ?", 
                            (r['data'], r['descricao'], r['valor'], r['categoria'], r['status_fatura'], int(r['id']), user)
                        )
                        if r['descricao'] and r['categoria'] != "Ignorar":
                            c_fin.execute(
                                "INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) VALUES (?, ?, ?) ON CONFLICT(usuario, termo_chave) DO UPDATE SET categoria_destino = excluded.categoria_destino", 
                                (user, str(r['descricao']).strip(), r['categoria'])
                            )
                
                st.success("Salvo!")
                st.rerun()
        else:
            st.info("Nenhum lançamento cadastrado.")