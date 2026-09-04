import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal
from google import genai
from google.genai import types
from database import engine
from sqlalchemy import text
import pypdf

class Transacao(BaseModel):
    data: str = Field(description="Data no formato YYYY-MM-DD")
    descricao: str = Field(description="Nome do estabelecimento, recebedor ou pagador")
    valor: float = Field(description="Valor numérico absoluto")
    categoria: str = Field(description="Categoria da despesa ou ganho")
    tipo: Literal["ENTRADA", "SAÍDA"] = Field(description="ENTRADA se o dinheiro entrou/foi recebido/crédito. SAÍDA se o dinheiro saiu/foi gasto/pagamento/débito.")
    status_fatura: Literal["ABERTA", "FECHADA", "CONTA_CORRENTE"]
    origem: Literal["FATURA_CARTAO", "EXTRATO_CONTA"]

class ExtratoProcessado(BaseModel):
    itens: List[Transacao]

def render(user, conn_fin, c_fin, todas_categorias, api_key):
    st.subheader("Lançar Extrato ou Fatura")

    tipo_documento = st.radio("Tipo de documento:", ["💳 Fatura de Cartão de Crédito", "🏦 Extrato de Conta Corrente / Pix"], horizontal=True)
    
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

    arquivos_extrato = st.file_uploader(
        "Faça upload de um ou mais arquivos (.csv, .ofx, .txt, .pdf):", 
        type=["csv", "ofx", "txt", "pdf"], 
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}"
    )
    texto_fatura = st.text_area("Ou cole o texto aqui:", placeholder="Cole as linhas...", height=120)

    if st.button("Processar com IA", type="primary"):
        conteudos = []
        
        if arquivos_extrato:
            for arq in arquivos_extrato:
                if arq.name.lower().endswith(".pdf"):
                    try:
                        leitor_pdf = pypdf.PdfReader(arq)
                        texto_extraido = ""
                        for pagina in leitor_pdf.pages:
                            texto_extraido += pagina.extract_text() or ""
                        if texto_extraido.strip():
                            conteudos.append(texto_extraido)
                    except Exception as ex_pdf:
                        st.error(f"Erro ao ler o arquivo PDF {arq.name}: {ex_pdf}")
                else:
                    texto_txt = arq.getvalue().decode("utf-8", errors="ignore")
                    if texto_txt.strip():
                        conteudos.append(texto_txt)
        elif texto_fatura.strip():
            conteudos.append(texto_fatura)

        # Configura a lista de chaves (a principal dos Secrets + a nova que você mandou)
        chaves_disponiveis = [
            api_key, 
            "AQ.Ab84296LpjhIWvPe4njMTJDqtEVeBh_ElQj63BBrBv3ptcGlKBg" # Substitua ou ajuste conforme sua segunda chave completa se necessário
        ]
        # Remove chaves inválidas ou vazias
        chaves_validas = [k.strip() for k in chaves_disponiveis if k and k != "SUA_CHAVE_AQUI"]

        if not chaves_validas:
            st.error("Nenhuma chave de API do Gemini foi configurada corretamente.")
        elif not conteudos:
            st.warning("Forneça pelo menos um arquivo válido ou cole o texto.")
        else:
            ano_atual = datetime.now().year
            origem_doc = "FATURA_CARTAO" if "Fatura" in tipo_documento else "EXTRATO_CONTA"
            user_str = str(user).strip()

            regras_str = ""
            try:
                with engine.connect() as conn_r:
                    df_regras = pd.read_sql_query(
                        text("SELECT termo_chave, categoria_destino FROM regras_categorias WHERE LOWER(usuario) = LOWER(:u)"), 
                        conn_r, 
                        params={"u": user_str}
                    )
                if df_regras is not None and not df_regras.empty:
                    regras_str = "\n".join([f"- Se contiver '{r['termo_chave']}', use '{r['categoria_destino']}'" for _, r in df_regras.iterrows()])
            except Exception:
                regras_str = ""

            total_itens_salvos = 0
            total_itens_duplicados = 0
            todos_itens_exibicao = []

            for idx, conteudo in enumerate(conteudos):
                with st.spinner(f"A IA está analisando o documento {idx + 1} de {len(conteudos)}..."):
                    prompt = f"""
                    Ano: {ano_atual}. Tipo de Origem: {origem_doc}.
                    {regras_str}
                    INSTRUÇÃO CRÍTICA SOBRE O TIPO (OBRIGATÓRIO):
                    - Analise se a transação representa entrada de dinheiro (PIX recebido, depósito, transferência recebida, salário, crédito) -> defina como 'ENTRADA'.
                    - Analise se a transação representa saída de dinheiro (compra, pagamento, débito, tarifa, saque) -> defina como 'SAÍDA'.
                    O tipo depende EXCLUSIVAMENTE da natureza da movimentação no extrato, independentemente da categoria escolhida.
                    IGNORAR: Pagamento de fatura anterior, transferências entre contas do mesmo titular, resgate RDB, Pix no Crédito.
                    CATEGORIAS DISPONÍVEIS: {', '.join(todas_categorias)}
                    Conteúdo:
                    {conteudo}
                    """

                    response = None
                    sucesso_requisicao = False

                    # Tenta rodar a IA fazendo rotação automática entre as chaves em caso de erro 429 (cota esgotada)
                    for chave_atual in chaves_validas:
                        try:
                            client = genai.Client(api_key=chave_atual)
                            
                            for tentativa in range(3):
                                try:
                                    response = client.models.generate_content(
                                        model='models/gemini-3.6-flash', contents=prompt,
                                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ExtratoProcessado, temperature=0.0)
                                    )
                                    if response and response.text:
                                        sucesso_requisicao = True
                                        break
                                except Exception as ex_tentativa:
                                    if ("503" in str(ex_tentativa) or "UNAVAILABLE" in str(ex_tentativa)) and tentativa < 2:
                                        time.sleep(2)
                                        continue
                                    raise ex_tentativa

                            if sucesso_requisicao:
                                break # Passou com essa chave, sai do loop de chaves
                        except Exception as ex_chave:
                            # Se estourou a cota (429), tenta a próxima chave da lista
                            if "429" in str(ex_chave) or "RESOURCE_EXHAUSTED" in str(ex_chave):
                                continue
                            else:
                                # Outro erro qualquer, exibe e para
                                st.error(f"Erro na IA (Arquivo {idx + 1}): {ex_chave}")
                                break

                    if sucesso_requisicao and response and response.text:
                        try:
                            dados = json.loads(response.text)
                            itens = [it for it in dados.get("itens", []) if it['categoria'] != "Ignorar"]
                            
                            if itens:
                                with engine.connect() as connection:
                                    df_existentes = pd.read_sql_query(
                                        text("SELECT data, descricao, valor, origem FROM transacoes WHERE LOWER(usuario) = LOWER(:u)"),
                                        connection,
                                        params={"u": user_str}
                                    )

                                    for item in itens:
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
                                                    "tp": item.get('tipo', 'SAÍDA')
                                                }
                                            )
                                            connection.commit()
                                            total_itens_salvos += 1
                                            todos_itens_exibicao.append(item)
                                            
                                            df_existentes = pd.concat([df_existentes, pd.DataFrame([{
                                                "data": item['data'],
                                                "descricao": item['descricao'],
                                                "valor": item['valor'],
                                                "origem": item['origem']
                                            }])], ignore_index=True)
                                        else:
                                            total_itens_duplicados += 1
                        except Exception as e_parse:
                            st.error(f"Erro ao salvar dados do arquivo {idx + 1}: {e_parse}")
                    elif not sucesso_requisicao:
                        st.error(f"Todas as chaves de API falharam ou atingiram a cota no arquivo {idx + 1}.")

            if todos_itens_exibicao or total_itens_duplicados > 0:
                if todos_itens_exibicao:
                    st.dataframe(pd.DataFrame(todos_itens_exibicao), use_container_width=True)
                
                msg = f"Processamento concluído! **{total_itens_salvos}** novos lançamentos salvos."
                if total_itens_duplicados > 0:
                    msg += f" *({total_itens_duplicados} itens repetidos foram ignorados automaticamente para evitar duplicação)*."
                
                st.success(msg)
                
                st.session_state.uploader_key += 1
                time.sleep(2.0)
                st.rerun()
            else:
                st.info("Nenhuma transação nova ou válida encontrada nos documentos fornecidos.")