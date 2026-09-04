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

        if not api_key or api_key == "SUA_CHAVE_AQUI":
            st.error("A chave da API do Gemini não foi configurada corretamente nos Secrets do Streamlit Cloud.")
        elif not conteudos:
            st.warning("Forneça pelo menos um arquivo válido ou cole o texto.")
        else:
            client = genai.Client(api_key=api_key)
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

                    try:
                        response = None
                        for tentativa in range(4):
                            try:
                                response = client.models.generate_content(
                                    model='models/gemini-3.6-flash', contents=prompt,
                                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ExtratoProcessado, temperature=0.0)
                                )
                                break
                            except Exception as ex:
                                if ("503" in str(ex) or "UNAVAILABLE" in str(ex)) and tentativa < 3:
                                    time.sleep(3)
                                    continue
                                raise ex

                        if response and response.text:
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
                    except Exception as e:
                        st.error(f"Erro ao processar o arquivo {idx + 1}: {e}")

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