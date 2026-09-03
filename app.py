# --- CATEGORIAS PADRÃO E PERSONALIZADAS ---
CATEGORIAS_PADRAO = [
    "Casa", "Alimentação Rua", "Alimentação Casa", "Carro", "Gasolina",
    "Saúde", "Educação", "Lazer", "Investimento", "Dívidas", "Compras", "Não sei"
]

# Busca categorias customizadas do usuário no banco (salvas como parâmetro)
cats_salvas_str = get_param(user, "categorias_personalizadas", "")
if cats_salvas_str:
    # Se houver salvas, usa elas combinando com as padrão sem duplicar
    extras = [c.strip() for c in cats_salvas_str.split(",") if c.strip()]
    CATEGORIAS_DESPESAS = sorted(list(set(CATEGORIAS_PADRAO + extras)))
else:
    CATEGORIAS_DESPESAS = CATEGORIAS_PADRAO

TODAS_CATEGORIAS = CATEGORIAS_DESPESAS + ["Ganhos Fixos", "Ganhos Variáveis", "Ignorar"]