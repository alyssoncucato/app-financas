import streamlit as st
import pandas as pd
from database import engine, get_param, set_param
from sqlalchemy import text

def render(user):
    st.subheader("✈️ Planejamento Completo de Viagem")
    
    p1 = get_param(user, "participante_1", "Alysson")
    p2 = get_param(user, "participante_2", "Isabela")

    # --- SELEÇÃO / CRIAÇÃO DO DESTINO ---
    try:
        with engine.connect() as conn:
            df_viagens = pd.read_sql_query(
                text("SELECT id, destino, data_viagem, precisa_passaporte_visto FROM viagens_lista WHERE usuario = :u ORDER BY id DESC"),
                conn,
                params={"u": user}
            )
    except Exception:
        df_viagens = pd.DataFrame()

    with st.expander("➕ Cadastrar Nova Viagem / Destino", expanded=df_viagens.empty):
        with st.form("form_nova_viagem"):
            c_v1, c_v2, c_v3 = st.columns([2, 1, 1])
            with c_v1:
                novo_destino = st.text_input("Destino da Viagem:", placeholder="Ex: Santiago - Chile, Gramado, Orlando...")
            with c_v2:
                data_est = st.text_input("Data ou Mês Previsto:", placeholder="Ex: Outubro / 2026")
            with c_v3:
                precisa_visto_doc = st.checkbox("Exige Passaporte / Visto?", value=False)
            
            btn_criar_viagem = st.form_submit_button("Criar Roteiro de Viagem", type="primary")
            if btn_criar_viagem:
                if novo_destino.strip():
                    try:
                        with engine.connect() as conn_ins:
                            with conn_ins.begin():
                                conn_ins.execute(
                                    text("""
                                        INSERT INTO viagens_lista (usuario, destino, data_viagem, precisa_passaporte_visto) 
                                        VALUES (:u, :d, :dt, :pv)
                                    """),
                                    {"u": user, "d": novo_destino.strip(), "dt": data_est.strip(), "pv": "1" if precisa_visto_doc else "0"}
                                )
                        st.success("Viagem cadastrada!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar viagem: {e}")
                else:
                    st.warning("Preencha o destino.")

    if df_viagens.empty:
        st.info("Nenhuma viagem cadastrada ainda. Cadastre o seu destino acima para começar o roteiro!")
        return

    # Seletor da viagem atual
    destinos_dict = {f"{r['destino']} ({r['data_viagem'] or 'Data não inf.'})": r['id'] for _, r in df_viagens.iterrows()}
    viagem_escolhida_nome = st.selectbox("Selecione a Viagem em Planejamento:", list(destinos_dict.keys()))
    viagem_id = int(destinos_dict[viagem_escolhida_nome])
    
    viagem_atual = df_viagens[df_viagens['id'] == viagem_id].iloc[0]
    exige_visto = str(viagem_atual.get('precisa_passaporte_visto', '0')) == "1"

    st.divider()

    # --- CARREGA OS ITENS DA VIAGEM ---
    try:
        with engine.connect() as conn:
            df_itens = pd.read_sql_query(
                text("SELECT id, categoria, item, valor_estimado, quem_paga, status, obs FROM viagens_itens WHERE viagem_id = :vid ORDER BY id ASC"),
                conn,
                params={"vid": viagem_id}
            )
    except Exception:
        df_itens = pd.DataFrame()

    # Se a viagem for nova e não tiver itens, preenche com um checklist inteligente completo
    if df_itens.empty:
        itens_padrao = [
            ("Passagens e Voos", "Voo de Ida", 0.0, "Dividido", "Pendente", "Bagagem despachada inclusa?"),
            ("Passagens e Voos", "Voo de Volta", 0.0, "Dividido", "Pendente", ""),
            ("Hospedagem", "Hotel / Airbnb", 0.0, "Dividido", "Pendente", "Com café da manhã?"),
            ("Translado e Transporte", "Translado: Casa -> Aeroporto de Origem", 0.0, p1, "Pendente", "Uber / Táxi / Estacionamento"),
            ("Translado e Transporte", "Translado: Aeroporto Destino -> Hotel", 0.0, "Dividido", "Pendente", ""),
            ("Translado e Transporte", "Transporte Local durante a viagem", 0.0, "Dividido", "Pendente", "Metrô / Carro alugado / Uber"),
            ("Translado e Transporte", "Translado: Hotel -> Aeroporto Destino", 0.0, "Dividido", "Pendente", ""),
            ("Translado e Transporte", "Translado: Aeroporto Origem -> Casa", 0.0, p1, "Pendente", ""),
            ("Alimentação", "Estimativa de Restaurantes e Alimentação", 0.0, "Dividido", "Pendente", "Almoço, janta e cafés"),
            ("Passeios e Lazer", "Ingressos e Roteiros Principais", 0.0, "Dividido", "Pendente", ""),
            ("Seguro e Saúde", "Seguro Viagem", 0.0, "Dividido", "Pendente", ""),
            ("Compras", "Lembranças e Gastos Pessoais", 0.0, "Dividido", "Pendente", "")
        ]
        
        if exige_visto:
            itens_padrao = [
                ("Documentação", f"Passaporte ({p1})", 0.0, p1, "Pendente", "Verificar validade mínima 6 meses"),
                ("Documentação", f"Passaporte ({p2})", 0.0, p2, "Pendente", "Verificar validade mínima 6 meses"),
                ("Documentação", f"Visto / Autorização ({p1})", 0.0, p1, "Pendente", "Taxa consular"),
                ("Documentação", f"Visto / Autorização ({p2})", 0.0, p2, "Pendente", "Taxa consular"),
                ("Documentação", "Certificado Internacional de Vacina / IOF", 0.0, "Dividido", "Pendente", "")
            ] + itens_padrao

        with engine.connect() as conn_ins_default:
            with conn_ins_default.begin():
                for cat, itm, val, qp, stt, obs in itens_padrao:
                    conn_ins_default.execute(
                        text("""
                            INSERT INTO viagens_itens (viagem_id, categoria, item, valor_estimado, quem_paga, status, obs)
                            VALUES (:vid, :cat, :itm, :val, :qp, :stt, :obs)
                        """),
                        {"vid": viagem_id, "cat": cat, "itm": itm, "val": val, "qp": qp, "stt": stt, "obs": obs}
                    )
        st.rerun()

    # --- MÉTRICAS CONSOLIDADAS DA VIAGEM ---
    total_orcado = df_itens['valor_estimado'].sum() if not df_itens.empty else 0.0
    total_pago = df_itens[df_itens['status'] == 'Pago']['valor_estimado'].sum() if not df_itens.empty else 0.0
    total_pendente = total_orcado - total_pago

    # Cálculo da divisão por pessoa
    custo_p1 = 0.0
    custo_p2 = 0.0
    for _, row in df_itens.iterrows():
        v = float(row['valor_estimado'] or 0.0)
        qp = str(row['quem_paga']).strip()
        if qp == p1:
            custo_p1 += v
        elif qp == p2:
            custo_p2 += v
        else: # Dividido
            custo_p1 += v / 2.0
            custo_p2 += v / 2.0

    st.markdown("### 📊 Resumo Financeiro do Roteiro")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("💰 Total Orçado", f"R$ {total_orcado:,.2f}")
    m2.metric("🟢 Já Pago / Reservado", f"R$ {total_pago:,.2f}")
    m3.metric("⏳ Falta Pagar", f"R$ {total_pendente:,.2f}")
    m4.metric(f"🔵 Custo {p1}", f"R$ {custo_p1:,.2f}")
    m5.metric(f"🩷 Custo {p2}", f"R$ {custo_p2:,.2f}")

    st.divider()

    # --- TABELA EDITÁVEL COM CHECKLIST E ITENS ---
    st.markdown("### 📋 Itens, Logística e Documentos")
    st.caption("Altere os valores, adicione novos passeios/translados ou marque os status. Clique em salvar ao finalizar:")

    categorias_opcoes = [
        "Documentação", "Passagens e Voos", "Hospedagem", 
        "Translado e Transporte", "Passeios e Lazer", 
        "Alimentação", "Seguro e Saúde", "Compras", "Outros"
    ]
    pagador_opcoes = ["Dividido", p1, p2]
    status_opcoes = ["Pendente", "Pago", "Reservado", "Não se Aplica"]

    ed_itens = st.data_editor(
        df_itens,
        column_config={
            "id": None,
            "viagem_id": None,
            "categoria": st.column_config.SelectboxColumn("Categoria", options=categorias_opcoes, required=True, width="medium"),
            "item": st.column_config.TextColumn("Descrição do Item / Etapa", width="large", required=True),
            "valor_estimado": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "quem_paga": st.column_config.SelectboxColumn("Quem Paga", options=pagador_opcoes, required=True, width="small"),
            "status": st.column_config.SelectboxColumn("Status", options=status_opcoes, required=True, width="small"),
            "obs": st.column_config.TextColumn("Anotações / Detalhes", width="large")
        },
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=f"editor_viagem_{viagem_id}"
    )

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        if st.button("💾 Salvar Alterações da Viagem", type="primary"):
            try:
                with engine.connect() as connection:
                    with connection.begin():
                        ids_tela = [int(r['id']) for _, r in ed_itens.iterrows() if pd.notna(r.get('id'))]
                        if ids_tela:
                            connection.execute(
                                text("DELETE FROM viagens_itens WHERE viagem_id = :vid AND id NOT IN :ids"),
                                {"vid": viagem_id, "ids": tuple(ids_tela)}
                            )
                        else:
                            connection.execute(
                                text("DELETE FROM viagens_itens WHERE viagem_id = :vid"),
                                {"vid": viagem_id}
                            )

                        for _, r in ed_itens.iterrows():
                            c = str(r['categoria']) if pd.notna(r.get('categoria')) else "Outros"
                            it = str(r['item']) if pd.notna(r.get('item')) else ""
                            v = float(r['valor_estimado']) if pd.notna(r.get('valor_estimado')) else 0.0
                            qp = str(r['quem_paga']) if pd.notna(r.get('quem_paga')) else "Dividido"
                            stt = str(r['status']) if pd.notna(r.get('status')) else "Pendente"
                            ob = str(r['obs']) if pd.notna(r.get('obs')) else ""

                            if pd.notna(r.get('id')):
                                connection.execute(
                                    text("""
                                        UPDATE viagens_itens 
                                        SET categoria = :c, item = :it, valor_estimado = :v, quem_paga = :qp, status = :stt, obs = :ob 
                                        WHERE id = :id AND viagem_id = :vid
                                    """),
                                    {"c": c, "it": it, "v": v, "qp": qp, "stt": stt, "ob": ob, "id": int(r['id']), "vid": viagem_id}
                                )
                            else:
                                if it.strip() or v > 0:
                                    connection.execute(
                                        text("""
                                            INSERT INTO viagens_itens (viagem_id, categoria, item, valor_estimado, quem_paga, status, obs) 
                                            VALUES (:vid, :c, :it, :v, :qp, :stt, :ob)
                                        """),
                                        {"vid": viagem_id, "c": c, "it": it, "v": v, "qp": qp, "stt": stt, "ob": ob}
                                    )
                st.success("Planejamento da viagem atualizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar alterações: {e}")

    with col_btn2:
        if st.button("🗑️ Excluir Viagem", type="secondary"):
            try:
                with engine.connect() as connection:
                    with connection.begin():
                        connection.execute(text("DELETE FROM viagens_itens WHERE viagem_id = :vid"), {"vid": viagem_id})
                        connection.execute(text("DELETE FROM viagens_lista WHERE id = :vid AND usuario = :u"), {"vid": viagem_id, "u": user})
                st.success("Viagem excluída!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao excluir viagem: {e}")