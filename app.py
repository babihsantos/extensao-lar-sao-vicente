import os
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from st_supabase_connection import SupabaseConnection

# =========================================================
# CONFIGURAÇÃO
# =========================================================
st.set_page_config(
    page_title="Gestão de Doações — Lar São Vicente",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DIAS_ALERTA = 30
CATEGORIAS_PADRAO = [
    "Alimentação", "Higiene Pessoal", "Limpeza",
    "Medicamentos", "Vestuário", "Outros",
]

conn = st.connection("supabase_connection", type=SupabaseConnection)

# =========================================================
# CSS MODERNO
# =========================================================
st.markdown(
    """
    <style>
    /* ---------- base ---------- */
    .stApp { background: #f4f6fb; }
    .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 1400px; }

    /* esconder header padrão do streamlit */
    header[data-testid="stHeader"] { background: transparent; }

    /* ---------- sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e2a47 0%, #2E86AB 100%);
    }
    section[data-testid="stSidebar"] * { color: #eef2f7 !important; }
    section[data-testid="stSidebar"] .stRadio > label { color: #eef2f7 !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15); }
    section[data-testid="stSidebar"] .stButton>button {
        background: rgba(255,255,255,0.12);
        color: #fff;
        border: 1px solid rgba(255,255,255,0.2);
    }
    section[data-testid="stSidebar"] .stButton>button:hover {
        background: rgba(255,255,255,0.22);
    }

    /* ---------- hero ---------- */
    .hero {
        position: relative;
        background: linear-gradient(120deg, #2E86AB 0%, #6A4C93 55%, #C73E1D 100%);
        background-size: 200% 200%;
        animation: gradShift 12s ease infinite;
        padding: 2rem 2.2rem;
        border-radius: 20px;
        color: #fff;
        margin-bottom: 1.5rem;
        box-shadow: 0 12px 40px rgba(46,134,171,0.28);
        overflow: hidden;
    }
    .hero::before {
        content: ""; position: absolute; top:-50%; right:-10%;
        width: 380px; height: 380px;
        background: radial-gradient(circle, rgba(255,255,255,0.18), transparent 70%);
        border-radius: 50%;
    }
    .hero h1 { margin: 0; font-size: 1.9rem; font-weight: 800; letter-spacing: -0.5px; }
    .hero .sub { opacity: 0.92; margin-top: .4rem; font-size: 1rem; }
    .hero .meta { margin-top: 1rem; font-size: .85rem; opacity: .85;
                  display:flex; gap: 1.4rem; flex-wrap: wrap; }
    .hero .meta span { display:inline-flex; align-items:center; gap:.35rem; }
    @keyframes gradShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* ---------- cards KPI ---------- */
    .kpi {
        background: #fff;
        padding: 1.1rem 1.2rem;
        border-radius: 16px;
        box-shadow: 0 4px 18px rgba(20,30,60,0.07);
        border-left: 5px solid var(--c);
        transition: transform .18s ease, box-shadow .18s ease;
        height: 100%;
    }
    .kpi:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 28px rgba(20,30,60,0.14);
    }
    .kpi .icon { font-size: 1.6rem; }
    .kpi .label {
        font-size: .78rem; color: #6b7280; font-weight: 600;
        text-transform: uppercase; letter-spacing: .4px;
        margin-top: .3rem;
    }
    .kpi .value {
        font-size: 1.9rem; font-weight: 800; color: #111827;
        margin-top: .15rem; line-height: 1.1;
    }
    .kpi .delta { font-size: .78rem; color: #6b7280; margin-top: .3rem; }

    /* ---------- seções ---------- */
    .section-title {
        font-size: 1.15rem; font-weight: 700; color: #1f2937;
        margin: 1.6rem 0 .9rem 0;
        display: flex; align-items: center; gap: .5rem;
    }
    .section-title::before {
        content: ""; width: 5px; height: 22px; border-radius: 4px;
        background: linear-gradient(180deg, #2E86AB, #6A4C93);
        display: inline-block;
    }

    /* ---------- card genérico ---------- */
    .card {
        background: #fff; border-radius: 16px; padding: 1.2rem 1.3rem;
        box-shadow: 0 4px 18px rgba(20,30,60,0.07);
        border: 1px solid #eef1f7;
        height: 100%;
    }
    .card h4 { margin: 0 0 .6rem 0; color:#111827; font-size: 1rem; }

    /* ---------- alertas ---------- */
    .alert {
        padding: 1rem 1.2rem; border-radius: 14px; margin-bottom: .7rem;
        display: flex; align-items: center; gap: 1rem;
        font-weight: 600;
    }
    .alert .icon { font-size: 1.8rem; }
    .alert.danger  { background:#fef2f2; border-left: 5px solid #C73E1D; color:#7f1d1d; }
    .alert.warn    { background:#fffbeb; border-left: 5px solid #F18F01; color:#78350f; }
    .alert.ok      { background:#f0fdf4; border-left: 5px solid #16a34a; color:#14532d; }
    .alert .count  { font-size: 1.4rem; font-weight: 800; }

    /* ---------- timeline ---------- */
    .timeline { position: relative; padding-left: 1.4rem; }
    .timeline::before {
        content:""; position:absolute; left: 6px; top: 0; bottom: 0;
        width: 2px; background: #e5e7eb;
    }
    .tl-item {
        position: relative; margin-bottom: 1rem;
        background: #fff; padding: .7rem .9rem;
        border-radius: 12px; box-shadow: 0 2px 10px rgba(20,30,60,0.05);
    }
    .tl-item::before {
        content:""; position:absolute; left:-1.15rem; top: 14px;
        width: 12px; height: 12px; border-radius: 50%;
        background: var(--dot, #2E86AB);
        border: 2px solid #fff;
        box-shadow: 0 0 0 2px var(--dot, #2E86AB);
    }
    .tl-item .t { font-size: .78rem; color: #6b7280; }
    .tl-item .h { font-weight: 700; color: #111827; margin-top: .1rem; }
    .tl-item .d { font-size: .84rem; color: #4b5563; margin-top: .1rem; }

    /* ---------- badge ---------- */
    .badge {
        display: inline-block; padding: .18rem .6rem;
        border-radius: 999px; font-size: .74rem; font-weight: 700;
    }
    .badge.in  { background:#dbeafe; color:#1e40af; }
    .badge.out { background:#fee2e2; color:#991b1b; }
    .badge.del { background:#f3f4f6; color:#374151; }
    .badge.edit{ background:#fef3c7; color:#92400e; }

    /* ---------- tabela ---------- */
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

    /* ---------- métricas nativas ---------- */
    [data-testid="stMetric"] {
        background: #fff; border-radius: 14px;
        padding: .8rem 1rem; box-shadow: 0 3px 12px rgba(20,30,60,0.06);
    }

    /* botões */
    .stButton>button, .stDownloadButton>button {
        border-radius: 10px; font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# BASE DE DADOS
# =========================================================
@st.cache_data(ttl=30)
def carregar_inventario() -> pd.DataFrame:
    r = conn.table("inventario").select("*").order("categoria").order("item").execute()
    df = pd.DataFrame(r.data)
    if not df.empty and "estoque_minimo" not in df.columns:
        df["estoque_minimo"] = 5
    return df


@st.cache_data(ttl=30)
def carregar_movimentos() -> pd.DataFrame:
    r = conn.table("movimentos").select("*").order("data", desc=True).execute()
    return pd.DataFrame(r.data)


def registar_entrada(item, categoria, quantidade, validade, doador, estoque_minimo):
    vs = str(validade) if validade else None
    r = conn.table("inventario").select("id, quantidade").eq("item", item).eq("validade", vs).execute()
    if r.data:
        iid = r.data[0]["id"]
        nova = r.data[0]["quantidade"] + quantidade
        conn.table("inventario").update(
            {"quantidade": nova, "estoque_minimo": estoque_minimo}
        ).eq("id", iid).execute()
    else:
        conn.table("inventario").insert({
            "id": str(uuid.uuid4()),
            "item": item.strip(), "categoria": categoria,
            "quantidade": quantidade, "validade": vs,
            "doador": doador.strip() or "Anónimo",
            "estoque_minimo": estoque_minimo,
            "data_entrada": datetime.now().isoformat(timespec="seconds"),
        }).execute()

    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Entrada", "item": item.strip(), "categoria": categoria,
        "quantidade": quantidade, "pessoa": doador.strip() or "Anónimo",
        "observacoes": "Doação registada",
    }).execute()
    st.cache_data.clear()


def atualizar_item(iid, item, categoria, qtd, validade, doador, minimo):
    conn.table("inventario").update({
        "item": item.strip(), "categoria": categoria,
        "quantidade": qtd, "validade": str(validade) if validade else None,
        "doador": doador.strip() or "Anónimo", "estoque_minimo": minimo,
    }).eq("id", iid).execute()
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Edição", "item": item.strip(), "categoria": categoria,
        "quantidade": qtd, "pessoa": "Sistema", "observacoes": "Item editado",
    }).execute()
    st.cache_data.clear()


def dar_baixa(iid, qtd, destino, obs):
    r = conn.table("inventario").select("item, categoria, quantidade").eq("id", iid).execute()
    if not r.data:
        return False, "Item não encontrado."
    item, cat, stock = r.data[0]["item"], r.data[0]["categoria"], r.data[0]["quantidade"]
    if qtd > stock:
        return False, f"Stock insuficiente (disponível: {stock})."
    nova = stock - qtd
    if nova == 0:
        conn.table("inventario").delete().eq("id", iid).execute()
    else:
        conn.table("inventario").update({"quantidade": nova}).eq("id", iid).execute()
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Saída", "item": item, "categoria": cat,
        "quantidade": qtd, "pessoa": destino.strip() or "—",
        "observacoes": obs.strip() or "Baixa de stock",
    }).execute()
    st.cache_data.clear()
    return True, "Baixa registada."


def apagar_item(iid):
    r = conn.table("inventario").select("item, categoria, quantidade").eq("id", iid).execute()
    if not r.data:
        return False, "Item não encontrado."
    item, cat, q = r.data[0]["item"], r.data[0]["categoria"], r.data[0]["quantidade"]
    conn.table("inventario").delete().eq("id", iid).execute()
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Eliminação", "item": item, "categoria": cat,
        "quantidade": q, "pessoa": "Sistema", "observacoes": "Item eliminado",
    }).execute()
    st.cache_data.clear()
    return True, "Item eliminado."


# =========================================================
# PDF
# =========================================================
@st.cache_resource
def _fonte():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for n, p in [("DejaVu","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                 ("Arial","C:/Windows/Fonts/arial.ttf")]:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont(n, p)); return n
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
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm, title=titulo)
    f = _fonte()
    s = getSampleStyleSheet()
    ts = ParagraphStyle("T", parent=s["Title"], fontName=f, fontSize=16,
                        textColor=colors.HexColor("#2E86AB"), spaceAfter=4)
    ss = ParagraphStyle("S", parent=s["Normal"], fontName=f, fontSize=9,
                        textColor=colors.HexColor("#666"), spaceAfter=2)
    story = [Paragraph(titulo, ts)]
    if subtitulo: story.append(Paragraph(subtitulo, ss))
    story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", ss))
    story.append(Spacer(1, 6*mm))
    if df.empty:
        story.append(Paragraph("Sem dados.", ss))
    else:
        dados = [list(df.columns)] + [[_fmt(v) for v in r] for r in df.values.tolist()]
        t = Table(dados, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2E86AB")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,-1),f),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cfd8dc")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f5f7fa")]),
        ]))
        story.append(t)
    doc.build(story); return buf.getvalue()


def botao_pdf(df, titulo, sub, nome):
    k = f"pdf_{nome}"
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 Preparar PDF", key=f"b_{nome}", use_container_width=True):
            with st.spinner("Gerando..."):
                st.session_state[k] = gerar_pdf(df, titulo, sub)
    if k in st.session_state:
        with c2:
            st.download_button("⬇️ Descarregar", data=st.session_state[k],
                file_name=nome, mime="application/pdf", use_container_width=True)


# =========================================================
# HELPERS
# =========================================================
def status_validade(v):
    if not v or pd.isna(v): return "Sem validade"
    try: d = pd.to_datetime(v).date()
    except Exception: return "Inválida"
    h = date.today()
    if d < h: return "Vencido"
    if d <= h + timedelta(days=DIAS_ALERTA): return "A vencer"
    return "OK"


def renomear(df):
    m = {"item":"Item","categoria":"Categoria","quantidade":"Qtd",
         "validade":"Validade","doador":"Doador","data_entrada":"Data Entrada",
         "data":"Data/Hora","tipo":"Tipo","pessoa":"Pessoa",
         "observacoes":"Observações","estoque_minimo":"Est. Mínimo"}
    return df.rename(columns={k:v for k,v in m.items() if k in df.columns})


def render_tabela(df):
    if df.empty:
        st.info("Sem registos."); return
    d = df.copy()
    if "validade" in d.columns:
        d["Estado"] = d["validade"].apply(status_validade)
    st.dataframe(renomear(d), use_container_width=True, hide_index=True)


def kpi_card(icon, label, value, color, extra=""):
    return f"""
    <div class="kpi" style="--c:{color}">
        <div class="icon">{icon}</div>
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="delta">{extra}</div>
    </div>
    """


def alert_card(kind, icon, count, text):
    return f"""
    <div class="alert {kind}">
        <div class="icon">{icon}</div>
        <div>
            <div class="count">{count}</div>
            <div style="font-weight:500;font-size:.85rem;opacity:.85">{text}</div>
        </div>
    </div>
    """


def section_title(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def hero():
    agora = datetime.now().strftime("%d/%m/%Y · %H:%M")
    st.markdown(f"""
    <div class="hero">
        <h1>🏥 Sistema de Controlo de Doações e Inventário</h1>
        <div class="sub">Lar São Vicente de Paulo — São José do Rio Preto · Projeto de Extensão UNIP</div>
        <div class="meta">
            <span>📅 {agora}</span>
            <span>☁️ Dados sincronizados (Supabase)</span>
            <span>🔒 Sessão local</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def badge(tipo):
    cls = {"Entrada":"in","Saída":"out","Eliminação":"del","Edição":"edit"}.get(tipo,"del")
    return f'<span class="badge {cls}">{tipo}</span>'


# =========================================================
# HERO
# =========================================================
hero()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("## 🏥 Lar São Vicente")
    st.caption("Sistema de inventário")
    st.divider()

    menu = st.radio(
        "Menu",
        [
            "📊  Dashboard",
            "📦  Registar Doação",
            "🔍  Inventário",
            "📤  Dar Baixa",
            "⚠️  Alertas de Validade",
            "📉  Estoque Baixo",
            "👥  Doadores",
            "📈  Relatórios",
            "🕓  Histórico",
            "🗑️  Apagar Item",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("🔄 Recarregar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("💾 Dados no Supabase · cache 30s")


# =========================================================
# 1. DASHBOARD
# =========================================================
if menu == "📊  Dashboard":
    inv = carregar_inventario()
    mov = carregar_movimentos()

    if inv.empty:
        st.info("Ainda não há dados. Vai a **📦 Registar Doação** para começar.")
    else:
        inv["_status"] = inv["validade"].apply(status_validade)
        total_un = int(inv["quantidade"].sum())
        venc = int(inv.loc[inv["_status"] == "Vencido", "quantidade"].sum())
        aven = int(inv.loc[inv["_status"] == "A vencer", "quantidade"].sum())
        baixo = int((inv["quantidade"] <= inv["estoque_minimo"]).sum())
        total_doa = mov[mov["tipo"] == "Entrada"]["quantidade"].sum() if not mov.empty else 0

        # -------- KPIs --------
        cols = st.columns(6)
        cards = [
            ("📦", "Unidades em stock", f"{total_un:,}".replace(",", "."), "#2E86AB", f"{len(inv)} lotes"),
            ("🏷️", "Itens distintos", len(inv), "#6A4C93", f"{inv['categoria'].nunique()} categorias"),
            ("📥", "Doações recebidas", int(total_doa), "#16a34a", "histórico total"),
            ("⚠️", "A vencer (30d)", aven, "#F18F01", f"{len(inv[inv['_status']=='A vencer'])} lotes"),
            ("🚫", "Vencidos", venc, "#C73E1D", f"{len(inv[inv['_status']=='Vencido'])} lotes"),
            ("📉", "Estoque baixo", baixo, "#dc2626", "repor urgente"),
        ]
        for c, (i, l, v, col, e) in zip(cols, cards):
            c.markdown(kpi_card(i, l, v, col, e), unsafe_allow_html=True)

        # -------- alertas --------
        section_title("🚨 Estado do Inventário")

        a1, a2, a3 = st.columns(3)
        if venc > 0:
            a1.markdown(alert_card("danger", "🚫", len(inv[inv['_status']=='Vencido']),
                "Lotes vencidos — retirar do stock!"), unsafe_allow_html=True)
        else:
            a1.markdown(alert_card("ok", "✅", 0, "Nenhum item vencido"), unsafe_allow_html=True)

        if aven > 0:
            a2.markdown(alert_card("warn", "⚠️", len(inv[inv['_status']=='A vencer']),
                f"A vencer nos próximos {DIAS_ALERTA} dias"), unsafe_allow_html=True)
        else:
            a2.markdown(alert_card("ok", "✅", 0, "Nada a vencer"), unsafe_allow_html=True)

        if baixo > 0:
            a3.markdown(alert_card("warn", "📉", baixo,
                "Itens abaixo do estoque mínimo"), unsafe_allow_html=True)
        else:
            a3.markdown(alert_card("ok", "✅", 0, "Estoque saudável"), unsafe_allow_html=True)

        # -------- gráficos --------
        section_title("📊 Análise Visual")

        g1, g2 = st.columns([1.3, 1])
        with g1:
            por_cat = (inv.groupby("categoria", as_index=False)["quantidade"]
                       .sum().sort_values("quantidade", ascending=True))
            fig = px.bar(
                por_cat, x="quantidade", y="categoria", orientation="h",
                color="quantidade", color_continuous_scale="Blues",
                text="quantidade",
            )
            fig.update_layout(
                title="Stock por categoria",
                height=380, showlegend=False, coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=50, b=0),
                xaxis_title="", yaxis_title="",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="white",
            )
            fig.update_traces(textposition="outside", marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

        with g2:
            fig2 = px.pie(
                por_cat, names="categoria", values="quantidade", hole=0.55,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig2.update_layout(
                title="Distribuição",
                height=380, margin=dict(l=0, r=0, t=50, b=0),
                paper_bgcolor="white",
                legend=dict(orientation="h", y=-0.1),
            )
            fig2.update_traces(textposition="inside", textinfo="percent")
            st.plotly_chart(fig2, use_container_width=True)

        # -------- timeline + top --------
        section_title("🕓 Atividade Recente")

        t1, t2 = st.columns([1.4, 1])
        with t1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("##### Últimas movimentações")
            if mov.empty:
                st.caption("Sem movimentos.")
            else:
                for _, r in mov.head(6).iterrows():
                    cor = {"Entrada":"#16a34a","Saída":"#C73E1D",
                           "Eliminação":"#6b7280","Edição":"#F18F01"}.get(r["tipo"], "#2E86AB")
                    dt = pd.to_datetime(r["data"]).strftime("%d/%m %H:%M") if r["data"] else ""
                    st.markdown(f"""
                    <div class="timeline">
                        <div class="tl-item" style="--dot:{cor}">
                            <div class="t">{dt} · {badge(r['tipo'])}</div>
                            <div class="h">{r['item']}</div>
                            <div class="d">{r['quantidade']} un · {r.get('pessoa') or '—'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with t2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("##### 🏆 Top 5 — mais em stock")
            top = inv.nlargest(5, "quantidade")[["item", "categoria", "quantidade"]]
            medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i, (_, r) in enumerate(top.iterrows()):
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;
                            padding:.5rem .3rem;border-bottom:1px solid #f1f5f9">
                    <div><b>{medals[i]}</b> {r['item']}
                        <span style="color:#6b7280;font-size:.8rem">· {r['categoria']}</span></div>
                    <div style="font-weight:700;color:#2E86AB">{int(r['quantidade'])}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # -------- inventário --------
        section_title("📋 Inventário Completo")
        col_t, col_p = st.columns([3, 1])
        with col_p:
            botao_pdf(
                renomear(inv.drop(columns=["id","_status"], errors="ignore")),
                "Inventário Completo", "Lar São Vicente de Paulo",
                f"inventario_{date.today()}.pdf",
            )
        render_tabela(inv.drop(columns=["_status"]))


# =========================================================
# 2. REGISTAR DOAÇÃO
# =========================================================
elif menu == "📦  Registar Doação":
    section_title("📦 Registar Nova Doação ou Entrada")

    with st.form("form_doacao", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            item = st.text_input("Nome do Item *", placeholder="Ex.: Leite, Arroz…")
            categoria = st.selectbox("Categoria *", CATEGORIAS_PADRAO)
            quantidade = st.number_input("Quantidade *", min_value=1, step=1, value=1)
            estoque_minimo = st.number_input(
                "Estoque mínimo (alerta)", min_value=0, step=1, value=5,
                help="Avisa quando o stock ficar abaixo deste valor.")
        with c2:
            tem_val = st.checkbox("Este item tem validade?", value=True)
            validade = st.date_input("Data de Validade",
                value=date.today() + timedelta(days=90),
                disabled=not tem_val)
            doador = st.text_input("Doador / Origem", placeholder="Nome ou 'Anónimo'")

        ok = st.form_submit_button("💾 Guardar Registo", use_container_width=True)
        if ok:
            if not item.strip():
                st.warning("⚠️ Preenche o **Nome do Item**.")
            else:
                registar_entrada(item, categoria, int(quantidade),
                    validade if tem_val else None, doador, int(estoque_minimo))
                st.success(f"✅ '{item}' registado!")
                st.balloons()


# =========================================================
# 3. INVENTÁRIO (+ EDITAR)
# =========================================================
elif menu == "🔍  Inventário":
    section_title("🔍 Consultar / Editar Inventário")
    inv = carregar_inventario()

    if inv.empty:
        st.info("Sem dados.")
    else:
        c1, c2, c3 = st.columns([1.2, 1.5, 1])
        with c1:
            cat = st.selectbox("Categoria", ["Todas"] + sorted(inv["categoria"].unique()))
        with c2:
            busca = st.text_input("🔎 Pesquisar por nome ou doador", "")
        with c3:
            ordem = st.selectbox("Ordenar por", ["Item", "Quantidade", "Validade"])

        df = inv.copy()
        if cat != "Todas":
            df = df[df["categoria"] == cat]
        if busca.strip():
            b = busca.lower()
            df = df[df["item"].str.lower().str.contains(b, na=False)
                    | df["doador"].str.lower().str.contains(b, na=False)]

        mapa = {"Item":"item","Quantidade":"quantidade","Validade":"validade"}
        df = df.sort_values(mapa.get(ordem,"item"),
                            ascending=(ordem != "Quantidade"), na_position="last")

        m1, m2 = st.columns(2)
        m1.metric("Itens filtrados", len(df))
        m2.metric("Unidades totais", int(df["quantidade"].sum()) if not df.empty else 0)

        render_tabela(df)

        st.divider()
        section_title("✏️ Editar item")

        if df.empty:
            st.caption("Sem itens para editar.")
        else:
            opcoes = {f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']}": r["id"]
                      for _, r in df.iterrows()}
            esc = st.selectbox("Escolhe o item", list(opcoes.keys()), key="sel_edit")
            iid = opcoes[esc]
            linha = inv[inv["id"] == iid].iloc[0]

            with st.form("form_edit"):
                c1, c2 = st.columns(2)
                with c1:
                    e_item = st.text_input("Nome", value=linha["item"])
                    e_cat = st.selectbox("Categoria", CATEGORIAS_PADRAO,
                        index=CATEGORIAS_PADRAO.index(linha["categoria"])
                        if linha["categoria"] in CATEGORIAS_PADRAO else 0)
                    e_qtd = st.number_input("Quantidade", min_value=0,
                        value=int(linha["quantidade"]))
                with c2:
                    tv = pd.notna(linha["validade"]) and linha["validade"]
                    e_tv = st.checkbox("Tem validade?", value=bool(tv))
                    try:
                        dv = pd.to_datetime(linha["validade"]).date() if tv else date.today()
                    except Exception:
                        dv = date.today()
                    e_val = st.date_input("Validade", value=dv, disabled=not e_tv)
                    e_d = st.text_input("Doador", value=linha.get("doador","") or "")
                    e_m = st.number_input("Estoque mínimo", min_value=0,
                        value=int(linha.get("estoque_minimo",5) or 5))
                sv = st.form_submit_button("💾 Guardar alterações", use_container_width=True)
                if sv:
                    atualizar_item(iid, e_item, e_cat, int(e_qtd),
                                   e_val if e_tv else None, e_d, int(e_m))
                    st.success("✅ Item atualizado!")
                    st.rerun()

        if not df.empty:
            st.divider()
            c_csv, c_pdf = st.columns(2)
            with c_csv:
                st.download_button("⬇️ Exportar CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=f"inventario_{date.today()}.csv",
                    mime="text/csv", use_container_width=True)
            with c_pdf:
                botao_pdf(renomear(df.drop(columns=["id"], errors="ignore")),
                    "Inventário Filtrado", f"Categoria: {cat}",
                    f"inventario_{date.today()}.pdf")


# =========================================================
# 4. DAR BAIXA
# =========================================================
elif menu == "📤  Dar Baixa":
    section_title("📤 Registar Saída / Baixa")
    inv = carregar_inventario()
    if not inv.empty:
        opcoes = {f"{r['item']} — {r['categoria']} | stock: {r['quantidade']}": r["id"]
                  for _, r in inv.iterrows()}
        esc = st.selectbox("Item", list(opcoes.keys()))
        iid = opcoes[esc]
        smax = int(inv.loc[inv["id"] == iid, "quantidade"].iloc[0])

        with st.form("form_baixa"):
            c1, c2 = st.columns(2)
            with c1:
                qtd = st.number_input("Quantidade *", min_value=1,
                                      max_value=smax, value=min(1, smax))
                destino = st.text_input("Destino / Beneficiário")
            with c2:
                obs = st.text_area("Observações", height=100)
            ok = st.form_submit_button("📤 Confirmar", use_container_width=True)
            if ok:
                s, m = dar_baixa(iid, int(qtd), destino, obs)
                st.success(f"✅ {m}") if s else st.error(f"❌ {m}")
                if s: st.rerun()


# =========================================================
# 5. ALERTAS DE VALIDADE
# =========================================================
elif menu == "⚠️  Alertas de Validade":
    section_title("⚠️ Alertas de Validade")
    inv = carregar_inventario()
    if not inv.empty:
        df = inv.copy()
        df["_dt"] = pd.to_datetime(df["validade"], errors="coerce").dt.date
        h = date.today()
        venc = df[df["_dt"] < h]
        aven = df[(df["_dt"] >= h) & (df["_dt"] <= h + timedelta(days=DIAS_ALERTA))]
        sem = df[df["_dt"].isna()]

        c1, c2, c3 = st.columns(3)
        c1.markdown(kpi_card("🚫","Vencidos",len(venc),"#C73E1D"), unsafe_allow_html=True)
        c2.markdown(kpi_card("⚠️",f"A vencer ({DIAS_ALERTA}d)",len(aven),"#F18F01"), unsafe_allow_html=True)
        c3.markdown(kpi_card("❔","Sem validade",len(sem),"#6A4C93"), unsafe_allow_html=True)

        st.divider()
        if not venc.empty:
            st.error(f"🚫 **{len(venc)} lote(s) vencido(s)**")
            render_tabela(venc.drop(columns=["_dt"]))
        if not aven.empty:
            st.warning(f"⚠️ **{len(aven)} lote(s) a vencer**")
            render_tabela(aven.drop(columns=["_dt"]))
        if venc.empty and aven.empty:
            st.success("✅ Tudo em ordem!")
        if not sem.empty:
            with st.expander(f"❔ {len(sem)} sem validade"):
                render_tabela(sem.drop(columns=["_dt"]))

        if not venc.empty or not aven.empty:
            comb = pd.concat([venc, aven]).drop(columns=["_dt"])
            botao_pdf(renomear(comb.drop(columns=["id"], errors="ignore")),
                "Alertas de Validade", f"Vencidos: {len(venc)} | A vencer: {len(aven)}",
                f"alertas_{date.today()}.pdf")


# =========================================================
# 6. ESTOQUE BAIXO
# =========================================================
elif menu == "📉  Estoque Baixo":
    section_title("📉 Itens abaixo do estoque mínimo")
    inv = carregar_inventario()
    if inv.empty:
        st.info("Sem dados.")
    else:
        baixo = inv[inv["quantidade"] <= inv["estoque_minimo"]].sort_values("quantidade")
        if baixo.empty:
            st.success("✅ Nenhum item abaixo do mínimo definido.")
        else:
            st.warning(f"⚠️ **{len(baixo)} item(ns)** precisam de reposição.")
            render_tabela(baixo)
            botao_pdf(renomear(baixo.drop(columns=["id"], errors="ignore")),
                "Itens com Estoque Baixo", "Necessitam de reposição",
                f"estoque_baixo_{date.today()}.pdf")


# =========================================================
# 7. DOADORES
# =========================================================
elif menu == "👥  Doadores":
    section_title("👥 Doadores e Histórico")
    mov = carregar_movimentos()
    if mov.empty:
        st.info("Sem movimentos ainda.")
    else:
        ent = mov[mov["tipo"] == "Entrada"].copy()
        if ent.empty:
            st.info("Ainda sem doações registadas.")
        else:
            resumo = (ent.groupby("pessoa")
                .agg(Doações=("id","count"), Unidades=("quantidade","sum"), Última=("data","max"))
                .reset_index().rename(columns={"pessoa":"Doador"})
                .sort_values("Unidades", ascending=False))

            c1, c2, c3 = st.columns(3)
            c1.markdown(kpi_card("👥","Total doadores",len(resumo),"#2E86AB"), unsafe_allow_html=True)
            c2.markdown(kpi_card("📦","Unidades doadas",int(resumo["Unidades"].sum()),"#16a34a"), unsafe_allow_html=True)
            c3.markdown(kpi_card("📥","Doações totais",int(resumo["Doações"].sum()),"#6A4C93"), unsafe_allow_html=True)

            st.divider()
            col_a, col_b = st.columns([1,1])
            with col_a:
                st.markdown("##### 🏆 Top 10 doadores")
                top10 = resumo.head(10)
                fig = px.bar(top10, x="Unidades", y="Doador", orientation="h",
                    color="Unidades", color_continuous_scale="Blues", text="Unidades")
                fig.update_layout(height=400, showlegend=False, coloraxis_showscale=False,
                    margin=dict(l=0,r=0,t=10,b=0), yaxis=dict(autorange="reversed"),
                    paper_bgcolor="white", plot_bgcolor="rgba(0,0,0,0)")
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)
            with col_b:
                st.markdown("##### 📋 Ranking completo")
                st.dataframe(resumo, use_container_width=True, hide_index=True)

            st.divider()
            d = st.selectbox("Ver histórico de:", ["—"] + list(resumo["Doador"]))
            if d != "—":
                hist = ent[ent["pessoa"] == d][["data","item","categoria","quantidade"]]
                st.dataframe(renomear(hist), use_container_width=True, hide_index=True)

            botao_pdf(resumo, "Relatório de Doadores",
                f"Total: {len(resumo)} doadores", f"doadores_{date.today()}.pdf")


# =========================================================
# 8. RELATÓRIOS
# =========================================================
elif menu == "📈  Relatórios":
    section_title("📈 Relatórios e Análises")
    mov = carregar_movimentos()
    inv = carregar_inventario()
    if mov.empty:
        st.info("Sem dados para analisar.")
    else:
        df = mov.copy()
        df["_dt"] = pd.to_datetime(df["data"], errors="coerce")
        df["_mes"] = df["_dt"].dt.to_period("M").astype(str)

        t1, t2, t3 = st.tabs(["📅 Fluxo Mensal", "🏷️ Categorias", "🎯 Resumo"])

        with t1:
            fluxo = (df.groupby(["_mes","tipo"])["quantidade"].sum()
                     .reset_index().rename(columns={"_mes":"Mês","tipo":"Tipo","quantidade":"Qtd"}))
            fig = px.bar(fluxo, x="Mês", y="Qtd", color="Tipo", barmode="group",
                color_discrete_map={"Entrada":"#2E86AB","Saída":"#C73E1D",
                                    "Eliminação":"#999","Edição":"#F18F01"}, text="Qtd")
            fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0),
                paper_bgcolor="white", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(fluxo, use_container_width=True, hide_index=True)

        with t2:
            por_cat = (df[df["tipo"]=="Entrada"].groupby("categoria")["quantidade"]
                       .sum().reset_index().sort_values("quantidade", ascending=True))
            fig = px.bar(por_cat, x="quantidade", y="categoria", orientation="h",
                color="quantidade", color_continuous_scale="Greens", text="quantidade")
            fig.update_layout(height=420, showlegend=False, coloraxis_showscale=False,
                margin=dict(l=0,r=0,t=10,b=0), xaxis_title="", yaxis_title="",
                paper_bgcolor="white", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        with t3:
            ent = df[df["tipo"]=="Entrada"]; sai = df[df["tipo"]=="Saída"]
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(kpi_card("📥","Entradas",int(ent["quantidade"].sum()),"#16a34a"), unsafe_allow_html=True)
            c2.markdown(kpi_card("📤","Saídas",int(sai["quantidade"].sum()),"#C73E1D"), unsafe_allow_html=True)
            c3.markdown(kpi_card("🕓","Movimentos",len(df),"#6A4C93"), unsafe_allow_html=True)
            c4.markdown(kpi_card("📦","Stock atual",
                int(inv["quantidade"].sum()) if not inv.empty else 0,"#F18F01"), unsafe_allow_html=True)

            st.divider()
            st.markdown("##### Resumo por mês")
            resumo = (df.groupby(["_mes","tipo"])["quantidade"].sum()
                      .unstack(fill_value=0).reset_index().rename(columns={"_mes":"Mês"}))
            st.dataframe(resumo, use_container_width=True, hide_index=True)
            botao_pdf(resumo, "Relatório Mensal", "Resumo por mês e tipo",
                f"relatorio_{date.today()}.pdf")


# =========================================================
# 9. HISTÓRICO
# =========================================================
elif menu == "🕓  Histórico":
    section_title("🕓 Histórico de Movimentos")
    mov = carregar_movimentos()
    if not mov.empty:
        c1, c2, c3 = st.columns([1,1,1.2])
        with c1: tipo = st.selectbox("Tipo", ["Todos","Entrada","Saída","Eliminação","Edição"])
        with c2: per = st.selectbox("Período", ["Tudo","Últimos 7 dias","Últimos 30 dias"])
        with c3: busca = st.text_input("🔎 Pesquisar", "")

        df = mov.copy(); df["_dt"] = pd.to_datetime(df["data"], errors="coerce")
        if tipo != "Todos": df = df[df["tipo"] == tipo]
        if per == "Últimos 7 dias": df = df[df["_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
        elif per == "Últimos 30 dias": df = df[df["_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=30)]
        if busca.strip():
            b = busca.lower()
            df = df[df["item"].str.lower().str.contains(b, na=False)
                    | df["pessoa"].str.lower().str.contains(b, na=False)]

        st.metric("Movimentos filtrados", len(df))
        st.dataframe(renomear(df[["data","tipo","item","categoria","quantidade","pessoa","observacoes"]]),
            use_container_width=True, hide_index=True)

        if not df.empty:
            c_csv, c_pdf = st.columns(2)
            with c_csv:
                st.download_button("⬇️ CSV",
                    data=df.drop(columns=["_dt"]).to_csv(index=False).encode("utf-8"),
                    file_name=f"movimentos_{date.today()}.csv",
                    mime="text/csv", use_container_width=True)
            with c_pdf:
                botao_pdf(renomear(df.drop(columns=["_dt","id"], errors="ignore")),
                    "Histórico de Movimentos", f"Tipo: {tipo} | Período: {per}",
                    f"movimentos_{date.today()}.pdf")


# =========================================================
# 10. APAGAR
# =========================================================
elif menu == "🗑️  Apagar Item":
    section_title("🗑️ Apagar Item")
    inv = carregar_inventario()
    if not inv.empty:
        st.caption("⚠️ Ação irreversível. Para saída parcial usa **📤 Dar Baixa**.")
        opcoes = {f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']}": r["id"]
                  for _, r in inv.iterrows()}
        esc = st.selectbox("Item", list(opcoes.keys()))
        conf = st.checkbox("Confirmo que quero eliminar permanentemente.")
        if st.button("🗑️ Eliminar", type="primary", disabled=not conf):
            s, m = apagar_item(opcoes[esc])
            st.success(f"✅ {m}") if s else st.error(f"❌ {m}")
            if s: st.rerun()
