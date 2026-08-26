import streamlit as st
import pandas as pd

def render(user, conn_fin, c_fin, get_param, set_param):
    st.subheader("⚙️ Configurações e Perfil")

    # --- SEÇÃO DE EDITAR PERFIL ---
    st.write("#### 👤 Meu Perfil")
    user_data = c_fin.execute(f"SELECT email, senha, foto FROM usuarios WHERE username = '{user}'").fetchone()
    email_atual = user_data[0] if user_data and user_data[0] else ""
    senha_atual = user_data[1] if user_data and user_data[1] else ""
    foto_atual = user_data[2] if user_data and user_data[2] else ""

    col_f1, col_f2 = st.columns([1, 4])
    with col_f1:
        if foto_atual:
            st.image(foto_atual, width=80)
        else:
            st.markdown("📷 *Sem foto*")
    
    with col_f2:
        with st.form("form_perfil"):
            novo_email = st.text_input("E-mail vinculado:", value=email_atual)
            nova_senha = st.text_input("Nova Senha (deixe em branco para manter):", type="password", value="")
            nova_foto_url = st.text_input("Link da Foto de Perfil (URL da imagem):", value=foto_atual)
            
            if st.form_submit_button("💾 Salvar Alterações de Perfil", type="primary"):
                s_final = nova_senha.strip() if nova_senha.strip() else senha_atual
                c_fin.execute(f"UPDATE usuarios SET email = '{novo_email.strip()}', senha = '{s_final}', foto = '{nova_foto_url.strip()}' WHERE username = '{user}'")
                st.success("Perfil atualizado com sucesso!")
                st.rerun()

    st.divider()

    # --- SEÇÃO DE ABAS VISÍVEIS ---
    st.write("#### 🗂️ Gerenciar Abas Visíveis")
    st.caption("Escolha quais módulos extras você deseja exibir no seu menu superior:")

    padrao_ativado = "1" if user == "alysson" else "0"
    
    ativ_divida = st.checkbox("📌 Dívida Fixa", value=get_param(user, "ativ_divida", padrao_ativado) == "1")
    ativ_casa = st.checkbox("❤️ Casa / Financiamento", value=get_param(user, "ativ_casa", padrao_ativado) == "1")
    ativ_extra = st.checkbox("🏠 Extra Casa", value=get_param(user, "ativ_extra", padrao_ativado) == "1")
    ativ_projetos = st.checkbox("🚗 Projetos e Reformas", value=get_param(user, "ativ_projetos", padrao_ativado) == "1")

    if st.button("Salvar Preferências de Abas"):
        set_param(user, "ativ_divida", "1" if ativ_divida else "0")
        set_param(user, "ativ_casa", "1" if ativ_casa else "0")
        set_param(user, "ativ_extra", "1" if ativ_extra else "0")
        set_param(user, "ativ_projetos", "1" if ativ_projetos else "0")
        st.success("Preferências salvas! Atualizando menu...")
        st.rerun()

    st.divider()
    st.write("#### 💾 Backup dos Dados (Supabase)")
    st.caption("Baixe um backup com todas as suas transações e dados salvos na nuvem em formato CSV:")

    try:
        # Puxa os dados do banco para gerar o CSV de backup em tempo real
        df_transacoes = pd.read_sql_query(f"SELECT * FROM transacoes WHERE usuario = '{user}'", conn_fin)
        csv_data = df_transacoes.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            "📥 Baixar Backup de Transações (.csv)", 
            data=csv_data, 
            file_name=f"backup_transacoes_{user}.csv", 
            mime="text/csv", 
            type="secondary"
        )
    except Exception as e:
        st.info("Ainda não há transações para exportar.")

    st.divider()
    df_regras = pd.read_sql_query(f"SELECT id, termo_chave AS \"Termo\", categoria_destino AS \"Categoria\" FROM regras_categorias WHERE usuario = '{user}'", conn_fin)
    if not df_regras.empty:
        st.dataframe(df_regras, use_container_width=True)