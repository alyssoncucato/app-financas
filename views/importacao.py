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
    valor: float = Field(description="Valor numérico")
    categoria: Literal[
        "Casa", "Alimentação Rua", "Alimentação Casa", "Carro", "Gasolina", 
        "Saúde", "Educação", "Lazer", "Investimento", "Dívidas", "Compras", 
        "Não sei", "Ganhos Fixos", "Ganhos Variáveis", "Ignorar"
    ]
    status_fatura: Literal["ABERTA", "FECHADA", "CONTA_CORRENTE"]
    origem: Literal["FATURA_CARTAO", "EXTRATO_CONTA"]

class ExtratoProcessado(BaseModel):
    itens: List[Transacao]

def render(user, conn_fin, c_fin, todas_categorias, api_key):
    st.subheader("Lançar Extrato ou Fatura")

    tipo_documento = st.radio("Tipo de documento:", ["💳 Fatura de Cartão de Crédito", "🏦 Extrato de Conta Corrente / Pix"], horizontal=True)
    
    # Usamos uma chave no file_uploader para permitir limpar o componente programaticamente
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

            df_regras = pd.read_sql_query(f"SELECT termo_chave, categoria_destino FROM regras_categorias WHERE usuario = '{user}'", conn_fin)
            regras_str = "\n".join([f"- Se contiver '{r['termo_chave']}', use '{r['categoria_destino']}'" for _, r in df_regras.iterrows()])

            total_itens_salvos = 0
            todos_itens_exibicao = []

            for idx, conteudo in enumerate(conteudos):
                with st.spinner(f"A IA está analisando o documento {idx + 1} de {len(conteudos)}..."):
                    prompt = f"""
                    Ano: {ano_atual}. Tipo: {origem_doc}.
                    {regras_str}
                    IGNORAR: Pagamento de fatura anterior, transferências entre contas do mesmo titular, resgate RDB, Pix no Crédito.
                    CATEGORIAS: {', '.join(todas_categorias)}
                    Conteúdo:
                    {conteudo}
                    """

                    try:
                        response = None
                        for tentativa in range(3):
                            try:
                                response = client.models.generate_content(
                                    model='models/gemini-3.6-flash', contents=prompt,
                                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ExtratoProcessado, temperature=0.0)
                                )
                                break
                            except Exception as ex:
                                if "503" in str(ex) and tentativa < 2:
                                    time.sleep(2)
                                    continue
                                raise ex

                        dados = json.loads(response.text)
                        itens = [it for it in dados.get("itens", []) if it['categoria'] != "Ignorar"]
                        
                        if itens:
                            todos_itens_exibicao.extend(itens)
                            with engine.connect() as connection:
                                with connection.begin():
                                    for item in itens:
                                        connection.execute(
                                            text("""
                                                INSERT INTO transacoes (usuario, data, descricao, valor, categoria, status_fatura, origem) 
                                                VALUES (:u, :d, :desc, :v, :cat, :sf, :orig)
                                            """),
                                            {
                                                "u": user,
                                                "d": item['data'],
                                                "desc": item['descricao'],
                                                "v": item['valor'],
                                                "cat": item['categoria'],
                                                "sf": item['status_fatura'],
                                                "orig": item['origem']
                                            }
                                        )
                                        total_itens_salvos += 1
                    except Exception as e:
                        st.error(f"Erro ao processar o arquivo {idx + 1}: {e}")

            if todos_itens_exibicao:
                st.dataframe(pd.DataFrame(todos_itens_exibicao), use_container_width=True)
                st.success(f"Processamento concluído! Total de {total_itens_salvos} lançamentos salvos com sucesso no Supabase.")
                
                # Incrementa a chave para limpar automaticamente o file_uploader e recarrega a tela
                st.session_state.uploader_key += 1
                time.sleep(1.5)
                st.rerun()
            else:
                st.info("Nenhuma transação válida encontrada nos documentos fornecidos.")