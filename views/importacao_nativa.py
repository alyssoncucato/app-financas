import streamlit as st
import pandas as pd
import re
from datetime import datetime
from database import engine
from sqlalchemy import text

def parse_ofx(file_content, tipo_origem):
    """Lê arquivos OFX de forma matemática e classifica entradas e saídas corretamente."""
    transacoes = []
    try:
        texto = file_content.decode("utf-8", errors="ignore")
        trans_blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', texto, re.DOTALL | re.IGNORECASE)
        
        for bloco in trans_blocks:
            data_match = re.search(r'<DTPOSTED>(\d{8})', bloco, re.IGNORECASE)
            valor_match = re.search(r'<TRNAMT>([-\d\.]+)', bloco, re.IGNORECASE)
            memo_match = re.search(r'<MEMO>(.*?)</MEMO>', bloco, re.IGNORECASE)
            name_match = re.search(r'<NAME>(.*?)</NAME>', bloco, re.IGNORECASE)
            trntype_match = re.search(r'<TRNTYPE>(.*?)<', bloco, re.IGNORECASE)
            
            if data_match and valor_match:
                dt_str = data_match.group(1)
                data_formatada = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:]}"
                
                valor_raw = float(valor_match.group(1))
                tipo_trn = trntype_match.group(1).upper() if trntype_match else ""
                
                desc = "LANÇAMENTO"
                if memo_match:
                    desc = memo_match.group(1).strip()
                elif name_match:
                    desc = name_match.group(1).strip()
                
                desc_upper = desc.upper()

                if tipo_origem == "FATURA_CARTAO":
                    origem = "FATURA_CARTAO"
                    status_fatura = "ABERTA"
                    
                    # Se for crédito na fatura (pagamento da fatura recebido ou estorno de compra)
                    if valor_raw > 0 or tipo_trn == "CREDIT" or "PAGAMENTO RECEBIDO" in desc_upper:
                        valor = abs(valor_raw)
                        tipo = "ENTRADA"
                        categoria = "PAGAMENTO FATURA" if "PAGAMENTO RECEBIDO" in desc_upper else "Estorno"
                    else:
                        valor = abs(valor_raw)
                        tipo = "SAÍDA"
                        categoria = "Não Categorizado"
                else:
                    # Extrato de conta corrente
                    origem = "EXTRATO_CONTA"
                    status_fatura = "CONTA_CORRENTE"
                    valor = abs(valor_raw)
                    tipo = "ENTRADA" if valor_raw > 0 else "SAÍDA"
                    
                    # Ignora aplicações ou resgates de RDB (apenas movimentação interna de caixinha)
                    if "APLICAÇÃO RDB" in desc_upper or "RESGATE RDB" in desc_upper:
                        categoria = "Ignorar"
                    elif "PAGAMENTO DE FATURA" in desc_upper:
                        categoria = "PAGAMENTO FATURA"
                    else:
                        categoria = "Não Categorizado"
                
                transacoes.append({
                    "data": data_formatada,
                    "descricao": desc_upper,
                    "valor": valor,
                    "tipo": tipo,
                    "origem": origem,
                    "status_fatura": status_fatura,
                    "categoria": categoria
                })
    except Exception as e:
        st.error(f"Erro ao processar arquivo OFX: {e}")
        
    return transacoes

def render(user, conn_fin, c_fin, todas_categorias):
    st.subheader("📥 Importação Nativa (.OFX / .CSV)")
    st.info("Esta aba lê seus extratos bancários ou faturas de forma 100% matemática, sem consumir cota de IA.")

    with st.form("form_importacao_nativa"):
        tipo_destino = st.radio(
            "O que você está importando?", 
            ["🏦 Extrato de Conta Corrente / Pix", "💳 Fatura de Cartão de Crédito"], 
            horizontal=True,
            key="radio_tipo_importacao_nat"
        )
        
        arquivos = st.file_uploader(
            "Selecione um ou mais arquivos OFX:", 
            type=["ofx"], 
            accept_multiple_files=True, 
            key="uploader_nativo_multiplo"
        )
        
        btn_ler = st.form_submit_button("🔍 Carregar e Analisar Arquivos", type="primary")

    origem_escolhida = "FATURA_CARTAO" if "Fatura" in tipo_destino else "EXTRATO_CONTA"

    if arquivos and btn_ler:
        todas_transacoes_lidas = []
        for arquivo in arquivos:
            if arquivo.name.lower().endswith(".ofx"):
                trans_arq = parse_ofx(arquivo.getvalue(), origem_escolhida)
                todas_transacoes_lidas.extend(trans_arq)

        if todas_transacoes_lidas:
            st.session_state.transacoes_pendentes_salvar = todas_transacoes_lidas
            st.session_state.origem_pendente = origem_escolhida

    if "transacoes_pendentes_salvar" in st.session_state and st.session_state.transacoes_pendentes_salvar:
        itens_pendentes = st.session_state.transacoes_pendentes_salvar
        df_preview = pd.DataFrame(itens_pendentes)
        
        st.success(f"Foram identificadas **{len(df_preview)}** transações prontas para gravação.")
        st.dataframe(df_preview, use_container_width=True)

        if st.button("💾 Gravar Todos os Lançamentos no Banco", type="primary"):
            user_str = str(user).strip()
            salvos = 0
            duplicados = 0

            with engine.connect() as connection:
                try:
                    df_existentes = pd.read_sql_query(
                        text("SELECT data, descricao, valor, origem FROM transacoes WHERE LOWER(usuario) = LOWER(:u)"),
                        connection,
                        params={"u": user_str}
                    )
                except Exception:
                    df_existentes = pd.DataFrame()

                for item in itens_pendentes:
                    duplicado = False
                    if df_existentes is not None and not df_existentes.empty and 'descricao' in df_existentes.columns:
                        try:
                            match = df_existentes[
                                (df_existentes['data'].astype(str).str.strip() == str(item['data']).strip()) &
                                (df_existentes['descricao'].astype(str).str.strip().str.lower() == str(item['descricao']).strip().lower()) &
                                (abs(df_existentes['valor'].astype(float) - float(item['valor'])) < 0.01) &
                                (df_existentes['origem'].astype(str).str.strip() == str(item['origem']).strip())
                            ]
                            if not match.empty:
                                duplicado = True
                        except Exception:
                            pass

                    if not duplicado:
                        connection.execute(
                            text("""
                                INSERT INTO transacoes (usuario, data, descricao, valor, categoria, status_fatura, origem, tipo) 
                                VALUES (:u, :d, :desc, :v, :cat, :sf, :orig, :tp)
                            """),
                            {
                                "u": user_str,
                                "d": str(item['data']),
                                "desc": str(item['descricao']),
                                "v": float(item['valor']),
                                "cat": str(item['categoria']),
                                "sf": str(item['status_fatura']),
                                "orig": str(item['origem']),
                                "tp": str(item['tipo'])
                            }
                        )
                        salvos += 1
                        novo_df = pd.DataFrame([{
                            "data": item['data'],
                            "descricao": item['descricao'],
                            "valor": item['valor'],
                            "origem": item['origem']
                        }])
                        df_existentes = pd.concat([df_existentes, novo_df], ignore_index=True)
                    else:
                        duplicados += 1
                
                connection.commit()

            st.session_state.transacoes_pendentes_salvar = []
            st.success(f"Finalizado! **{salvos}** salvos e **{duplicados}** repetidos ignorados.")
            st.rerun()