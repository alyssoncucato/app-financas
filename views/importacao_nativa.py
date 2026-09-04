import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
from database import engine
from sqlalchemy import text

def parse_ofx(file_content):
    """Lê arquivos OFX de forma nativa e retorna uma lista de dicionários com as transações."""
    transacoes = []
    try:
        # Tenta limpar o OFX para formato XML válido ou extrai via tags STMTTRN
        texto = file_content.decode("utf-8", errors="ignore")
        
        # O padrão OFX usa tags <STMTTRN> para cada transação
        import re
        trans_blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', texto, re.DOTALL | re.IGNORECASE)
        
        for bloco in trans_blocks:
            # Extrai os campos básicos usando Regex
            tipo_match = re.search(r'<TRNTYPE>(.*?)</TRNTYPE>', bloco, re.IGNORECASE)
            data_match = re.search(r'<DTPOSTED>(\d{8})', bloco, re.IGNORECASE)
            valor_match = re.search(r'<TRNAMT>([-\d\.]+)', bloco, re.IGNORECASE)
            memo_match = re.search(r'<MEMO>(.*?)</MEMO>', bloco, re.IGNORECASE)
            name_match = re.search(r'<NAME>(.*?)</NAME>', bloco, re.IGNORECASE)
            
            if data_match and valor_match:
                dt_str = data_match.group(1) # Formato YYYYMMDD
                data_formatada = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:]}"
                
                valor = float(valor_match.group(1))
                
                # Descrição prioriza MEMO, depois NAME, senão genérico
                desc = "LANÇAMENTO BANCÁRIO"
                if memo_match:
                    desc = memo_match.group(1).strip()
                elif name_match:
                    desc = name_match.group(1).strip()
                
                # Determina Entrada ou Saída com base no sinal do valor do OFX
                tipo = "ENTRADA" if valor > 0 else "SAÍDA"
                
                transacoes.append({
                    "data": data_formatada,
                    "descricao": desc.upper(),
                    "valor": abs(valor), # Valor absoluto para o banco
                    "tipo": tipo,
                    "origem": "EXTRATO_CONTA",
                    "status_fatura": "CONTA_CORRENTE",
                    "categoria": "Não Categorizado" # Categoria padrão inicial
                })
    except Exception as e:
        st.error(f"Erro ao processar arquivo OFX: {e}")
        
    return transacoes

def render(user, conn_fin, c_fin, todas_categorias):
    st.subheader("📥 Importação Nativa (.OFX / .CSV)")
    st.info("Esta aba lê seus extratos bancários de forma 100% matemática, sem consumir cota de Inteligência Artificial.")

    arquivo = st.file_uploader("Selecione o arquivo OFX ou CSV do banco:", type=["ofx", "csv"], key="uploader_nativo")

    if arquivo is not None:
        transacoes_lidas = []
        
        if arquivo.name.lower().endswith(".ofx"):
            transacoes_lidas = parse_ofx(arquivo.getvalue())
        elif arquivo.name.lower().endswith(".csv"):
            try:
                df_csv = pd.read_csv(arquivo, encoding="utf-8", errors="ignore")
                st.write("Prévia do CSV detectado:", df_csv.head(2))
                st.warning("Para arquivos CSV, certifique-se de que o formato possui colunas de Data, Descrição e Valor.")
            except Exception as e:
                st.error(f"Erro ao ler CSV: {e}")

        if transacoes_lidas:
            df_preview = pd.DataFrame(transacoes_lidas)
            st.success(f"Foram identificadas **{len(df_preview)}** transações no arquivo.")
            
            # Permite ajustar categorias rapidamente se quiser antes de salvar
            st.markdown("### Prévia dos Lançamentos:")
            st.dataframe(df_preview, use_container_width=True)

            if st.button("💾 Salvar Lançamentos no Banco", type="primary"):
                user_str = str(user).strip()
                salvos = 0
                duplicados = 0

                with engine.connect() as connection:
                    df_existentes = pd.read_sql_query(
                        text("SELECT data, descricao, valor, origem FROM transacoes WHERE usuario = :u"),
                        connection,
                        params={"u": user_str}
                    )

                    for item in transacoes_lidas:
                        duplicado = False
                        if df_existentes is not None and not df_existentes.empty:
                            match = df_existentes[
                                (df_existentes['data'].astype(str).str.strip() == str(item['data']).strip()) &
                                (df_existentes['descricao'].astype(str).str.strip().lower() == str(item['descricao']).strip().lower()) &
                                (abs(df_existentes['valor'] - float(item['valor'])) < 0.01) &
                                (df_existentes['origem'].astype(str).str.strip() == str(item['origem']).strip())
                            ]
                            if not match.empty:
                                duplicado = True

                        if not duplicado:
                            connection.execute(
                                text("""
                                    INSERT INTO transacoes (usuario, data, descricao, valor, categoria, status_fatura, origem, tipo) 
                                    VALUES (:u, :d, :desc, :v, :cat, :sf, :orig, :tp)
                                """),
                                {
                                    "u": user_str,
                                    "d": item['data'],
                                    "desc": item['descricao'],
                                    "v": item['valor'],
                                    "cat": item['categoria'],
                                    "sf": item['status_fatura'],
                                    "orig": item['origem'],
                                    "tp": item['tipo']
                                }
                            )
                            connection.commit()
                            salvos += 1
                            
                            # Atualiza o dataframe local para evitar duplicatas no mesmo lote
                            df_existentes = pd.concat([df_existentes, pd.DataFrame([{
                                "data": item['data'],
                                "descricao": item['descricao'],
                                "valor": item['valor'],
                                "origem": item['origem']
                            }])], ignore_index=True)
                        else:
                            duplicados += 1

                st.success(f"Processo finalizado! **{salvos}** novos lançamentos salvos com sucesso. *({duplicados} repetidos ignorados)*.")
                st.rerun()