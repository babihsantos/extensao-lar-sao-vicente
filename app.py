import os
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
from st_supabase_connection import SupabaseConnection

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Gestão de Doações — Lar São Vicente",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

CATEGORIAS = [
    "Alimentação",
    "Higiene Pessoal",
    "Limpeza",
    "Medicamentos",
    "Vestuário",
    "Outros",
]
DIAS_ALERTA = 30

# Conexão com o banco de dados na nuvem (Supabase)
# O nome "supabase_connection" deve ser o mesmo usado no Secrets
conn = st.connection("supabase_connection", type=SupabaseConnection)

# =========================================================
# CSS PERSONALIZADO
# =========================================================
st.markdown(
    """
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
        .main-header {
            background: linear-gradient(120deg, #2E86AB 0%, #6A4C93 100%);
            padding: 1.4rem 1.8rem; border-radius: 14px; color: #fff;
            box-shadow: 0 4px 14px rgba(0,0,0,0.12); margin-bottom: 1.2rem;
        }
        .main-header h1 { margin: 0; font-size: 1.55rem; font-weight: 700; }
        .main-header p  { margin: .35rem 0 0 0; opacity: .92; font-size: .92rem; }
        [data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 700; }
        [data-testid="stMetricLabel"] { font-size: .85rem; color: #555; }
        .stButton>button, .stDownloadButton>button { border-radius: 8px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# FUNÇÕES DE BANCO DE DADOS (SUPABASE)
# =========================================================
@st.cache_data(ttl=60)
def carregar_inventario() -> pd.DataFrame:
    resposta = conn.table("inventario").select("*").order("categoria").order("item").execute()
    return pd.DataFrame(resposta.data)

@st.cache_data(ttl=60)
def carregar_movimentos() -> pd.DataFrame:
    resposta = conn.table("movimentos").select("*").order("data", desc=True).execute()
    return pd.DataFrame(resposta.data)

def registar_entrada(item, categoria, quantidade, validade, doador):
    validade_str = str(validade) if validade else None
    
    # Busca um item existente com o mesmo nome e validade
    resposta = conn.table("inventario").select("id, quantidade").eq("item", item).eq("validade", validade_str).execute()
    
    if resposta.data:
        # Item já existe: atualiza a quantidade
        item_id = resposta.data[0]['id']
        nova_qtd = resposta.data[0]['quantidade'] + quantidade
        conn.table("inventario").update({"quantidade": nova_qtd}).eq("id", item_id).execute()
    else:
        # Item novo: insere na tabela
        conn.table("inventario").insert({
            "id": str(uuid.uuid4()),
            "item": item.strip(),
            "categoria": categoria,
            "quantidade": quantidade,
            "validade": validade_str,
            "doador": doador.strip() or "Anónimo",
            "data_entrada": datetime.now().isoformat(timespec="seconds")
        }).execute()
    
    # Regista o movimento de entrada
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Entrada",
        "item": item.strip(),
        "categoria": categoria,
        "quantidade": quantidade,
        "pessoa": doador.strip() or "Anónimo",
        "observacoes": "Doação registada"
    }).execute()
    
    st.cache_data.clear()

def dar_baixa(item_id, quantidade, destino, observacoes):
    resposta = conn.table("inventario").select("item, categoria, quantidade").eq("id", item_id).execute()
    if not resposta.data:
        return False, "Item não encontrado."
    
    item = resposta.data[0]['item']
    categoria = resposta.data[0]['categoria']
    stock_atual = resposta.data[0]['quantidade']
    
    if quantidade > stock_atual:
        return False, f"Stock insuficiente (disponível: {stock_atual})."
    
    nova_qtd = stock_atual - quantidade
    if nova_qtd == 0:
        conn.table("inventario").delete().eq("id", item_id).execute()
    else:
        conn.table("inventario").update({"quantidade": nova_qtd}).eq("id", item_id).execute()
    
    # Regista o movimento de saída
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Saída",
        "item": item,
        "categoria": categoria,
        "quantidade": quantidade,
        "pessoa": destino.strip() or "—",
        "observacoes": observacoes.strip() or "Baixa de stock"
    }).execute()
    
    st.cache_data.clear()
    return True, "Baixa registada com sucesso."

def apagar_item(item_id):
    resposta = conn.table("inventario").select("item, categoria, quantidade").eq("id", item_id).execute()
    if not resposta.data:
        return False, "Item não encontrado."
    
    item = resposta.data[0]['item']
    categoria = resposta.data[0]['categoria']
    qtd = resposta.data[0]['quantidade']
    
    conn.table("inventario").delete().eq("id", item_id).execute()
    
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Eliminação",
        "item": item,
        "categoria": categoria,
        "quantidade": qtd,
        "pessoa": "—",
        "observacoes": "Item eliminado do inventário"
    }).execute()
    
    st.cache_data.clear()
    return True, "Item eliminado."

# =========================================================
# GERAÇÃO DE PDF
# =========================================================
@st.cache_resource
def _registar_fonte_unicode():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidatos = [
        ("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("Arial", "C:/Windows/Fonts/arial.ttf"),
    ]
    for nome, caminho in candidatos:
        if os.path.exists(caminho):
            try:
                pdfmetrics.registerFont(TTFont(nome, caminho))
                return nome
            except Exception:
                continue
    return "Helvetica"

def _formatar_celula(valor):
    return "" if pd.isna(valor) else str(valor)

def gerar_pdf(df: pd.DataFrame, titulo: str, subtitulo: str = "") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm, title=titulo)
    fonte = _registar_fonte_unicode()
    estilos = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle("TituloCustom", parent=estilos["Title"], fontName=fonte, fontSize=16, textColor=colors.HexColor("#2E86AB"), spaceAfter=4)
    sub_style = ParagraphStyle("SubCustom", parent=estilos["Normal"], fontName=fonte, fontSize=9, textColor=colors.HexColor("#666666"), spaceAfter=2)

    story = [Paragraph(titulo, titulo_style)]
    if subtitulo: 
        story.append(Paragraph(subtitulo, sub_style))
    story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", sub_style))
    story.append(Spacer(1, 6 * mm))

    if df.empty:
        story.append(Paragraph("Sem dados para apresentar.", sub_style))
    else:
        cols = list(df.columns)
        dados = [cols] + [[_formatar_celula(v) for v in linha] for linha in df.values.tolist()]
        tabela = Table(dados, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), fonte),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd8dc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ]))
        story.append(tabela)

    doc.build(story)
    return buffer.getvalue()

def botao_pdf(df: pd.DataFrame, titulo: str, subtitulo: str, nome_ficheiro: str):
    chave_pdf = f"pdf_bytes_{nome_ficheiro}"
    if st.button("📄 Preparar PDF", key=f"btn_gerar_{nome_ficheiro}", use_container_width=True):
        with st.spinner("Gerando PDF..."):
            st.session_state[chave_pdf] = gerar_pdf(df, titulo, subtitulo)
    if chave_pdf in st.session_state:
        st.download_button(
            "⬇️ Descarregar PDF", 
            data=st.session_state[chave_pdf], 
            file_name=nome_ficheiro, 
            mime="application/pdf", 
            use_container_width=True
        )

# =========================================================
# FUNÇÕES AUXILIARES (HELPERS)
# =========================================================
def calcular_status_validade(validade_str):
    if not validade_str or pd.isna(validade_str): 
        return "Sem validade"
    try: 
        d = pd.to_datetime(validade_str).date()
    except Exception: 
        return "Inválida"
    hoje = date.today()
    if d < hoje: 
        return "Vencido"
    if d <= hoje + timedelta(days=DIAS_ALERTA): 
        return "A vencer"
    return "OK"

def renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    mapa = {
        "item": "Item", "categoria": "Categoria", "quantidade": "Qtd", 
        "validade": "Validade", "doador": "Doador", "data_entrada": "Data Entrada", 
        "data": "Data/Hora", "tipo": "Tipo", "pessoa": "Pessoa", "observacoes": "Observações"
    }
    return df.rename(columns={k: v for k, v in mapa.items() if k in df.columns})

def render_tabela(df: pd.DataFrame):
    if df.empty:
        st.info("Sem registos para mostrar.")
        return
    df_show = df.copy()
    if "validade" in df_show.columns:
        df_show["Estado"] = df_show["validade"].apply(lambda v: calcular_status_validade(v))
    st.dataframe(renomear_colunas(df_show), use_container_width=True, hide_index=True)

# =========================================================
# CABEÇALHO PRINCIPAL
# =========================================================
st.markdown("""
    <div class="main-header">
        <h1>🏥 Sistema de Controlo de Doações e Inventário</h1>
        <p>Lar São Vicente de Paulo — São José do Rio Preto · Projeto de Extensão UNIP</p>
    </div>
""", unsafe_allow_html=True)

# =========================================================
# MENU LATERAL (BARRA LATERAL)
# =========================================================
with st.sidebar:
    # --- ALTERAÇÃO AQUI: Nome mudado para Lar São Vicente ---
    st.markdown("### 🏥 Lar São Vicente")
    
    menu = st.radio(
        "Menu", 
        [
            "📊 Dashboard", 
            "📦 Registar Doação", 
            "🔍 Consultar Inventário", 
            "📤 Dar Baixa / Saída", 
            "⚠️ Alertas de Validade", 
            "🕓 Histórico de Movimentos", 
            "🗑️ Apagar Item"
        ], 
        label_visibility="collapsed"
    )
    st.divider()
    st.caption("💡 Dados guardados na nuvem (Supabase).")
    if st.button("🔄 Recarregar dados", use_container_width=True): 
        st.rerun()

# =========================================================
# 1. DASHBOARD
# =========================================================
if menu == "📊 Dashboard":
    inv = carregar_inventario()
    mov = carregar_movimentos()
    
    if inv.empty:
        st.info("Ainda não há dados. Começa por registar uma doação em **📦 Registar Doação**.")
    else:
        total_unidades = int(inv["quantidade"].sum())
        inv_valid = inv.copy()
        inv_valid["_status"] = inv_valid["validade"].apply(lambda v: calcular_status_validade(v))
        vencidos = int(inv_valid.loc[inv_valid["_status"] == "Vencido", "quantidade"].sum())
        a_vencer = int(inv_valid.loc[inv_valid["_status"] == "A vencer", "quantidade"].sum())

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📦 Unidades em stock", f"{total_unidades:,}".replace(",", "."))
        c2.metric("🏷️ Itens distintos", len(inv))
        c3.metric("📂 Categorias", inv["categoria"].nunique())
        c4.metric("⚠️ A vencer (30d)", a_vencer)
        c5.metric("🚫 Vencidos", vencidos)
        
        st.divider()

        col_a, col_b = st.columns([1.1, 1])
        with col_a:
            st.subheader("📊 Stock por Categoria")
            st.bar_chart(
                inv.groupby("categoria")["quantidade"].sum().sort_values(ascending=False), 
                use_container_width=True
            )
        with col_b:
            st.subheader("🕓 Últimas Movimentações")
            if not mov.empty:
                st.dataframe(
                    renomear_colunas(mov[["data", "tipo", "item", "quantidade", "pessoa"]].head(8)), 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.caption("Sem movimentos registados.")
        
        st.divider()
        
        col_titulo, col_btn = st.columns([3, 1])
        with col_titulo: 
            st.subheader("📋 Inventário Completo")
        with col_btn: 
            botao_pdf(
                renomear_colunas(inv.drop(columns=["id"])), 
                "Inventário Completo", 
                "Lar São Vicente de Paulo", 
                f"inventario_{date.today()}.pdf"
            )
        render_tabela(inv)

# =========================================================
# 2. REGISTAR DOAÇÃO
# =========================================================
elif menu == "📦 Registar Doação":
    st.subheader("📦 Registar Nova Doação ou Entrada")
    
    with st.form("form_doacao", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            item = st.text_input("Nome do Item *", placeholder="Ex.: Leite, Arroz…")
            categoria = st.selectbox("Categoria *", CATEGORIAS)
            quantidade = st.number_input("Quantidade *", min_value=1, step=1, value=1)
        with col2:
            tem_validade = st.checkbox("Este item tem validade?", value=True)
            validade = st.date_input(
                "Data de Validade", 
                value=date.today() + timedelta(days=90), 
                disabled=not tem_validade
            )
            doador = st.text_input("Doador / Origem", placeholder="Nome ou 'Anónimo'")
            
        submitted = st.form_submit_button("💾 Guardar Registo", use_container_width=True)
        
        if submitted:
            if not item.strip(): 
                st.warning("⚠️ Preenche o **Nome do Item**.")
            else:
                registar_entrada(item, categoria, int(quantidade), validade if tem_validade else None, doador)
                st.success(f"✅ '{item}' registado com sucesso!")
                st.balloons()

# =========================================================
# 3. CONSULTAR INVENTÁRIO
# =========================================================
elif menu == "🔍 Consultar Inventário":
    st.subheader("🔍 Consultar Inventário")
    inv = carregar_inventario()
    
    if not inv.empty:
        col1, col2, col3 = st.columns([1.2, 1.5, 1])
        with col1: 
            cat = st.selectbox("Categoria", ["Todas"] + sorted(inv["categoria"].unique()))
        with col2: 
            busca = st.text_input("🔎 Pesquisar por nome ou doador", "")
        with col3: 
            ordem = st.selectbox("Ordenar por", ["Item", "Quantidade", "Validade"])
        
        df = inv.copy()
        if cat != "Todas": 
            df = df[df["categoria"] == cat]
        if busca.strip(): 
            df = df[
                df["item"].str.lower().str.contains(busca.lower(), na=False) | 
                df["doador"].str.lower().str.contains(busca.lower(), na=False)
            ]
        
        # Correção do erro KeyError na ordenação
        mapa_ordem = {"Item": "item", "Quantidade": "quantidade", "Validade": "validade"}
        coluna_ordem = mapa_ordem.get(ordem, "item")
        df = df.sort_values(by=coluna_ordem, ascending=(ordem != "Quantidade"), na_position="last")
        
        render_tabela(df)
        
        if not df.empty:
            col_csv, col_pdf = st.columns(2)
            with col_csv: 
                st.download_button(
                    "⬇️ Exportar CSV", 
                    data=df.to_csv(index=False).encode("utf-8"), 
                    file_name=f"inventario_{date.today()}.csv", 
                    mime="text/csv", 
                    use_container_width=True
                )
            with col_pdf: 
                botao_pdf(
                    renomear_colunas(df.drop(columns=["id"], errors="ignore")), 
                    "Inventário Filtrado", 
                    f"Filtro: {cat}", 
                    f"inventario_{date.today()}.pdf"
                )

# =========================================================
# 4. DAR BAIXA
# =========================================================
elif menu == "📤 Dar Baixa / Saída":
    st.subheader("📤 Registar Saída / Baixa de Stock")
    inv = carregar_inventario()
    
    if not inv.empty:
        opcoes = {
            f"{r['item']} — {r['categoria']} | stock: {r['quantidade']}": r["id"] 
            for _, r in inv.iterrows()
        }
        escolha = st.selectbox("Selecione o item", list(opcoes.keys()))
        item_id = opcoes[escolha]
        stock_max = int(inv.loc[inv["id"] == item_id, "quantidade"].iloc[0])
        
        with st.form("form_baixa"):
            col1, col2 = st.columns(2)
            with col1:
                qtd = st.number_input(
                    "Quantidade a retirar *", 
                    min_value=1, 
                    max_value=stock_max, 
                    value=min(1, stock_max)
                )
                destino = st.text_input("Destino / Beneficiário", placeholder="Ex.: Cozinha")
            with col2: 
                obs = st.text_area("Observações", height=100)
                
            ok = st.form_submit_button("📤 Confirmar Saída", use_container_width=True)
            
            if ok:
                sucesso, msg = dar_baixa(item_id, int(qtd), destino, obs)
                if sucesso: 
                    st.success(f"✅ {msg}")
                    st.rerun()
                else: 
                    st.error(f"❌ {msg}")

# =========================================================
# 5. ALERTAS DE VALIDADE
# =========================================================
elif menu == "⚠️ Alertas de Validade":
    st.subheader("⚠️ Alertas de Validade")
    inv = carregar_inventario()
    
    if not inv.empty:
        df = inv.copy()
        df["_validade_dt"] = pd.to_datetime(df["validade"], errors="coerce").dt.date
        hoje = date.today()
        
        vencidos = df[df["_validade_dt"] < hoje]
        a_vencer = df[
            (df["_validade_dt"] >= hoje) & 
            (df["_validade_dt"] <= hoje + timedelta(days=DIAS_ALERTA))
        ]
        
        c1, c2 = st.columns(2)
        c1.metric("🚫 Vencidos", len(vencidos))
        c2.metric(f"⚠️ A vencer ({DIAS_ALERTA}d)", len(a_vencer))
        st.divider()
        
        if not vencidos.empty: 
            st.error(f"🚫 **{len(vencidos)} lote(s) vencido(s)**")
            render_tabela(vencidos.drop(columns=["_validade_dt"]))
            
        if not a_vencer.empty: 
            st.warning(f"⚠️ **{len(a_vencer)} lote(s) a vencer**")
            render_tabela(a_vencer.drop(columns=["_validade_dt"]))
            
        if vencidos.empty and a_vencer.empty: 
            st.success("✅ Nenhum produto vencido ou a vencer.")

# =========================================================
# 6. HISTÓRICO
# =========================================================
elif menu == "🕓 Histórico de Movimentos":
    st.subheader("🕓 Histórico de Movimentos")
    mov = carregar_movimentos()
    
    if not mov.empty:
        df = mov.copy()
        st.dataframe(
            renomear_colunas(df[["data", "tipo", "item", "categoria", "quantidade", "pessoa", "observacoes"]]), 
            use_container_width=True, 
            hide_index=True
        )
        st.download_button(
            "⬇️ Exportar CSV", 
            data=df.to_csv(index=False).encode("utf-8"), 
            file_name=f"movimentos_{date.today()}.csv", 
            mime="text/csv"
        )

# =========================================================
# 7. APAGAR
# =========================================================
elif menu == "🗑️ Apagar Item":
    st.subheader("🗑️ Apagar Item do Inventário")
    inv = carregar_inventario()
    
    if not inv.empty:
        st.caption("⚠️ Ação irreversível.")
        opcoes = {
            f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']}": r["id"] 
            for _, r in inv.iterrows()
        }
        escolha = st.selectbox("Selecione o item", list(opcoes.keys()))
        confirmar = st.checkbox("Confirmo que quero eliminar este item permanentemente.")
        
        if st.button("🗑️ Eliminar", type="primary", disabled=not confirmar):
            ok, msg = apagar_item(opcoes[escolha])
            if ok: 
                st.success(f"✅ {msg}")
                st.rerun()
            else: 
                st.error(f"❌ {msg}")
                
