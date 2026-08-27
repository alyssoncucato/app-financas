import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text

def render_divida(user, conn_proj, c_proj, get_param, set_param):
    t_div = get_param(user, "divida_titulo", "DÍVIDA FIXA")
    st.subheader(f"📌 {t_div}")

    p1 = get_param(user, "participante_1", "Alysson")
    p2 = get_param(user, "participante_2", "Isabela")

    ano_s = st.selectbox("Ano:", [2025, 2026, 2027], index=1, key="select_ano_divida")

    # --- 1. BUSCA DADOS DA TABELA DE DÍVIDAS NO SUPABASE ---
    try:
        with engine.connect() as conn:
            df_div = pd.read_sql_query(
                text("SELECT id, ano, mes, valor, destino FROM controle_divida WHERE usuario = :usuario AND ano = :ano"),
                conn,
                params={"usuario": user, "ano": int(ano_s)}
            )
    except Exception:
        df_div = pd.DataFrame()

    # Os pagamentos mensais possuem o campo 'mes' preenchido (JANEIRO, FEVEREIRO...)
    if not df_div.empty:
        df_mensal = df_div[df_div['mes'].notna() & (df_div['mes'].astype(str).str.strip() != "")]
    else:
        df_mensal = pd.DataFrame()

    # Soma tudo o que foi pago nos meses com destino IVA ou PIX IVA
    if not df_mensal.empty:
        df_mensal['dest_clean'] = df_mensal['destino'].astype(str).str.strip().str.upper()
        t_pago = df_mensal[df_mensal['dest_clean'].isin(['PIX IVA', 'IVA'])]['valor'].sum()
    else:
        t_pago = 0.0

    # Valor da Doação fixa (20.000)
    v_doa = 20000.00
    
    # Dívida Total fixa padrão da planilha (49.555,81)
    v_tot = 49555.81
    falta = v_tot - (t_pago + v_doa)

    # Métricas Globais do Topo
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Dívida Total (IVA)", f"R$ {v_tot:,.2f}")
    c2.metric("🟢 Pago (IVA Mensal)", f"R$ {t_pago:,.2f}")
    c3.metric("🔵 Doação", f"R$ {v_doa:,.2f}")
    c4.metric("🟤 Falta", f"R$ {falta:,.2f}")

    st.divider()

    # --- 2. TABELA DE PAGAMENTOS MENSAIS PARA A IVA (R$ 1.700 / mês) ---
    st.markdown("### 💳 Pagamentos Mensais para a IVA (Abatimento)")
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    
    t_mensal_tab = []
    for m in meses:
        r = df_mensal[df_mensal['mes'].astype(str).str.strip().str.upper() == m] if not df_mensal.empty else pd.DataFrame()
        if not r.empty:
            dest_atual = str(r.iloc[0]['destino'] or "").strip()
            dest_opcao = dest_atual.upper() if dest_atual.upper() in ["PIX IVA", "IVA"] else ("PIX IVA" if dest_atual else "")
            t_mensal_tab.append({
                "id": r.iloc[0]['id'],
                "Mês": m,
                "Valor (R$)": float(r.iloc[0]['valor'] or 0.0),
                "Destino": dest_opcao
            })
        else:
            t_mensal_tab.append({
                "id": None,
                "Mês": m,
                "Valor (R$)": 0.0,
                "Destino": ""
            })

    ed_mensal = st.data_editor(
        pd.DataFrame(t_mensal_tab)[["id", "Mês", "Valor (R$)", "Destino"]],
        column_config={
            "id": None,
            "Mês": st.column_config.TextColumn("Mês", disabled=True),
            "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "Destino": st.column_config.SelectboxColumn("Destino", options=["", "PIX IVA", "IVA"])
        },
        hide_index=True,
        width="stretch",
        key=f"editor_mensal_{ano_s}"
    )

    if st.button("💾 Salvar Pagamentos Mensais", type="primary", key="btn_save_mensal"):
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for _, r in ed_mensal.iterrows():
                        val = float(r['Valor (R$)']) if pd.notna(r['Valor (R$)']) else 0.0
                        dest = str(r['Destino']) if pd.notna(r['Destino']) else ""
                        
                        if pd.notna(r.get('id')):
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
            st.success("Pagamentos mensais salvos com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar pagamentos mensais: {e}")

    st.divider()

    # --- 3. TABELA DE DETALHAMENTO DOS GASTOS (MODELO PLANILHA) ---
    st.markdown("### 📋 Detalhamento dos Gastos da Dívida")
    st.info("💡 *Nota: Esta tabela exibe o resumo descritivo dos itens da planilha para o seu acompanhamento.*")

    itens_padrao = [
        ("IR ALYSSON", "TENTATIVA DE COMPRA COM DECLARACAO DE IR", 1737.62, 868.82, 868.81, 0.0),
        ("IR ISABELA", "TENTATIVA DE COMPRA COM DECLARACAO DE IR", 201.61, 100.86, 100.85, 0.0),
        ("IMPOSTO SALARIO ALYSSON", "IMPOSTO DO SALARIO ALYSSON PARA JACKSON", 1000.00, 1000.00, 0.0, 0.0),
        ("VISTORIA", "VISTORIA DA CAIXA PARA AVALIAR A CASA", 750.00, 750.00, 0.0, 0.0),
        ("CARTORIO", "ASSINATURA DA DECLARAÇÃO DE 1º IMOVEL", 29.30, 29.30, 0.0, 0.0),
        ("ITBI", "IMPOSTO TRANSFERENCIA PREFEITURA", 2560.00, 0.0, 0.0, 2560.00),
        ("CARTORIO", "TAXA DO REGISTRO DO CONTRATO", 5995.81, 0.0, 0.0, 5995.81),
        ("PRIMEIRA ENTRADA", "VALOR DE ENTRADA DA CASA COMEÇO", 25500.00, 0.0, 0.0, 25500.00),
        ("REAJUSTE ENTRADA", "VALOR QUE FALTOU NA ENTRADA DA CASA", 18500.00, 3000.00, 5000.00, 10500.00),
        ("CAIXA", "SEGURO E TAXA DA CAIXA", 4978.99, 0.0, 0.0, 5000.00),
        ("ELETRICISTA", "ELETRICA DA CASA - 220V E DISJUNTORES", 950.00, 950.00, 0.0, 0.0)
    ]

    t_div_tab = []
    for gasto, desc, val, vp1, vp2, iva in itens_padrao:
        t_div_tab.append({
            "Gasto": gasto,
            "Descrição": desc,
            "Valor Total (R$)": val,
            f"{p1} (R$)": vp1,
            f"{p2} (R$)": vp2,
            "IVA (R$)": iva
        })

    st.dataframe(pd.DataFrame(t_div_tab), hide_index=True, width="stretch")

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