import streamlit as st
import pandas as pd

def render_divida(user, conn_proj, c_proj, get_param, set_param):
    t_div = get_param(user, "divida_titulo", "DÍVIDA FIXA")
    st.subheader(f"📌 {t_div}")
    v_tot = float(get_param(user, "valor_total", "50005.81"))
    v_doa = float(get_param(user, "doacao", "20000.00"))
    df_div = pd.read_sql_query("SELECT id, ano, mes, valor, destino FROM controle_divida WHERE usuario = ?", conn_proj, params=(user,))
    t_pago = df_div['valor'].sum() if not df_div.empty else 0.0
    falta = v_tot - (t_pago + v_doa)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Total", f"R$ {v_tot:,.2f}")
    c2.metric("🟢 Pago", f"R$ {t_pago:,.2f}")
    c3.metric("🔵 Doação", f"R$ {v_doa:,.2f}")
    c4.metric("🟤 Falta", f"R$ {falta:,.2f}")

    ano_s = st.selectbox("Ano:", [2025, 2026, 2027], index=1)
    df_a = df_div[df_div['ano'] == ano_s]
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    t_div_tab = []
    for m in meses:
        r = df_a[df_a['mes'] == m]
        if not r.empty:
            t_div_tab.append({"id": r.iloc[0]['id'], "Mês": m, "Valor (R$)": r.iloc[0]['valor'], "Destino": r.iloc[0]['destino']})
        else:
            t_div_tab.append({"id": None, "Mês": m, "Valor (R$)": 0.0, "Destino": ""})

    ed_div = st.data_editor(pd.DataFrame(t_div_tab), column_config={"id": None, "Mês": st.column_config.TextColumn("Mês", disabled=True)}, hide_index=True, width="stretch")
    if st.button("💾 Salvar Dívida", type="primary"):
        for _, r in ed_div.iterrows():
            if pd.notna(r['id']):
                if r['Valor (R$)'] > 0: c_proj.execute("UPDATE controle_divida SET valor=?, destino=? WHERE id=? AND usuario=?", (r['Valor (R$)'], r['Destino'], r['id'], user))
                else: c_proj.execute("DELETE FROM controle_divida WHERE id=? AND usuario=?", (r['id'], user))
            else:
                if r['Valor (R$)'] > 0: c_proj.execute("INSERT INTO controle_divida (usuario, ano, mes, valor, destino) VALUES (?, ?, ?, ?, ?)", (user, ano_s, r['Mês'], r['Valor (R$)'], r['Destino']))
        conn_proj.commit()
        st.success("Salvo!")
        st.rerun()

def render_casa(user, conn_proj, c_proj, get_param):
    t_casa = get_param(user, "casa_titulo", "CASA / FINANCIAMENTO")
    p1 = get_param(user, "participante_1", "Você")
    p2 = get_param(user, "participante_2", "Parceiro(a)")
    st.subheader(f"❤️ {t_casa}")

    df_c = pd.read_sql_query("SELECT id, ano, mes, col1, col2, col3, col4, val_p1, val_p2 FROM casa_despesas WHERE usuario = ?", conn_proj, params=(user,))
    ano_c = st.selectbox("Ano Casa:", [2025, 2026, 2027], index=1)
    df_ca = df_c[df_c['ano'] == ano_c]
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    
    t_c_tab = []
    for m in meses:
        r = df_ca[df_ca['mes'] == m]
        if not r.empty:
            row = r.iloc[0]
            t_c_tab.append({"id": row['id'], "Mês": m, "Parcela": row['col1'], "Manutenção": row['col2'], "Energia": row['col3'], "Água": row['col4'], f"{p1} Pago": row['val_p1'], f"{p2} Pago": row['val_p2']})
        else:
            t_c_tab.append({"id": None, "Mês": m, "Parcela": 0.0, "Manutenção": 0.0, "Energia": 0.0, "Água": 0.0, f"{p1} Pago": 0.0, f"{p2} Pago": 0.0})

    ed_c = st.data_editor(pd.DataFrame(t_c_tab), column_config={"id": None, "Mês": st.column_config.TextColumn("Mês", disabled=True)}, hide_index=True, width="stretch")
    if st.button("💾 Salvar Casa", type="primary"):
        for _, r in ed_c.iterrows():
            tot = r['Parcela'] + r['Manutenção'] + r['Energia'] + r['Água']
            vp1, vp2 = r[f"{p1} Pago"], r[f"{p2} Pago"]
            if pd.notna(r['id']):
                if tot > 0: c_proj.execute("UPDATE casa_despesas SET col1=?, col2=?, col3=?, col4=?, val_p1=?, val_p2=? WHERE id=? AND usuario=?", (r['Parcela'], r['Manutenção'], r['Energia'], r['Água'], vp1, vp2, r['id'], user))
                else: c_proj.execute("DELETE FROM casa_despesas WHERE id=? AND usuario=?", (r['id'], user))
            else:
                if tot > 0: c_proj.execute("INSERT INTO casa_despesas (usuario, ano, mes, col1, col2, col3, col4, val_p1, val_p2) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (user, ano_c, r['Mês'], r['Parcela'], r['Manutenção'], r['Energia'], r['Água'], vp1, vp2))
        conn_proj.commit()
        st.success("Salvo!")
        st.rerun()

def render_extra_casa(user, conn_proj, c_proj, get_param):
    st.subheader("🏠 Extra Casa")
    p1 = get_param(user, "participante_1", "Você")
    p2 = get_param(user, "participante_2", "Parceiro(a)")

    df_q = pd.read_sql_query("SELECT id, item, val_p1, val_p2 FROM extra_casa WHERE usuario = ?", conn_proj, params=(user,))
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
            c_proj.execute("INSERT INTO extra_casa (usuario, item, val_p1, val_p2) VALUES (?, ?, ?, ?)", (user, it, va, vi))
            conn_proj.commit()
            st.rerun()

    if not df_q.empty:
        ed_q = st.data_editor(df_q, column_config={"id": None, "item": st.column_config.TextColumn("Item"), "val_p1": st.column_config.NumberColumn(f"{p1} (R$)", format="R$ %.2f"), "val_p2": st.column_config.NumberColumn(f"{p2} (R$)", format="R$ %.2f")}, hide_index=True, width="stretch")
        if st.button("💾 Salvar Alterações Extra Casa", type="primary"):
            for _, r in ed_q.iterrows():
                if r['item']: c_proj.execute("UPDATE extra_casa SET item=?, val_p1=?, val_p2=? WHERE id=? AND usuario=?", (r['item'], r['val_p1'], r['val_p2'], r['id'], user))
                else: c_proj.execute("DELETE FROM extra_casa WHERE id=? AND usuario=?", (r['id'], user))
            conn_proj.commit()
            st.success("Atualizado!")
            st.rerun()