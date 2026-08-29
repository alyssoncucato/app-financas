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
    
    arquivo_extrato = st.file_uploader("Faça upload (.csv, .ofx, .txt, .pdf):", type=["csv", "ofx", "txt", "pdf"])
    texto_fatura = st.text_area("Ou cole o texto aqui:", placeholder="Cole as linhas...", height=120)

    if st.button("Processar com IA", type="primary"):
        conteudo = ""
        if arquivo_extrato is not None:
            if arquivo_extrato.name.lower().endswith(".pdf"):
                try:
                    leitor_pdf = pypdf.PdfReader(arquivo_extrato)
                    texto_extraido = ""
                    for pagina in leitor_pdf.pages:
                        texto_extraido += pagina.extract_text() or ""
                    conteudo = texto_extraido
                except Exception as ex_pdf:
                    st.error(f"Erro ao ler o arquivo PDF: {ex_pdf}")
            else:
                conteudo = arquivo_extrato.getvalue().decode("utf-8", errors="ignore")
        elif texto_fatura.strip():
            conteudo = texto_fatura

        if not api_key or api_key == "SUA_CHAVE_AQUI":
            st.error("A chave da API do Gemini não foi configurada corretamente nos Secrets do Streamlit Cloud.")
        elif not conteudo:
            st.warning("Forneça o conteúdo do arquivo ou cole o texto.")
        else:
            with st.spinner("A IA está analisando..."):
                client = genai.Client(api_key=api_key)
                ano_atual = datetime.now().year
                origem_doc = "FATURA_CARTAO" if "Fatura" in tipo_documento else "EXTRATO_CONTA"

                df_regras = pd.read_sql_query(f"SELECT termo_chave, categoria_destino FROM regras_categorias WHERE usuario = '{user}'", conn_fin)
                regras_str = "\n".join([f"- Se contiver '{r['termo_chave']}', use '{r['categoria_destino']}'" for _, r in df_regras.iterrows()])

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
                            # CORRIGIDO para o modelo ativo gemini-3.6-flash
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
                        st.dataframe(pd.DataFrame(itens), use_container_width=True)
                        
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
                        st.success(f"{len(itens)} lançamentos salvos com sucesso no Supabase!")
                    else:
                        st.info("Nenhuma transação válida.")
                except Exception as e:
                    st.error(f"Erro: {e}")