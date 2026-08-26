if itens:
                        st.dataframe(pd.DataFrame(itens), use_container_width=True)
                        
                        # Salva de forma segura utilizando transação direta do SQLAlchemy / Supabase
                        from database import engine
                        from sqlalchemy import text
                        
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