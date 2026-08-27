import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text

def render_divida(user, conn_proj, c_proj, get_param, set_param):
    t_div = get_param(user, "divida_titulo", "DÍVIDA FIXA")
    st.subheader(f"📌 {t_div}")
    v_tot = float(get_param(user, "valor_total", "50005.81"))
    v_doa = float(get_param(user, "doacao", "20000.00"))
    
    # Busca dados direto com a engine segura
    try:
        with engine.connect() as conn:
            df_div = pd.read_sql_query(
                text("SELECT id, ano, mes, valor, destino FROM controle_divida WHERE usuario = :usuario"),
                conn,
                params={"usuario": user}
            )
    except Exception:
        df_div = pd.DataFrame()

    # REGRA: O valor pago só soma se o destino for exatamente "PIX IVA" (ignorando maiúsculas/minúsculas)
    if not df_div.empty:
        df_div['destino_clean'] = df_div['destino'].astype(str).str.strip().str.upper()
        t_pago = df_div[df_div['destino_clean'] == 'PIX IVA']['valor'].sum()
    else:
        t_pago = 0.0

    falta = v_tot - (t_pago + v_doa)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Total", f"R$ {v_tot:,.2f}")
    c2.metric("🟢 Pago (PIX IVA)", f"R$ {t_pago:,.2f}")
    c3.metric("🔵 Doação", f"R$ {v_doa:,.2f}")
    c4.metric("🟤 Falta", f"R$ {falta:,.2f}")

    # Seletor de Ano (ao mudar, limpa a chave do editor para forçar o recarregamento correto)
    ano_s = st.selectbox("Ano:", [2025, 2026, 2027], index=1, key="select_ano_divida")
    
    # Filtra estritamente pelo ano selecionado
    df_a = df_div[df_div['ano'] == int(ano_s)] if not df_div.empty else pd.DataFrame()
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    
    t_div_tab = []
    for m in meses:
        r = df_a[df_a['mes'] == m] if not df_a.empty else pd.DataFrame()
        if not r.empty:
            dest_atual = str(r.iloc[0]['destino'] or "").strip()
            if dest_atual.upper() not in ["PIX IVA", ""]:
                dest_opcao = dest_atual
            else:
                dest_opcao = dest_atual.upper() if dest_atual else ""

            t_div_tab.append({
                "id": r.iloc[0]['id'], 
                "Mês": m, 
                "Valor (R$)": float(r.iloc[0]['valor']),
                "Destino": dest_opcao
            })
        else:
            # Se não houver registro para este mês neste ano, vem zerado e limpo!
            t_div_tab.append({
                "id": None, 
                "Mês": m, 
                "Valor (R$)": 0.0,
                "Destino": ""
            })

    df_tabela = pd.DataFrame(t_div_tab)[["id", "Mês", "Valor (R$)", "Destino"]]

    # Chave dinâmica baseada no ano para o Streamlit recriar o editor limpo ao trocar de ano
    ed_div = st.data_editor(
        df_tabela, 
        column_config={
            "id": None, 
            "Mês": st.column_config.TextColumn("Mês", disabled=True),
            "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "Destino": st.column_config.SelectboxColumn("Destino", options=["", "PIX IVA"])
        }, 
        hide_index=True, 
        width="stretch",
        key=f"editor_dividas_{ano_s}"
    )

    if st.button("💾 Salvar Dívida", type="primary"):
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for _, r in ed_div.iterrows():
                        val = float(r['Valor (R$)']) if pd.notna(r['Valor (R$)']) else 0.0
                        dest = str(r['Destino']) if pd.notna(r['Destino']) else ""
                        
                        if pd.notna(r['id']):
                            if val > 0:
                                connection.execute(
                                    text("UPDATE controle_divida SET valor = :val, destino = :dest WHERE id = :id AND usuario = :usuario"),
                                    {"val": val, "dest": dest, "id": int(r['id']), "usuario": user}
                                )
                            else:
                                connection.execute(
                                    text("DELETE FROM controle_divida WHERE id = :id AND usuario = :usuario"),
                                    {"id": int(r['id']), "usuario": user}
                                )
                        else:
                            if val > 0:
                                connection.execute(
                                    text("INSERT INTO controle_divida (usuario, ano, mes, valor, destino) VALUES (:usuario, :ano, :mes, :val, :dest)"),
                                    {"usuario": user, "ano": int(ano_s), "mes": r['Mês'], "val": val, "dest": dest}
                                )
            
            st.success("Dívida salva com sucesso no Supabase!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar dívida: {e}")

def render_casa(user, conn_proj, c_proj, get_param):
    t_casa = get_param(user, "casa_titulo", "CASA / FINANCIAMENTO")
    p1 = get_param(user, "participante_1", "Você")
    p2 = get_param(user, "participante_2", "Parceiro(a)")
    st.subheader(f"❤️ {t_casa}")

    try:
        with engine.connect() as conn:
            df_c = pd.read_sql_query(
                text("SELECT id, ano, mes, col1, col2, col3, col4, val_p1, val_p2 FROM casa_despesas WHERE usuario = :usuario"),
                conn,
                params={"usuario": user}
            )
    except Exception:
        df_c = pd.DataFrame()

    ano_c = st.selectbox("Ano Casa:", [2025, 2026, 2027], index=1, key="select_ano_casa")
    df_ca = df_c[df_c['ano'] == int(ano_c)] if not df_c.empty else pd.DataFrame()
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    
    t_c_tab = []
    for m in meses:
        r = df_ca[df_ca['mes'] == m] if not df_ca.empty else pd.DataFrame()
        if not r.empty:
            row = r.iloc[0]
            t_c_tab.append({"id": row['id'], "Mês": m, "Parcela": float(row['col1']), "Manutenção": float(row['col2']), "Energia": float(row['col3']), "Água": float(row['col4']), f"{p1} Pago": float(row['val_p1']), f"{p2} Pago": float(row['val_p2'])})
        else:
            t_c_tab.append({"id": None, "Mês": m, "Parcela": 0.0, "Manutenção": 0.0, "Energia": 0.0, "Água": 0.0, f"{p1} Pago": 0.0, f"{p2} Pago": 0.0})

    ed_c = st.data_editor(
        pd.DataFrame(t_c_tab), 
        column_config={
            "id": None, 
            "Mês": st.column_config.TextColumn("Mês", disabled=True)
        }, 
        hide_index=True, 
        width="stretch",
        key=f"editor_casa_{ano_c}"
    )

    if st.button("💾 Salvar Casa", type="primary"):
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for _, r in ed_c.iterrows():
                        p = float(r['Parcela'])
                        man = float(r['Manutenção'])
                        ene = float(r['Energia'])
                        agu = float(r['Água'])
                        tot = p + man + ene + agu
                        vp1 = float(r[f"{p1} Pago"])
                        vp2 = float(r[f"{p2} Pago"])
                        
                        if pd.notna(r['id']):
                            if tot > 0:
                                connection.execute(
                                    text("UPDATE casa_despesas SET col1 = :c1, col2 = :c2, col3 = :c3, col4 = :c4, val_p1 = :vp1, val_p2 = :vp2 WHERE id = :id AND usuario = :usuario"),
                                    {"c1": p, "c2": man, "c3": ene, "c4": agu, "vp1": vp1, "vp2": vp2, "id": int(r['id']), "usuario": user}
                                )
                            else:
                                connection.execute(
                                    text("DELETE FROM casa_despesas WHERE id = :id AND usuario = :usuario"),
                                    {"id": int(r['id']), "usuario": user}
                                )
                        else:
                            if tot > 0:
                                connection.execute(
                                    text("INSERT INTO casa_despesas (usuario, ano, mes, col1, col2, col3, col4, val_p1, val_p2) VALUES (:usuario, :ano, :mes, :c1, :c2, :c3, :c4, :vp1, :vp2)"),
                                    {"usuario": user, "ano": int(ano_c), "mes": r['Mês'], "c1": p, "c2": man, "c3": ene, "c4": agu, "vp1": vp1, "vp2": vp2}
                                )
            st.success("Casa salva com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar casa: {e}")

def render_extra_casa(user, conn_proj, c_proj, get_param):
    st.subheader("🏠 Extra Casa")
    p1 = get_param(user, "participante_1", "Você")
    p2 = get_param(user, "participante_2", "Parceiro(a)")

    try:
        with engine.connect() as conn:
            df_q = pd.read_sql_query(
                text("SELECT id, item, val_p1, val_p2 FROM extra_casa WHERE usuario = :usuario"),
                conn,
                params={"usuario": user}
            )
    except Exception:
        df_q = pd.DataFrame()

    tot_p1 = df_q['val_p1'].sum() if not df_q.empty else 0.0
    tot_p2 = df_q['val_p2'].sum() if not df_q.empty else 0.0

    c1, c2 = st.columns(2)
    c1.metric(f"🔵 TOTAL PAGO - {p1.upper()}", f"R$ {tot_p1:,.2f}")
    c2.metric(f"🩷 TOTAL PAGO - {p2.upper()}", f"R$ {tot_p2:,.2f}")

    st.divider()

    with st.form("f_extra_casa"):
        it = st.text_input("Item (Ex: Pedrinhas, Grama):")
        va = st.number_input(f"{p1} Pagou (R$):", value=0.0)
        vi = st.number_input(f"{p2} Pagou (R$):", value=0.0)
        if st.form_submit_button("Adicionar Item") and it:
            try:
                with engine.connect() as connection:
                    with connection.begin():
                        connection.execute(
                            text("INSERT INTO extra_casa (usuario, item, val_p1, val_p2) VALUES (:usuario, :item, :vp1, :vp2)"),
                            {"usuario": user, "item": it, "vp1": va, "vp2": vi}
                        )
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao adicionar item: {e}")

    if not df_q.empty:
        ed_q = st.data_editor(
            df_q, 
            column_config={
                "id": None, 
                "item": st.column_config.TextColumn("Item"), 
                "val_p1": st.column_config.NumberColumn(f"{p1} (R$)", format="R$ %.2f"), 
                "val_p2": st.column_config.NumberColumn(f"{p2} (R$)", format="R$ %.2f")
            }, 
            hide_index=True, 
            width="stretch",
            key="editor_extra_casa"
        )
        
        if st.button("💾 Salvar Alterações Extra Casa", type="primary"):
            try:
                with engine.connect() as connection:
                    with connection.begin():
                        for _, r in ed_q.iterrows():
                            item_nome = str(r['item']) if pd.notna(r['item']) else ""
                            vp1 = float(r['val_p1']) if pd.notna(r['val_p1']) else 0.0
                            vp2 = float(r['val_p2']) if pd.notna(r['val_p2']) else 0.0
                            
                            if item_nome.strip():
                                connection.execute(
                                    text("UPDATE extra_casa SET item = :item, val_p1 = :vp1, val_p2 = :vp2 WHERE id = :id AND usuario = :usuario"),
                                    {"item": item_nome, "vp1": vp1, "vp2": vp2, "id": int(r['id']), "usuario": user}
                                )
                            else:
                                connection.execute(
                                    text("DELETE FROM extra_casa WHERE id = :id AND usuario = :usuario"),
                                    {"id": int(r['id']), "usuario": user}
                                )
                st.success("Atualizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar extra casa: {e}")