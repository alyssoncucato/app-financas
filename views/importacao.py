import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal
from google import genai
from google.genai import types

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

def render(user, conn_fin, c_fin, todas_categorias):
    st.subheader("Lançar Extrato ou Fatura")
    api_key = st.text_input("Gemini API Key (Google AI Studio)", type="password")
    tipo_documento = st.radio("Tipo de documento:", ["💳 Fatura de Cartão de Crédito", "🏦 Extrato de Conta Corrente / Pix"], horizontal=True)
    arquivo_extrato = st.file_uploader("Faça upload (.csv, .ofx, .txt):", type=["csv", "ofx", "txt"])
    texto_fatura = st.text_area("Ou cole o texto aqui:", placeholder="Cole as linhas...", height=120)

    if st.button("Processar com IA", type="primary"):
        conteudo = ""
        if arquivo_extrato is not None:
            conteudo = arquivo_extrato.getvalue().decode("utf-8", errors="ignore")
        elif texto_fatura.strip():
            conteudo = texto_fatura

        if not api_key or not conteudo:
            st.warning("Forneça a API Key e o conteúdo.")
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
                    response = client.models.generate_content(
                        model='gemini-2.5-flash', contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ExtratoProcessado, temperature=0.0)
                    )
                    dados = json.loads(response.text)
                    itens = [it for it in dados.get("itens", []) if it['categoria'] != "Ignorar"]
                    if itens:
                        st.dataframe(pd.DataFrame(itens), use_container_width=True)
                        for item in itens:
                            c_fin.execute(
                                "INSERT INTO transacoes (usuario, data, descricao, valor, categoria, status_fatura, origem) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (user, item['data'], item['descricao'], item['valor'], item['categoria'], item['status_fatura'], item['origem'])
                            )
                        conn_fin.commit()
                        st.success(f"{len(itens)} lançamentos salvos!")
                    else:
                        st.info("Nenhuma transação válida.")
                except Exception as e:
                    st.error(f"Erro: {e}")