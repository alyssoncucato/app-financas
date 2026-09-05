import streamlit as st
import pandas as pd
import re
from datetime import datetime
from database import engine
from sqlalchemy import text

def parse_ofx(file_content, tipo_origem):
    """Lê arquivos OFX de forma nativa e retorna uma lista de dicionários com as transações."""
    transacoes = []
    try:
        texto = file_content.decode("utf-8", errors="ignore")
        trans_blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', texto, re.DOTALL | re.IGNORECASE)
        
        for bloco in trans_blocks:
            data_match = re.search(r'<DTPOSTED>(\d{8})', bloco, re.IGNORECASE)
            valor_match = re.search(r'<TRNAMT>([-\d\.]+)', bloco, re.IGNORECASE)
            memo_match = re.search(r'<MEMO>(.*?)</MEMO>', bloco, re.IGNORECASE)
            name_match = re.search(r'<NAME>(.*?)</NAME>', bloco, re.IGNORECASE)
            
            if data_match and valor_match:
                dt_str = data_match.group(1)
                data_formatada = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:]}"
                
                valor_raw = float(valor_match.group(1))
                
                desc = "LANÇAMENTO"
                if memo_match:
                    desc = memo_match.group(1).strip()
                elif name_match:
                    desc = name_match.group(1).strip()
                
                if tipo_origem == "FATURA_CARTAO":
                    # Fatura de cartão: o valor costuma vir negativo no OFX (gasto), tratamos como valor absoluto e tipo SAÍDA
                    valor = abs(valor_raw)
                    tipo = "SAÍDA"
                    origem = "FATURA_CARTAO"
                    status_fatura = "ABERTA"
                else:
                    # Extrato de conta corrente
                    valor = abs(valor_raw)
                    tipo = "ENTRADA" if valor_raw > 0 else "SAÍDA"
                    origem = "EXTRATO_CONTA"
                    status_fatura = "CONTA_CORRENTE"
                
                transacoes.append({
                    "data": data_formatada,
                    "descricao": desc.upper(),
                    "valor": valor,
                    "tipo": tipo,
                    "origem": origem,
                    "status_fatura": status_fatura,
                    "categoria": "Não Categorizado"
                })
    except Exception as e:
        st.error(f"Erro ao processar arquivo OFX: {e}")
        
    return transacoes

def render(user, conn_fin, c_fin, todas_categorias):
    st.subheader("📥 Importação Nativa (.OFX / .CSV)")
    st.info("Esta aba lê seus extratos bancários ou faturas de forma 100% matemática, sem consumir cota de Inteligência Artificial.")

    # Seletor para definir se o arquivo é Extrato ou Fatura
    tipo_destino = st.radio(
        "O que você está importando?", 
        ["🏦 Extrato de Conta Corrente / Pix", "💳 Fatura de Cartão de Crédito"], 
        horizontal=True,
        key="radio_tipo_importacao_nat"
    )
    
    origem_escolhida = "FATURA_CARTAO" if "Fatura" in tipo_destino else "EXTRATO_CONTA"

    arquivos = st.file_uploader(
        "Selecione um ou mais arquivos OFX ou CSV:", 
        type=["ofx", "csv"], 
        accept_multiple_files=True, 
        key="uploader_nativo_multiplo"
    )

    if arquivos:
        todas_transacoes_lidas = []
        
        for arquivo in arquivos:
            if arquivo.name.lower().endswith(".ofx"):
                trans_arq = parse_ofx(arquivo.getvalue(), origem_escolhida)
                todas_transacoes_lidas.extend(trans_arq)
            elif arquivo.name.lower().endswith(".csv"):
                try:
                    df_csv = pd.read_csv(arquivo, encoding="utf-8", errors="ignore")
                    st.write(f"Prévia do CSV detectado ({arquivo.name}):", df_csv.head(2))
                    st.warning("Para arquivos CSV, certifique-se de que o formato possui colunas compatíveis.")
                except Exception as e:
                    st.error(f"Erro ao ler CSV {arquivo.name}: {e}")

        if todas_transacoes_lidas:
            df_preview = pd.DataFrame(todas_transacoes_lidas)
            st.success(f"Foram identificadas no total **{len(df_preview)}** transações com destino para: **{'Cartão de Crédito' if origem_escolhida == 'FATURA_CARTAO' else 'Conta Corrente'}**.")
            
            st.markdown("### Prévia dos Lançamentos:")
            st.dataframe(df_preview, use_container_width=True)

            if st.button("💾 Salvar Lançamentos no Banco", type="primary"):
                user_str = str(user).strip()
                salvos = 0
                duplicados = 0

                with engine.connect() as connection:
                    try:
                        df_existentes = pd.read_sql_query(
                            text("SELECT data, descricao, valor, origem FROM transacoes WHERE usuario = :u"),
                            connection,
                            params={"u": user_str}
                        )
                    except Exception:
                        df_existentes = pd.DataFrame()

                    for item in todas_transacoes_lidas:
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
                            connection.commit()
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

                st.success(f"Processo finalizado! **{salvos}** novos lançamentos salvos com sucesso. *({duplicados} repetidos ignorados)*.")
                st.rerun()