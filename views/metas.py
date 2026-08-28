import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text
from io import BytesIO

def render(user, conn_proj, c_proj):
    st.subheader("🎯 Metas de Economia e Progresso")
    st.caption("Defina objetivos financeiros (ex: Trocar pneu, Viagem, Reserva de emergência) e acompanhe o progresso visualmente.")

    # --- 1. CRIAÇÃO DE NOVA META ---
    with st.form("form_nova_meta"):
        col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
        with col_m1:
            nome_meta = st.text_input("Nome da Meta:", placeholder="Ex: Juntar para IPVA, Casamento...")
        with col_m2:
            valor_alvo = st.number_input("Valor Alvo (R$):", min_value=0.0, format="%.2f", value=1000.0)
        with col_m3:
            valor_atual = st.number_input("Valor já Guardado (R$):", min_value=0.0, format="%.2f", value=0.0)
            
        if st.form_submit_button("Criar Meta de Economia", type="primary"):
            if nome_meta.strip():
                try:
                    with engine.connect() as connection:
                        with connection.begin():
                            connection.execute(
                                text("INSERT INTO metas_economia (usuario, nome_meta, valor_alvo, valor_atual) VALUES (:u, :n, :v_alvo, :v_atual)"),
                                {"u": user, "n": nome_meta.strip(), "v_alvo": valor_alvo, "v_atual": valor_atual}
                            )
                    st.success(f"Meta '{nome_meta}' criada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao criar meta: {e}")
            else:
                st.warning("Dê um nome para a meta.")

    st.divider()

    # --- 2. LISTAGEM E BARRAS DE PROGRESSO ---
    try:
        with engine.connect() as conn:
            df_metas = pd.read_sql_query(
                text("SELECT id, nome_meta, valor_alvo, valor_atual FROM metas_economia WHERE usuario = :u"),
                conn,
                params={"u": user}
            )
    except Exception:
        df_metas = pd.DataFrame()

    if df_metas.empty:
        st.info("Nenhuma meta cadastrada ainda. Crie sua primeira meta acima!")
    else:
        st.markdown("### 📊 Acompanhamento das Metas")
        for _, row in df_metas.iterrows():
            meta_id = int(row['id'])
            nome = row['nome_meta']
            alvo = float(row['valor_alvo'] or 1.0)
            atual = float(row['valor_atual'] or 0.0)
            
            progresso = min(max(atual / alvo, 0.0), 1.0)
            percentual = progresso * 100

            col_info1, col_info2, col_info3 = st.columns([3, 2, 2])
            col_info1.markdown(f"**{nome}**")
            col_info2.text(f"Guardado: R$ {atual:,.2f} / R$ {alvo:,.2f}")
            col_info3.text(f"Progresso: {percentual:.1f}%")

            st.progress(progresso)

            with st.expander(f"Atualizar valor para: {nome}"):
                novo_valor_atual = st.number_input("Novo valor guardado (R$):", value=atual, format="%.2f", key=f"val_meta_{meta_id}")
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Salvar Progresso", key=f"btn_save_meta_{meta_id}", type="primary"):
                        try:
                            with engine.connect() as connection:
                                with connection.begin():
                                    connection.execute(
                                        text("UPDATE metas_economia SET valor_atual = :v WHERE id = :id AND usuario = :u"),
                                        {"v": novo_valor_atual, "id": meta_id, "u": user}
                                    )
                            st.success("Atualizado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                with col_b2:
                    if st.button("Excluir Meta", key=f"btn_del_meta_{meta_id}", type="secondary"):
                        try:
                            with engine.connect() as connection:
                                with connection.begin():
                                    connection.execute(text("DELETE FROM metas_economia WHERE id = :id AND usuario = :u"), {"id": meta_id, "u": user})
                            st.success("Meta excluída.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
            st.markdown("---")

    st.divider()

    # --- 3. EXPORTAÇÃO PERSONALIZADA POR MÓDULO ---
    st.write("#### 📤 Exportar Relatórios Personalizados")
    st.caption("Baixe os dados consolidados dos projetos em formato de planilha Excel:")

    try:
        with engine.connect() as conn:
            df_proj_export = pd.read_sql_query(
                text("SELECT p.nome_projeto, i.item, i.valor, i.status FROM projetos_lista p JOIN projetos_itens i ON p.id = i.projeto_id WHERE p.usuario = :u"),
                conn,
                params={"u": user}
            )
        
        if not df_proj_export.empty:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_proj_export.to_excel(writer, index=False, sheet_name='Projetos e Reformas')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Baixar Relatório de Projetos (.xlsx)",
                data=excel_data,
                file_name=f"relatorio_projetos_{user}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.info("Nenhum dado de projeto disponível para exportação em Excel.")
    except Exception:
        st.info("Módulo de exportação pronto para uso.")