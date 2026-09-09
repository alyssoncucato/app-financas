import streamlit as st
import pandas as pd
from datetime import datetime
from calendar import monthrange
from sqlalchemy import text

def render(user, conn_fin, categorias_despesas, categorias_entradas, get_param=None, set_param=None):
    st.subheader("📊 Dashboard Financeiro & Projeção")
    
    try:
        query = text("SELECT * FROM transacoes WHERE LOWER(usuario) = LOWER(:u)")
        df = pd.read_sql_query(query, conn_fin, params={"u": user})
    except Exception as e:
        st.error(f"Erro ao carregar transações: {e}")
        return
    
    if df.empty:
        st.info("Nenhum lançamento encontrado. Importe extratos ou faturas para visualizar o dashboard.")
        return

    # Normalização e Tipagem
    df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
    df['ano'] = df['data_dt'].dt.year.fillna(datetime.now().year).astype(int)
    df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')
    
    if 'tipo' not in df.columns:
        df['tipo'] = "SAÍDA"
    df['tipo'] = df['tipo'].fillna("SAÍDA").str.upper()

    # --- SALDO REAL ACUMULADO DA CONTA CORRENTE ---
    saldo_inicial_str = get_param(user, "saldo_inicial_conta", "0.0") if get_param else "0.0"
    try:
        saldo_partida = float(saldo_inicial_str)
    except Exception:
        saldo_partida = 0.0

    df_cc_historico = df[(df['origem'] == 'EXTRATO_CONTA') & (~df['categoria'].isin(["Ignorar"]))]
    total_entradas_historico = df_cc_historico[df_cc_historico['tipo'] == 'ENTRADA']['valor'].sum()
    total_saidas_historico = df_cc_historico[df_cc_historico['tipo'] == 'SAÍDA']['valor'].sum()
    saldo_atual_em_conta = saldo_partida + total_entradas_historico - total_saidas_historico

    # --- MENU DE NAVEGAÇÃO ---
    st.markdown("### 🎯 Seleção de Visualização")
    col_n1, col_n2, col_n3 = st.columns(3)
    
    with col_n1:
        tipo_visao = st.selectbox(
            "1. Fonte de Dados:", 
            ["Visão Geral (Consolidada)", "💳 Cartão de Crédito (Faturas)", "🏦 Extrato Conta Corrente (Pix / Débito)"]
        )
    
    with col_n2:
        anos_disponiveis = sorted(list(df['ano'].unique()), reverse=True)
        if not anos_disponiveis:
            anos_disponiveis = [datetime.now().year]
        ano_sel = st.selectbox("2. Ano:", anos_disponiveis)

    df_ano = df[df['ano'] == ano_sel]

    if "Cartão" in tipo_visao:
        df_filtrado = df_ano[df_ano['origem'] == 'FATURA_CARTAO']
    elif "Conta Corrente" in tipo_visao:
        df_filtrado = df_ano[df_ano['origem'] == 'EXTRATO_CONTA']
    else:
        df_filtrado = df_ano

    with col_n3:
        meses_ano = sorted(df_filtrado['mes_ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
        opcoes_mes = ["Todos os Meses do Ano"] + meses_ano
        mes_atual_str = datetime.now().strftime('%m/%Y')
        index_padrao = opcoes_mes.index(mes_atual_str) if mes_atual_str in opcoes_mes else 0
        mes_sel = st.selectbox("3. Mês:", opcoes_mes, index=index_padrao)

    if mes_sel != "Todos os Meses do Ano":
        df_final = df_filtrado[df_filtrado['mes_ano'] == mes_sel]
        titulo_periodo = f"Mês: {mes_sel} ({ano_sel})"
    else:
        df_final = df_filtrado
        titulo_periodo = f"Ano Consolidado: {ano_sel}"

    st.divider()

    # --- FILTRO CONTRA DUPLICIDADES E PAGAMENTOS DE FATURA ---
    df_base_calc = df_final[~df_final['categoria'].isin(["Ignorar"])]

    if tipo_visao == "Visão Geral (Consolidada)":
        mask_pgto_cc = (df_base_calc['origem'] == 'EXTRATO_CONTA') & (
            (df_base_calc['categoria'].str.upper().isin(["PAGAMENTO FATURA"])) |
            (df_base_calc['descricao'].str.upper().str.contains("PAGAMENTO DE FATURA|PAGTO FATURA|PGTO FATURA|FATURA CARTAO"))
        )
        mask_pgto_cartao = (df_base_calc['origem'] == 'FATURA_CARTAO') & (
            (df_base_calc['categoria'].str.upper().isin(["PAGAMENTO FATURA"])) |
            (df_base_calc['descricao'].str.upper().str.contains("PAGAMENTO RECEBIDO"))
        )
        df_calculo = df_base_calc[~(mask_pgto_cc | mask_pgto_cartao)]
    elif "Cartão" in tipo_visao:
        mask_pgto_cartao = (df_base_calc['descricao'].str.upper().str.contains("PAGAMENTO RECEBIDO")) | (df_base_calc['categoria'].str.upper() == "PAGAMENTO FATURA")
        df_calculo = df_base_calc[~mask_pgto_cartao]
    else:
        df_calculo = df_base_calc

    receitas = df_calculo[df_calculo['tipo'] == 'ENTRADA']['valor'].sum()
    despesas = df_calculo[df_calculo['tipo'] == 'SAÍDA']['valor'].sum()
    resultado_mes = receitas - despesas

    # --- BLOCO DE MÉTRICAS PRINCIPAIS ---
    st.markdown(f"### 📈 Panorama: **{tipo_visao}** — *{titulo_periodo}*")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Entradas / Receitas", f"R$ {receitas:,.2f}")
    c2.metric("📉 Saídas / Despesas", f"R$ {despesas:,.2f}")
    c3.metric("⚖️ Balanço do Período", f"R$ {resultado_mes:,.2f}", delta=f"{resultado_mes:,.2f}")
    c4.metric("🏦 Saldo Real em Conta (Hoje)", f"R$ {saldo_atual_em_conta:,.2f}")

    # --- PREVISÃO PARA O FINAL DO MÊS ---
    hoje = datetime.now()
    e_mes_atual = (mes_sel == hoje.strftime('%m/%Y'))

    if e_mes_atual and not df_final.empty:
        st.markdown("#### 🔮 Previsão Inteligente para o Final do Mês")
        dias_no_mes = monthrange(hoje.year, hoje.month)[1]
        dias_passados = max(hoje.day, 1)
        dias_restantes = max(dias_no_mes - dias_passados, 0)

        media_gasto_dia = despesas / dias_passados
        gasto_projetado_fim_mes = despesas + (media_gasto_dia * dias_restantes)
        resultado_projetado_mes = receitas - gasto_projetado_fim_mes
        saldo_conta_previsto_fim_mes = saldo_atual_em_conta - (media_gasto_dia * dias_restantes)

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("⏱️ Ritmo Diário de Gastos", f"R$ {media_gasto_dia:,.2f}/dia", help="Média gasta por dia até o momento")
        p2.metric("📅 Projeção de Despesa Total", f"R$ {gasto_projetado_fim_mes:,.2f}", help="Estimativa mantendo seu ritmo diário atual")
        p3.metric("🎯 Resultado Previsto do Mês", f"R$ {resultado_projetado_mes:,.2f}", delta=f"{resultado_projetado_mes:,.2f}")
        p4.metric("🏁 Saldo Previsto em Conta", f"R$ {saldo_conta_previsto_fim_mes:,.2f}", delta=f"Faltam {dias_restantes} dias")

    st.divider()

    # --- IMPACTO LÍQUIDO POR CATEGORIA ---
    todas_as_cats = list(set(categorias_despesas + categorias_entradas + list(df_calculo['categoria'].unique())))
    resumo_cat_list = []
    
    for cat in todas_as_cats:
        if cat in ["Ignorar", "PAGAMENTO FATURA"] or not str(cat).strip():
            continue
        df_cat = df_calculo[df_calculo['categoria'] == cat]
        if not df_cat.empty:
            t_saida = df_cat[df_cat['tipo'] == 'SAÍDA']['valor'].sum()
            t_entrada = df_cat[df_cat['tipo'] == 'ENTRADA']['valor'].sum()
            resumo_cat_list.append({
                'categoria': cat,
                'saida': t_saida,
                'entrada': t_entrada,
                'valor_liquido': t_entrada - t_saida,
                'qtd': len(df_cat)
            })
            
    df_resumo_cat = pd.DataFrame(resumo_cat_list)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("#### 📊 Impacto Líquido por Categoria")
        if not df_resumo_cat.empty:
            df_graf = df_resumo_cat[df_resumo_cat['valor_liquido'] != 0].set_index('categoria')['valor_liquido']
            if not df_graf.empty:
                st.bar_chart(df_graf)
            else:
                st.info("Sem variações para exibir.")
        else:
            st.info("Sem dados suficientes para gráficos.")

    with col_g2:
        st.markdown("#### 📅 Maiores Despesas do Período")
        df_maiores = df_calculo[df_calculo['tipo'] == 'SAÍDA'].nlargest(5, 'valor')[['data', 'descricao', 'valor', 'categoria']]
        if not df_maiores.empty:
            st.dataframe(df_maiores, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma saída registrada.")

    st.divider()

    # --- DETALHAMENTO EM ÁRVORE LIMPO (SEM HTML QUEBRADO) ---
    st.markdown("### 📂 Detalhamento por Categoria e Estabelecimento")
    df_validos = df_calculo.copy()

    if df_validos.empty:
        st.info("Nenhum lançamento detalhado para este filtro.")
        return

    df_validos['estabelecimento'] = df_validos['descricao'].str.strip().str.upper()
    cats_presentes = sorted([c for c in df_validos['categoria'].unique() if c not in ["Ignorar", "PAGAMENTO FATURA"]])

    for cat in cats_presentes:
        df_cat_itens = df_validos[df_validos['categoria'] == cat]
        t_saidas_cat = df_cat_itens[df_cat_itens['tipo'] == 'SAÍDA']['valor'].sum()
        t_entradas_cat = df_cat_itens[df_cat_itens['tipo'] == 'ENTRADA']['valor'].sum()
        liquido_cat = t_entradas_cat - t_saidas_cat

        sinal_liq = "+" if liquido_cat > 0 else ""
        
        with st.expander(f"📁 {cat} (Líquido: R$ {sinal_liq}{liquido_cat:,.2f})", expanded=False):
            st.markdown(
                f"**Entrou:** :green[R$ {t_entradas_cat:,.2f}] &nbsp;|&nbsp; "
                f"**Saiu:** :red[R$ {t_saidas_cat:,.2f}] &nbsp;|&nbsp; "
                f"**Total:** {len(df_cat_itens)} lançamentos"
            )
            st.divider()

            estabelecimentos = sorted(df_cat_itens['estabelecimento'].unique())
            for estab in estabelecimentos:
                df_estab_itens = df_cat_itens[df_cat_itens['estabelecimento'] == estab]
                t_estab = df_estab_itens['valor'].sum()
                
                with st.expander(f"🔹 {estab} — R$ {t_estab:,.2f} ({len(df_estab_itens)}x)"):
                    for _, row in df_estab_itens.iterrows():
                        data_fmt = pd.to_datetime(row['data']).strftime('%d/%m/%Y') if pd.notna(row['data']) else "Sem data"
                        tipo_cor = ":green[ENTRADA]" if row['tipo'] == 'ENTRADA' else ":red[SAÍDA]"
                        val_formatado = f":green[R$ {row['valor']:,.2f}]" if row['tipo'] == 'ENTRADA' else f":red[R$ {row['valor']:,.2f}]"
                        
                        st.markdown(
                            f"• **Data:** {data_fmt} &nbsp;|&nbsp; "
                            f"**Tipo:** {tipo_cor} &nbsp;|&nbsp; "
                            f"**Valor:** {val_formatado} &nbsp;|&nbsp; "
                            f"**Origem:** `{row['origem']}`"
                        )