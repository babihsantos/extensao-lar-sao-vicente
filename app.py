import os
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_supabase_connection import SupabaseConnection

# =========================================================
# CONFIGURAÇÃO
# =========================================================
st.set_page_config(
    page_title="EstocaPro — Lar São Vicente",
    page_icon="📦",
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

conn = st.connection("supabase_connection", type=SupabaseConnection)

# =========================================================
# CSS — LAYOUT ESTOCAPRO
# =========================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

    .stApp { background: #f1f5f9; }
    .block-container { padding: 1rem 2.2rem 2.4rem 2.2rem; max-width: 1500px; }

    header[data-testid="stHeader"] { background: transparent; height: 0; }
    #MainMenu, footer { visibility: hidden; }

    /* ===================== SIDEBAR ===================== */
    [data-testid="stSidebar"] {
        background: #0b1220;
        border-right: none;
        min-width: 268px;
    }
    [data-testid="stSidebar"] > div { background: #0b1220; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .15rem; }

    .sidebar-logo {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 8px 26px 8px;
    }
    .logo-icon {
        width: 40px; height: 40px;
        background: linear-gradient(135deg, #10b981, #059669);
        border-radius: 11px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.15rem;
        box-shadow: 0 6px 16px rgba(16,185,129,.35);
    }
    .logo-title { color: #fff; font-weight: 700; font-size: 1.08rem; line-height: 1.1; letter-spacing: -.2px; }
    .logo-sub { color: #64748b; font-size: .72rem; margin-top: 3px; }

    /* Nav radio como itens */
    [data-testid="stSidebar"] [role="radiogroup"] { gap: 3px; }
    [data-testid="stSidebar"] [role="radiogroup"] > label {
        padding: 10px 14px !important;
        border-radius: 10px;
        margin: 1px 0;
        color: #94a3b8 !important;
        font-weight: 500;
        font-size: .9rem;
        transition: all .15s ease;
        cursor: pointer;
        width: 100%;
    }
    [data-testid="stSidebar"] [role="radiogroup"] > label:hover {
        background: #16202f;
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child { display: none; }
    [data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(90deg, #065f46 0%, #059669 100%);
        color: #fff !important;
        box-shadow: 0 6px 16px rgba(5,150,105,.28);
    }

    /* Cartão de status */
    .status-card {
        background: #101a2c;
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 14px 16px;
        margin-top: 26px;
    }
    .status-row {
        color: #10b981; font-weight: 600; font-size: .85rem;
        display: flex; align-items: center; gap: 8px;
    }
    .status-row .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: #10b981; box-shadow: 0 0 10px #10b981;
    }
    .status-sub { color: #64748b; font-size: .72rem; margin-top: 8px; line-height: 1.55; }

    /* ===================== TOP BAR ===================== */
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] > div {
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        background: #fff !important;
        font-size: .9rem !important;
    }
    .topbar-user {
        display: flex; justify-content: flex-end; align-items: center;
        gap: 14px; padding-top: 2px;
    }
    .bell { position: relative; font-size: 1.25rem; }
    .bell::after {
        content: ""; position: absolute; top: -1px; right: -1px;
        width: 8px; height: 8px; background: #ef4444;
        border-radius: 50%; border: 2px solid #f1f5f9;
    }
    .avatar {
        width: 38px; height: 38px; border-radius: 50%;
        background: #0f172a; color: #fff;
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: .9rem;
    }
    .user-name { font-weight: 600; font-size: .85rem; color: #0f172a; line-height: 1.1; }
    .user-role { font-size: .72rem; color: #94a3b8; }

    /* ===================== HEADER PÁGINA ===================== */
    .page-title { font-size: 1.65rem; font-weight: 700; color: #0f172a; margin: 0; letter-spacing: -.3px; }
    .page-sub { color: #64748b; font-size: .9rem; margin-top: 4px; }

    /* ===================== METRIC CARDS ===================== */
    .metric-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 18px 20px;
        display: flex; align-items: flex-start; gap: 14px;
        height: 100%;
        transition: all .2s ease;
    }
    .metric-card:hover { box-shadow: 0 8px 24px rgba(15,23,42,.07); transform: translateY(-1px); }
    .metric-icon {
        width: 46px; height: 46px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.25rem; flex-shrink: 0;
    }
    .metric-label { font-size: .82rem; color: #64748b; font-weight: 500; margin-bottom: 6px; }
    .metric-value { font-size: 1.55rem; color: #0f172a; font-weight: 700; line-height: 1.15; letter-spacing: -.5px; }
    .metric-delta { font-size: .75rem; font-weight: 600; margin-top: 8px; }
    .metric-delta span { color: #94a3b8; font-weight: 400; }

    /* ===================== CARDS / CONTAINERS ===================== */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #fff;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div { padding: 10px 6px; }

    .card-title {
        font-size: 1rem; font-weight: 700; color: #0f172a;
        display: flex; align-items: center; gap: 8px;
        margin: 0 0 4px 0;
    }
    .card-title .ic { color: #059669; }

    /* ===================== BUTTONS ===================== */
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px; font-weight: 600;
        transition: all .15s ease;
    }
    .stButton > button[kind="primary"], .stDownloadButton > button {
        background: linear-gradient(135deg, #059669, #10b981);
        color: #fff; border: none;
        box-shadow: 0 6px 16px rgba(5,150,105,.22);
    }
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #047857, #059669);
        box-shadow: 0 8px 20px rgba(5,150,105,.32);
    }

    /* ===================== DATAFRAMES ===================== */
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }

    /* ===================== ATIVIDADES ===================== */
    .activity {
        display: flex; align-items: flex-start; gap: 12px;
        padding: 10px 4px;
        border-bottom: 1px solid #f1f5f9;
    }
    .activity:last-child { border-bottom: none; }
    .activity-icon {
        width: 34px; height: 34px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: .95rem; flex-shrink: 0;
    }
    .activity-title { font-size: .85rem; font-weight: 600; color: #0f172a; }
    .activity-sub { font-size: .75rem; color: #64748b; margin-top: 2px; }
    .activity-time { font-size: .72rem; color: #94a3b8; margin-left: auto; white-space: nowrap; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# BANCO DE DADOS
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
    resposta = conn.table("inventario").select("id, quantidade").eq("item", item).eq("validade", validade_str).execute()
    if resposta.data:
        item_id = resposta.data[0]['id']
        nova_qtd = resposta.data[0]['quantidade'] + quantidade
        conn.table("inventario").update({"quantidade": nova_qtd}).eq("id", item_id).execute()
    else:
        conn.table("inventario").insert({
            "id": str(uuid.uuid4()),
            "item": item.strip(),
            "categoria": categoria,
            "quantidade": quantidade,
            "validade": validade_str,
            "doador": doador.strip() or "Anónimo",
            "data_entrada": datetime.now().isoformat(timespec="seconds"),
        }).execute()
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Entrada",
        "item": item.strip(),
        "categoria": categoria,
        "quantidade": quantidade,
        "pessoa": doador.strip() or "Anónimo",
        "observacoes": "Doação registada",
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
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Saída",
        "item": item,
        "categoria": categoria,
        "quantidade": quantidade,
        "pessoa": destino.strip() or "—",
        "observacoes": observacoes.strip() or "Baixa de stock",
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
        "observacoes": "Item eliminado do inventário",
    }).execute()
    st.cache_data.clear()
    return True, "Item eliminado."

# =========================================================
# PDF
# =========================================================
@st.cache_resource
def _registar_fonte_unicode():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for nome, caminho in [("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                          ("Arial", "C:/Windows/Fonts/arial.ttf")]:
        if os.path.exists(caminho):
            try:
                pdfmetrics.registerFont(TTFont(nome, caminho))
                return nome
            except Exception:
                continue
    return "Helvetica"

def _fmt(v): return "" if pd.isna(v) else str(v)

def gerar_pdf(df, titulo, subtitulo=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm, title=titulo)
    fonte = _registar_fonte_unicode()
    estilos = getSampleStyleSheet()
    t_style = ParagraphStyle("T", parent=estilos["Title"], fontName=fonte, fontSize=16,
                             textColor=colors.HexColor("#0f172a"), spaceAfter=4)
    s_style = ParagraphStyle("S", parent=estilos["Normal"], fontName=fonte, fontSize=9,
                             textColor=colors.HexColor("#64748b"), spaceAfter=2)
    story = [Paragraph(titulo, t_style)]
    if subtitulo: story.append(Paragraph(subtitulo, s_style))
    story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", s_style))
    story.append(Spacer(1, 6 * mm))
    if df.empty:
        story.append(Paragraph("Sem dados para apresentar.", s_style))
    else:
        cols = list(df.columns)
        dados = [cols] + [[_fmt(v) for v in linha] for linha in df.values.tolist()]
        tabela = Table(dados, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), fonte),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(tabela)
    doc.build(story)
    return buffer.getvalue()

def botao_pdf(df, titulo, subtitulo, nome_ficheiro):
    chave = f"pdf_{nome_ficheiro}"
    if st.button("📄 Preparar PDF", key=f"b_{nome_ficheiro}", use_container_width=True):
        with st.spinner("Gerando PDF..."):
            st.session_state[chave] = gerar_pdf(df, titulo, subtitulo)
    if chave in st.session_state:
        st.download_button("⬇️ Descarregar PDF", data=st.session_state[chave],
                           file_name=nome_ficheiro, mime="application/pdf", use_container_width=True)

# =========================================================
# HELPERS
# =========================================================
def status_validade(v):
    if not v or pd.isna(v): return "Sem validade"
    try: d = pd.to_datetime(v).date()
    except Exception: return "Inválida"
    hoje = date.today()
    if d < hoje: return "Vencido"
    if d <= hoje + timedelta(days=DIAS_ALERTA): return "A vencer"
    return "OK"

def renomear(df):
    mapa = {"item": "Item", "categoria": "Categoria", "quantidade": "Qtd",
            "validade": "Validade", "doador": "Doador", "data_entrada": "Data Entrada",
            "data": "Data/Hora", "tipo": "Tipo", "pessoa": "Pessoa", "observacoes": "Observações"}
    return df.rename(columns={k: v for k, v in mapa.items() if k in df.columns})

def render_tabela(df):
    if df.empty:
        st.info("Sem registos para mostrar.")
        return
    df_show = df.copy()
    if "validade" in df_show.columns:
        df_show["Estado"] = df_show["validade"].apply(status_validade)
    st.dataframe(renomear(df_show), use_container_width=True, hide_index=True)

def metric_card(label, value, delta_text, delta_positive, icon, bg, color):
    arrow = "↗" if delta_positive else "↘"
    d_color = "#059669" if delta_positive else "#dc2626"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon" style="background:{bg};color:{color};">{icon}</div>
        <div style="flex:1;">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-delta" style="color:{d_color};">
                {arrow} {delta_text} <span>em relação ao mês anterior</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================
if "menu_nav" not in st.session_state:
    st.session_state.menu_nav = "📊 Visão geral"

def goto_novo():
    st.session_state.menu_nav = "📦 Registar Doação"

with st.sidebar:
    st.markdown("""
        <div class="sidebar-logo">
            <div class="logo-icon">📦</div>
            <div>
                <div class="logo-title">EstocaPro</div>
                <div class="logo-sub">Seu estoque, no controle</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    menu = st.radio(
        "Menu",
        ["📊 Visão geral", "📦 Registar Doação", "🔍 Consultar Inventário",
         "📤 Dar Baixa / Saída", "⚠️ Alertas de Validade",
         "🕓 Histórico", "🗑️ Apagar Item"],
        key="menu_nav",
        label_visibility="collapsed",
    )

    st.markdown(f"""
        <div class="status-card">
            <div class="status-row"><span class="dot"></span> Sistema online</div>
            <div class="status-sub">
                Última atualização<br>
                {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </div>
        </div>
    """, unsafe_allow_html=True)

# =========================================================
# TOP BAR
# =========================================================
tb1, tb2, tb3 = st.columns([3, 1.1, 1])
with tb1:
    st.text_input("busca_global", placeholder="🔍  Buscar produto, categoria, doador...",
                  label_visibility="collapsed", key="busca_global")
with tb2:
    st.date_input("data_ref", value=date.today(), label_visibility="collapsed", key="data_ref")
with tb3:
    st.markdown("""
        <div class="topbar-user">
            <div class="bell">🔔</div>
            <div class="avatar">B</div>
            <div>
                <div class="user-name">Bárbara</div>
                <div class="user-role">Administrador</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

# =========================================================
# PÁGINAS
# =========================================================

# ---------------- 1. VISÃO GERAL ----------------
if menu == "📊 Visão geral":
    inv = carregar_inventario()
    mov = carregar_movimentos()

    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown(
            '<div class="page-title">Visão geral do estoque</div>'
            '<div class="page-sub">Acompanhe o desempenho do seu estoque em tempo real.</div>',
            unsafe_allow_html=True,
        )
    with h2:
        st.button("＋ Novo produto", type="primary", use_container_width=True, on_click=goto_novo)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # --- Métricas ---
    total_unidades = int(inv["quantidade"].sum()) if not inv.empty else 0
    itens_distintos = len(inv) if not inv.empty else 0
    categorias_n = inv["categoria"].nunique() if not inv.empty else 0

    inv_v = inv.copy() if not inv.empty else pd.DataFrame()
    vencidos_qtd = a_vencer_qtd = estoque_baixo = 0
    if not inv_v.empty:
        inv_v["_st"] = inv_v["validade"].apply(status_validade)
        vencidos_qtd = int(inv_v.loc[inv_v["_st"] == "Vencido", "quantidade"].sum())
        a_vencer_qtd = int(inv_v.loc[inv_v["_st"] == "A vencer", "quantidade"].sum())
        estoque_baixo = int((inv_v["quantidade"] <= 5).sum())

    mov_hoje = 0
    if not mov.empty:
        try:
            mov_dt = pd.to_datetime(mov["data"], errors="coerce")
            mov_hoje = int((mov_dt.dt.date == date.today()).sum())
        except Exception:
            mov_hoje = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Itens distintos", f"{itens_distintos}", "+12%", True,
                    "📦", "#d1fae5", "#059669")
    with c2:
        metric_card("Unidades em estoque", f"{total_unidades:,}".replace(",", "."),
                    "+8%", True, "🗄️", "#d1fae5", "#059669")
    with c3:
        metric_card("Estoque baixo", f"{estoque_baixo}", "-5%", False,
                    "⚠️", "#fee2e2", "#dc2626")
    with c4:
        metric_card("Movimentações hoje", f"{mov_hoje}", "+23%", True,
                    "🔄", "#dbeafe", "#2563eb")

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # --- Gráficos ---
    g1, g2 = st.columns([1.6, 1])

    with g1:
        with st.container(border=True):
            st.markdown('<div class="card-title"><span class="ic">📈</span> Evolução do estoque (unidades)</div>',
                        unsafe_allow_html=True)
            if mov.empty:
                st.caption("Sem movimentos suficientes para gerar o gráfico.")
            else:
                m = mov.copy()
                m["dt"] = pd.to_datetime(m["data"], errors="coerce")
                m = m.dropna(subset=["dt"]).sort_values("dt")
                m["delta"] = m.apply(
                    lambda r: r["quantidade"] if r["tipo"] in ("Entrada",) else -r["quantidade"],
                    axis=1,
                )
                diario = m.set_index("dt").resample("D")["delta"].sum().cumsum()
                ult7 = diario.tail(7)
                if ult7.empty:
                    st.caption("Sem dados suficientes.")
                else:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=ult7.index, y=ult7.values,
                        mode="lines+markers",
                        line=dict(color="#059669", width=2.5, shape="spline"),
                        marker=dict(size=7, color="#059669"),
                        fill="tozeroy",
                        fillcolor="rgba(16,185,129,0.12)",
                        hovertemplate="%{x|%d/%m}<br>%{y} un.<extra></extra>",
                    ))
                    fig.update_layout(
                        height=280, margin=dict(l=10, r=10, t=10, b=10),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False, tickformat="%d/%m",
                                   tickfont=dict(color="#94a3b8", size=11)),
                        yaxis=dict(showgrid=True, gridcolor="#f1f5f9",
                                   tickfont=dict(color="#94a3b8", size=11)),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with g2:
        with st.container(border=True):
            st.markdown('<div class="card-title"><span class="ic">🥧</span> Categorias</div>',
                        unsafe_allow_html=True)
            if inv.empty:
                st.caption("Sem dados para apresentar.")
            else:
                cat = inv.groupby("categoria")["quantidade"].sum().sort_values(ascending=False)
                cores = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#94a3b8"]
                fig = go.Figure(data=[go.Pie(
                    labels=cat.index, values=cat.values, hole=0.62,
                    marker=dict(colors=cores[:len(cat)],
                                line=dict(color="#fff", width=2)),
                    textinfo="none",
                    hovertemplate="%{label}<br>%{value} un.<br>%{percent}<extra></extra>",
                )])
                fig.update_layout(
                    height=280, margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="v", x=1.0, y=0.5,
                                font=dict(size=11, color="#475569")),
                    annotations=[dict(text=f"<b>{int(cat.sum())}</b><br><span style='font-size:11px;color:#94a3b8'>unidades</span>",
                                      x=0.5, y=0.5, showarrow=False,
                                      font=dict(size=20, color="#0f172a"))],
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # --- Tabela + Atividades ---
    b1, b2 = st.columns([1.6, 1])

    with b1:
        with st.container(border=True):
            st.markdown('<div class="card-title"><span class="ic">📋</span> Produtos em estoque</div>',
                        unsafe_allow_html=True)
            if inv.empty:
                st.info("Ainda não há produtos. Comece por **📦 Registar Doação**.")
            else:
                df_show = inv.copy()
                busca = st.session_state.get("busca_global", "").strip()
                if busca:
                    df_show = df_show[
                        df_show["item"].str.lower().str.contains(busca.lower(), na=False)
                        | df_show["categoria"].str.lower().str.contains(busca.lower(), na=False)
                    ]
                df_show = df_show.head(8)
                df_show["Estado"] = df_show.apply(
                    lambda r: "Estoque baixo" if r["quantidade"] <= 5 else "Em estoque", axis=1
                )
                out = renomear(df_show[["item", "categoria", "quantidade", "Estado"]])
                st.dataframe(out, use_container_width=True, hide_index=True)
                st.caption(f"Mostrando {len(df_show)} de {len(inv)} produtos · use a busca acima para filtrar.")

    with b2:
        with st.container(border=True):
            st.markdown('<div class="card-title"><span class="ic">🕓</span> Atividades recentes</div>',
                        unsafe_allow_html=True)
            if mov.empty:
                st.caption("Sem atividades registadas.")
            else:
                icones = {
                    "Entrada": ("+", "#059669", "#d1fae5"),
                    "Saída": ("−", "#dc2626", "#fee2e2"),
                    "Eliminação": ("🗑", "#dc2626", "#fee2e2"),
                }
                for _, r in mov.head(6).iterrows():
                    sinal, cor, bgc = icones.get(r["tipo"], ("•", "#64748b", "#f1f5f9"))
                    try:
                        dt = pd.to_datetime(r["data"])
                        quando = "Hoje, " + dt.strftime("%H:%M") if dt.date() == date.today() \
                                 else dt.strftime("%d/%m %H:%M")
                    except Exception:
                        quando = ""
                    st.markdown(f"""
                        <div class="activity">
                            <div class="activity-icon" style="background:{bgc};color:{cor};font-weight:700;">{sinal}</div>
                            <div style="flex:1;">
                                <div class="activity-title">{r['tipo']} de produto</div>
                                <div class="activity-sub">{r['item']} · {int(r['quantidade'])} un.</div>
                            </div>
                            <div class="activity-time">{quando}</div>
                        </div>
                    """, unsafe_allow_html=True)

# ---------------- 2. REGISTAR DOAÇÃO ----------------
elif menu == "📦 Registar Doação":
    st.markdown('<div class="page-title">Registar nova doação</div>'
                '<div class="page-sub">Adicione um produto ou registe uma entrada de doação.</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        with st.form("form_doacao", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                item = st.text_input("Nome do Item *", placeholder="Ex.: Leite, Arroz…")
                categoria = st.selectbox("Categoria *", CATEGORIAS)
                quantidade = st.number_input("Quantidade *", min_value=1, step=1, value=1)
            with col2:
                tem_validade = st.checkbox("Este item tem validade?", value=True)
                validade = st.date_input("Data de Validade",
                                         value=date.today() + timedelta(days=90),
                                         disabled=not tem_validade)
                doador = st.text_input("Doador / Origem", placeholder="Nome ou 'Anónimo'")
            submitted = st.form_submit_button("💾 Guardar Registo", use_container_width=True)
            if submitted:
                if not item.strip():
                    st.warning("⚠️ Preenche o **Nome do Item**.")
                else:
                    registar_entrada(item, categoria, int(quantidade),
                                     validade if tem_validade else None, doador)
                    st.success(f"✅ '{item}' registado com sucesso!")
                    st.balloons()

# ---------------- 3. CONSULTAR INVENTÁRIO ----------------
elif menu == "🔍 Consultar Inventário":
    st.markdown('<div class="page-title">Consultar inventário</div>'
                '<div class="page-sub">Pesquise, filtre e exporte os produtos em estoque.</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    inv = carregar_inventario()
    if inv.empty:
        st.info("Sem dados no inventário.")
    else:
        with st.container(border=True):
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
                    df["item"].str.lower().str.contains(busca.lower(), na=False)
                    | df["doador"].str.lower().str.contains(busca.lower(), na=False)
                ]
            mapa_ordem = {"Item": "item", "Quantidade": "quantidade", "Validade": "validade"}
            df = df.sort_values(by=mapa_ordem[ordem],
                                ascending=(ordem != "Quantidade"),
                                na_position="last")
            render_tabela(df)

            if not df.empty:
                c_csv, c_pdf = st.columns(2)
                with c_csv:
                    st.download_button("⬇️ Exportar CSV",
                                       data=df.to_csv(index=False).encode("utf-8"),
                                       file_name=f"inventario_{date.today()}.csv",
                                       mime="text/csv", use_container_width=True)
                with c_pdf:
                    botao_pdf(renomear(df.drop(columns=["id"], errors="ignore")),
                              "Inventário Filtrado", f"Filtro: {cat}",
                              f"inventario_{date.today()}.pdf")

# ---------------- 4. DAR BAIXA ----------------
elif menu == "📤 Dar Baixa / Saída":
    st.markdown('<div class="page-title">Registar saída / baixa</div>'
                '<div class="page-sub">Retire unidades do estoque e registe o destino.</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    inv = carregar_inventario()
    if inv.empty:
        st.info("Sem itens em inventário.")
    else:
        with st.container(border=True):
            opcoes = {f"{r['item']} — {r['categoria']} | stock: {r['quantidade']}": r["id"]
                      for _, r in inv.iterrows()}
            escolha = st.selectbox("Selecione o item", list(opcoes.keys()))
            item_id = opcoes[escolha]
            stock_max = int(inv.loc[inv["id"] == item_id, "quantidade"].iloc[0])
            with st.form("form_baixa"):
                col1, col2 = st.columns(2)
                with col1:
                    qtd = st.number_input("Quantidade a retirar *", min_value=1,
                                          max_value=stock_max, value=min(1, stock_max))
                    destino = st.text_input("Destino / Beneficiário",
                                            placeholder="Ex.: Cozinha")
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

# ---------------- 5. ALERTAS DE VALIDADE ----------------
elif menu == "⚠️ Alertas de Validade":
    st.markdown('<div class="page-title">Alertas de validade</div>'
                '<div class="page-sub">Produtos vencidos ou próximos do vencimento.</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    inv = carregar_inventario()
    if inv.empty:
        st.info("Sem dados.")
    else:
        df = inv.copy()
        df["_v"] = pd.to_datetime(df["validade"], errors="coerce").dt.date
        hoje = date.today()
        vencidos = df[df["_v"] < hoje]
        a_vencer = df[(df["_v"] >= hoje) & (df["_v"] <= hoje + timedelta(days=DIAS_ALERTA))]

        c1, c2 = st.columns(2)
        with c1:
            metric_card("Vencidos", f"{len(vencidos)}", "-3%", False,
                        "🚫", "#fee2e2", "#dc2626")
        with c2:
            metric_card(f"A vencer ({DIAS_ALERTA}d)", f"{len(a_vencer)}", "+4%", False,
                        "⚠️", "#fef3c7", "#d97706")

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<div class="card-title"><span class="ic">🚫</span> Vencidos</div>',
                        unsafe_allow_html=True)
            if vencidos.empty:
                st.success("Nenhum produto vencido.")
            else:
                render_tabela(vencidos.drop(columns=["_v"]))

        with st.container(border=True):
            st.markdown('<div class="card-title"><span class="ic">⚠️</span> A vencer</div>',
                        unsafe_allow_html=True)
            if a_vencer.empty:
                st.success("Nenhum produto a vencer nos próximos dias.")
            else:
                render_tabela(a_vencer.drop(columns=["_v"]))

# ---------------- 6. HISTÓRICO ----------------
elif menu == "🕓 Histórico":
    st.markdown('<div class="page-title">Histórico de movimentos</div>'
                '<div class="page-sub">Todas as entradas, saídas e eliminações registadas.</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    mov = carregar_movimentos()
    with st.container(border=True):
        if mov.empty:
            st.info("Sem movimentos registados.")
        else:
            st.dataframe(
                renomear(mov[["data", "tipo", "item", "categoria",
                              "quantidade", "pessoa", "observacoes"]]),
                use_container_width=True, hide_index=True,
            )
            st.download_button("⬇️ Exportar CSV",
                               data=mov.to_csv(index=False).encode("utf-8"),
                               file_name=f"movimentos_{date.today()}.csv",
                               mime="text/csv")

# ---------------- 7. APAGAR ITEM ----------------
elif menu == "🗑️ Apagar Item":
    st.markdown('<div class="page-title">Apagar item</div>'
                '<div class="page-sub">Remova permanentemente um item do inventário.</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    inv = carregar_inventario()
    if inv.empty:
        st.info("Sem itens para eliminar.")
    else:
        with st.container(border=True):
            st.warning("⚠️ Esta ação é irreversível e será registada no histórico.")
            opcoes = {f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']}": r["id"]
                      for _, r in inv.iterrows()}
            escolha = st.selectbox("Selecione o item", list(opcoes.keys()))
            confirmar = st.checkbox("Confirmo que quero eliminar este item permanentemente.")
            if st.button("🗑️ Eliminar", type="primary", disabled=not confirmar):
                ok, msg = apagar_item(opcoes[escolha])
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
