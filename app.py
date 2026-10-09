import os
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import plotly.express as px
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
    "Alimentação",
    "Higiene Pessoal",
    "Limpeza",
    "Medicamentos",
    "Vestuário",
    "Outros",
]

conn = st.connection("supabase_connection", type=SupabaseConnection)


# =========================================================
# CSS
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

        div[data-testid="stMetric"] {
            background: #ffffff; padding: .9rem 1rem; border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-left: 4px solid #2E86AB;
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
    validade_str = str(validade) if validade else None
    r = (
        conn.table("inventario")
        .select("id, quantidade")
        .eq("item", item)
        .eq("validade", validade_str)
        .execute()
    )
    if r.data:
        item_id = r.data[0]["id"]
        nova = r.data[0]["quantidade"] + quantidade
        conn.table("inventario").update(
            {"quantidade": nova, "estoque_minimo": estoque_minimo}
        ).eq("id", item_id).execute()
    else:
        conn.table("inventario").insert({
            "id": str(uuid.uuid4()),
            "item": item.strip(),
            "categoria": categoria,
            "quantidade": quantidade,
            "validade": validade_str,
            "doador": doador.strip() or "Anónimo",
            "estoque_minimo": estoque_minimo,
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


def atualizar_item(item_id, item, categoria, quantidade, validade, doador, estoque_minimo):
    conn.table("inventario").update({
        "item": item.strip(),
        "categoria": categoria,
        "quantidade": quantidade,
        "validade": str(validade) if validade else None,
        "doador": doador.strip() or "Anónimo",
        "estoque_minimo": estoque_minimo,
    }).eq("id", item_id).execute()

    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Edição",
        "item": item.strip(),
        "categoria": categoria,
        "quantidade": quantidade,
        "pessoa": "Sistema",
        "observacoes": "Item editado",
    }).execute()
    st.cache_data.clear()


def dar_baixa(item_id, quantidade, destino, observacoes):
    r = conn.table("inventario").select("item, categoria, quantidade").eq("id", item_id).execute()
    if not r.data:
        return False, "Item não encontrado."
    item, categoria, stock = r.data[0]["item"], r.data[0]["categoria"], r.data[0]["quantidade"]
    if quantidade > stock:
        return False, f"Stock insuficiente (disponível: {stock})."

    nova = stock - quantidade
    if nova == 0:
        conn.table("inventario").delete().eq("id", item_id).execute()
    else:
        conn.table("inventario").update({"quantidade": nova}).eq("id", item_id).execute()

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
    return True, "Baixa registada."


def apagar_item(item_id):
    r = conn.table("inventario").select("item, categoria, quantidade").eq("id", item_id).execute()
    if not r.data:
        return False, "Item não encontrado."
    item, categoria, qtd = r.data[0]["item"], r.data[0]["categoria"], r.data[0]["quantidade"]
    conn.table("inventario").delete().eq("id", item_id).execute()
    conn.table("movimentos").insert({
        "id": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "tipo": "Eliminação",
        "item": item,
        "categoria": categoria,
        "quantidade": qtd,
        "pessoa": "Sistema",
        "observacoes": "Item eliminado",
    }).execute()
    st.cache_data.clear()
    return True, "Item eliminado."


# =========================================================
# PDF
# =========================================================
@st.cache_resource
def _fonte_unicode():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for nome, path in [
        ("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("Arial", "C:/Windows/Fonts/arial.ttf"),
    ]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(nome, path))
                return nome
            except Exception:
                continue
    return "Helvetica"


def _fmt(v):
    return "" if pd.isna(v) else str(v)


def gerar_pdf(df, titulo, subtitulo=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm,
        title=titulo,
    )
    fonte = _fonte_unicode()
    estilos = getSampleStyleSheet()
    t_style = ParagraphStyle("T", parent=estilos["Title"], fontName=fonte,
                             fontSize=16, textColor=colors.HexColor("#2E86AB"), spaceAfter=4)
    s_style = ParagraphStyle("S", parent=estilos["Normal"], fontName=fonte,
                             fontSize=9, textColor=colors.HexColor("#666666"), spaceAfter=2)

    story = [Paragraph(titulo, t_style)]
    if subtitulo:
        story.append(Paragraph(subtitulo, s_style))
    story.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_style))
    story.append(Spacer(1, 6 * mm))

    if df.empty:
        story.append(Paragraph("Sem dados.", s_style))
    else:
        dados = [list(df.columns)] + [[_fmt(v) for v in row] for row in df.values.tolist()]
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


def botao_pdf(df, titulo, subtitulo, nome):
    chave = f"pdf_{nome}"
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 Preparar PDF", key=f"btn_{nome}", use_container_width=True):
            with st.spinner("Gerando PDF..."):
                st.session_state[chave] = gerar_pdf(df, titulo, subtitulo)
    if chave in st.session_state:
        with c2:
            st.download_button(
                "⬇️ Descarregar PDF",
                data=st.session_state[chave],
                file_name=nome,
                mime="application/pdf",
                use_container_width=True,
            )


# =========================================================
# HELPERS
# =========================================================
def status_validade(v):
    if not v or pd.isna(v):
        return "Sem validade"
    try:
        d = pd.to_datetime(v).date()
    except Exception:
        return "Inválida"
    hoje = date.today()
    if d < hoje:
        return "Vencido"
    if d <= hoje + timedelta(days=DIAS_ALERTA):
        return "A vencer"
    return "OK"


def renomear(df):
    mapa = {
        "item": "Item", "categoria": "Categoria", "quantidade": "Qtd",
        "validade": "Validade", "doador": "Doador", "data_entrada": "Data Entrada",
        "data": "Data/Hora", "tipo": "Tipo", "pessoa": "Pessoa",
        "observacoes": "Observações", "estoque_minimo": "Est. Mínimo",
    }
    return df.rename(columns={k: v for k, v in mapa.items() if k in df.columns})


def render_tabela(df):
    if df.empty:
        st.info("Sem registos.")
        return
    d = df.copy()
    if "validade" in d.columns:
        d["Estado"] = d["validade"].apply(status_validade)
    st.dataframe(renomear(d), use_container_width=True, hide_index=True)


def card_kpi(col, icone, label, valor, cor="#2E86AB"):
    col.markdown(
        f"""
        <div style="background:#fff;padding:1rem;border-radius:12px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.05);
                    border-left:4px solid {cor};height:100%">
            <div style="font-size:.85rem;color:#555">{icone} {label}</div>
            <div style="font-size:1.7rem;font-weight:700;color:#222;margin-top:.3rem">{valor}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# CABEÇALHO
# =========================================================
st.markdown(
    """
    <div class="main-header">
        <h1>🏥 Sistema de Controlo de Doações e Inventário</h1>
        <p>Lar São Vicente de Paulo — São José do Rio Preto · Projeto de Extensão UNIP</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# MENU LATERAL
# =========================================================
with st.sidebar:
    st.markdown("### 🏥 Lar São Vicente")
    menu = st.radio(
        "Menu",
        [
            "📊 Dashboard",
            "📦 Registar Doação",
            "🔍 Consultar Inventário",
            "📤 Dar Baixa / Saída",
            "⚠️ Alertas de Validade",
            "📉 Estoque Baixo",
            "👥 Doadores",
            "📈 Relatórios",
            "🕓 Histórico",
            "🗑️ Apagar Item",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("💡 Dados guardados no Supabase.")
    if st.button("🔄 Recarregar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# =========================================================
# 1. DASHBOARD
# =========================================================
if menu == "📊 Dashboard":
    inv = carregar_inventario()
    mov = carregar_movimentos()

    if inv.empty:
        st.info("Ainda não há dados. Começa em **📦 Registar Doação**.")
    else:
        inv["_status"] = inv["validade"].apply(status_validade)
        total_un = int(inv["quantidade"].sum())
        venc = int(inv.loc[inv["_status"] == "Vencido", "quantidade"].sum())
        aven = int(inv.loc[inv["_status"] == "A vencer", "quantidade"].sum())
        baixo = int((inv["quantidade"] <= inv["estoque_minimo"]).sum())

        c1, c2, c3, c4, c5 = st.columns(5)
        card_kpi(c1, "📦", "Unidades em stock", f"{total_un:,}".replace(",", "."))
        card_kpi(c2, "🏷️", "Itens distintos", len(inv), "#6A4C93")
        card_kpi(c3, "📂", "Categorias", inv["categoria"].nunique(), "#F18F01")
        card_kpi(c4, "⚠️", "A vencer (30d)", aven, "#F18F01")
        card_kpi(c5, "🚫", "Vencidos", venc, "#C73E1D")

        st.divider()

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("📊 Stock por Categoria")
            por_cat = (
                inv.groupby("categoria", as_index=False)["quantidade"]
                .sum().sort_values("quantidade", ascending=False)
            )
            fig = px.bar(
                por_cat, x="categoria", y="quantidade",
                color="categoria",
                color_discrete_sequence=px.colors.qualitative.Set2,
                text="quantidade",
            )
            fig.update_layout(
                showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                height=320, xaxis_title="", yaxis_title="Unidades",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.subheader("🥧 Distribuição por Categoria")
            fig2 = px.pie(
                por_cat, names="categoria", values="quantidade", hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.subheader("🕓 Últimas Movimentações")
            if mov.empty:
                st.caption("Sem movimentos.")
            else:
                st.dataframe(
                    renomear(mov[["data", "tipo", "item", "quantidade", "pessoa"]].head(8)),
                    use_container_width=True, hide_index=True,
                )
        with c2:
            st.subheader("📉 Top 5 — Estoque Baixo")
            top_baixo = (
                inv[inv["quantidade"] <= inv["estoque_minimo"]]
                .sort_values("quantidade")[["item", "quantidade", "estoque_minimo"]]
                .head(5)
            )
            if top_baixo.empty:
                st.success("✅ Nenhum item abaixo do mínimo.")
            else:
                st.dataframe(renomear(top_baixo), use_container_width=True, hide_index=True)

        st.divider()
        col_t, col_p = st.columns([3, 1])
        with col_t:
            st.subheader("📋 Inventário Completo")
        with col_p:
            botao_pdf(
                renomear(inv.drop(columns=["id", "_status"], errors="ignore")),
                "Inventário Completo", "Lar São Vicente de Paulo",
                f"inventario_{date.today()}.pdf",
            )
        render_tabela(inv.drop(columns=["_status"]))

# =========================================================
# 2. REGISTAR DOAÇÃO
# =========================================================
elif menu == "📦 Registar Doação":
    st.subheader("📦 Registar Nova Doação ou Entrada")
    with st.form("form_doacao", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            item = st.text_input("Nome do Item *", placeholder="Ex.: Leite, Arroz…")
            categoria = st.selectbox("Categoria *", CATEGORIAS_PADRAO)
            quantidade = st.number_input("Quantidade *", min_value=1, step=1, value=1)
            estoque_minimo = st.number_input(
                "Estoque mínimo (alerta)", min_value=0, step=1, value=5,
                help="Avisa quando o stock ficar abaixo deste valor.",
            )
        with c2:
            tem_validade = st.checkbox("Este item tem validade?", value=True)
            validade = st.date_input(
                "Data de Validade",
                value=date.today() + timedelta(days=90),
                disabled=not tem_validade,
            )
            doador = st.text_input("Doador / Origem", placeholder="Nome ou 'Anónimo'")

        ok = st.form_submit_button("💾 Guardar Registo", use_container_width=True)
        if ok:
            if not item.strip():
                st.warning("⚠️ Preenche o **Nome do Item**.")
            else:
                registar_entrada(
                    item, categoria, int(quantidade),
                    validade if tem_validade else None,
                    doador, int(estoque_minimo),
                )
                st.success(f"✅ '{item}' registado!")
                st.balloons()

# =========================================================
# 3. CONSULTAR INVENTÁRIO (+ EDITAR)
# =========================================================
elif menu == "🔍 Consultar Inventário":
    st.subheader("🔍 Consultar / Editar Inventário")
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
            df = df[
                df["item"].str.lower().str.contains(b, na=False)
                | df["doador"].str.lower().str.contains(b, na=False)
            ]

        mapa = {"Item": "item", "Quantidade": "quantidade", "Validade": "validade"}
        df = df.sort_values(
            by=mapa.get(ordem, "item"),
            ascending=(ordem != "Quantidade"),
            na_position="last",
        )

        m1, m2 = st.columns(2)
        m1.metric("Itens filtrados", len(df))
        m2.metric("Unidades totais", int(df["quantidade"].sum()) if not df.empty else 0)

        render_tabela(df)

        st.divider()
        st.markdown("### ✏️ Editar item")

        if df.empty:
            st.caption("Sem itens para editar.")
        else:
            opcoes = {
                f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']}": r["id"]
                for _, r in df.iterrows()
            }
            escolha = st.selectbox("Escolhe o item a editar", list(opcoes.keys()), key="sel_edit")
            item_id = opcoes[escolha]
            linha = inv[inv["id"] == item_id].iloc[0]

            with st.form("form_edit"):
                c1, c2 = st.columns(2)
                with c1:
                    e_item = st.text_input("Nome", value=linha["item"])
                    e_cat = st.selectbox(
                        "Categoria", CATEGORIAS_PADRAO,
                        index=CATEGORIAS_PADRAO.index(linha["categoria"])
                        if linha["categoria"] in CATEGORIAS_PADRAO else 0,
                    )
                    e_qtd = st.number_input("Quantidade", min_value=0, value=int(linha["quantidade"]))
                with c2:
                    tem_val = pd.notna(linha["validade"]) and linha["validade"]
                    e_tem_val = st.checkbox("Tem validade?", value=bool(tem_val))
                    try:
                        dt_val = pd.to_datetime(linha["validade"]).date() if tem_val else date.today()
                    except Exception:
                        dt_val = date.today()
                    e_val = st.date_input("Validade", value=dt_val, disabled=not e_tem_val)
                    e_doador = st.text_input("Doador", value=linha.get("doador", "") or "")
                    e_min = st.number_input(
                        "Estoque mínimo", min_value=0,
                        value=int(linha.get("estoque_minimo", 5) or 5),
                    )

                salvar = st.form_submit_button("💾 Guardar alterações", use_container_width=True)
                if salvar:
                    atualizar_item(
                        item_id, e_item, e_cat, int(e_qtd),
                        e_val if e_tem_val else None,
                        e_doador, int(e_min),
                    )
                    st.success("✅ Item atualizado!")
                    st.rerun()

        if not df.empty:
            st.divider()
            c_csv, c_pdf = st.columns(2)
            with c_csv:
                st.download_button(
                    "⬇️ Exportar CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=f"inventario_{date.today()}.csv",
                    mime="text/csv", use_container_width=True,
                )
            with c_pdf:
                botao_pdf(
                    renomear(df.drop(columns=["id"], errors="ignore")),
                    "Inventário Filtrado", f"Categoria: {cat}",
                    f"inventario_{date.today()}.pdf",
                )

# =========================================================
# 4. DAR BAIXA
# =========================================================
elif menu == "📤 Dar Baixa / Saída":
    st.subheader("📤 Registar Saída / Baixa")
    inv = carregar_inventario()
    if not inv.empty:
        opcoes = {
            f"{r['item']} — {r['categoria']} | stock: {r['quantidade']}": r["id"]
            for _, r in inv.iterrows()
        }
        escolha = st.selectbox("Item", list(opcoes.keys()))
        item_id = opcoes[escolha]
        stock_max = int(inv.loc[inv["id"] == item_id, "quantidade"].iloc[0])

        with st.form("form_baixa"):
            c1, c2 = st.columns(2)
            with c1:
                qtd = st.number_input(
                    "Quantidade *", min_value=1,
                    max_value=stock_max, value=min(1, stock_max),
                )
                destino = st.text_input("Destino / Beneficiário")
            with c2:
                obs = st.text_area("Observações", height=100)
            ok = st.form_submit_button("📤 Confirmar", use_container_width=True)
            if ok:
                s, m = dar_baixa(item_id, int(qtd), destino, obs)
                st.success(f"✅ {m}") if s else st.error(f"❌ {m}")
                if s:
                    st.rerun()

# =========================================================
# 5. ALERTAS DE VALIDADE
# =========================================================
elif menu == "⚠️ Alertas de Validade":
    st.subheader("⚠️ Alertas de Validade")
    inv = carregar_inventario()
    if not inv.empty:
        df = inv.copy()
        df["_dt"] = pd.to_datetime(df["validade"], errors="coerce").dt.date
        hoje = date.today()

        venc = df[df["_dt"] < hoje]
        aven = df[(df["_dt"] >= hoje) & (df["_dt"] <= hoje + timedelta(days=DIAS_ALERTA))]
        sem = df[df["_dt"].isna()]

        c1, c2, c3 = st.columns(3)
        card_kpi(c1, "🚫", "Vencidos", len(venc), "#C73E1D")
        card_kpi(c2, "⚠️", f"A vencer ({DIAS_ALERTA}d)", len(aven), "#F18F01")
        card_kpi(c3, "❔", "Sem validade", len(sem), "#6A4C93")

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
            combinado = pd.concat([venc, aven]).drop(columns=["_dt"])
            botao_pdf(
                renomear(combinado.drop(columns=["id"], errors="ignore")),
                "Alertas de Validade",
                f"Vencidos: {len(venc)} | A vencer: {len(aven)}",
                f"alertas_{date.today()}.pdf",
            )

# =========================================================
# 6. ESTOQUE BAIXO
# =========================================================
elif menu == "📉 Estoque Baixo":
    st.subheader("📉 Itens abaixo do estoque mínimo")
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
            botao_pdf(
                renomear(baixo.drop(columns=["id"], errors="ignore")),
                "Itens com Estoque Baixo", "Necessitam de reposição",
                f"estoque_baixo_{date.today()}.pdf",
            )

# =========================================================
# 7. DOADORES
# =========================================================
elif menu == "👥 Doadores":
    st.subheader("👥 Doadores e Histórico")
    mov = carregar_movimentos()
    if mov.empty:
        st.info("Sem movimentos ainda.")
    else:
        entradas = mov[mov["tipo"] == "Entrada"].copy()
        if entradas.empty:
            st.info("Ainda sem doações registadas.")
        else:
            resumo = (
                entradas.groupby("pessoa")
                .agg(Doações=("id", "count"), Unidades=("quantidade", "sum"), Última=("data", "max"))
                .reset_index()
                .rename(columns={"pessoa": "Doador"})
                .sort_values("Unidades", ascending=False)
            )

            c1, c2 = st.columns(2)
            c1.metric("👥 Total de doadores", len(resumo))
            c2.metric("📦 Unidades doadas", int(resumo["Unidades"].sum()))

            st.divider()
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.markdown("#### 🏆 Top 10 doadores")
                top10 = resumo.head(10)
                fig = px.bar(
                    top10, x="Unidades", y="Doador", orientation="h",
                    color="Unidades", color_continuous_scale="Blues", text="Unidades",
                )
                fig.update_layout(
                    height=380, showlegend=False, coloraxis_showscale=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis=dict(autorange="reversed"),
                )
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                st.markdown("#### 📋 Tabela completa")
                st.dataframe(resumo, use_container_width=True, hide_index=True)

            st.divider()
            doador_sel = st.selectbox("Ver histórico de:", ["—"] + list(resumo["Doador"]))
            if doador_sel != "—":
                hist = entradas[entradas["pessoa"] == doador_sel][
                    ["data", "item", "categoria", "quantidade"]
                ].sort_values("data", ascending=False)
                st.dataframe(renomear(hist), use_container_width=True, hide_index=True)

            botao_pdf(
                resumo, "Relatório de Doadores",
                f"Total: {len(resumo)} doadores",
                f"doadores_{date.today()}.pdf",
            )

# =========================================================
# 8. RELATÓRIOS
# =========================================================
elif menu == "📈 Relatórios":
    st.subheader("📈 Relatórios e Análises")
    mov = carregar_movimentos()
    inv = carregar_inventario()

    if mov.empty:
        st.info("Sem dados para analisar.")
    else:
        df = mov.copy()
        df["_dt"] = pd.to_datetime(df["data"], errors="coerce")
        df["_mes"] = df["_dt"].dt.to_period("M").astype(str)

        tab1, tab2, tab3 = st.tabs(["📅 Fluxo Mensal", "🏷️ Categorias", "🎯 Resumo"])

        with tab1:
            fluxo = (
                df.groupby(["_mes", "tipo"])["quantidade"]
                .sum().reset_index()
                .rename(columns={"_mes": "Mês", "tipo": "Tipo", "quantidade": "Qtd"})
            )
            fig = px.bar(
                fluxo, x="Mês", y="Qtd", color="Tipo", barmode="group",
                color_discrete_map={
                    "Entrada": "#2E86AB", "Saída": "#C73E1D",
                    "Eliminação": "#999", "Edição": "#F18F01",
                },
                text="Qtd",
            )
            fig.update_layout(
                height=400, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(fluxo, use_container_width=True, hide_index=True)

        with tab2:
            por_cat = (
                df[df["tipo"] == "Entrada"]
                .groupby("categoria")["quantidade"].sum()
                .reset_index().sort_values("quantidade", ascending=False)
            )
            fig = px.bar(
                por_cat, x="quantidade", y="categoria", orientation="h",
                color="quantidade", color_continuous_scale="Greens", text="quantidade",
            )
            fig.update_layout(
                height=400, showlegend=False, coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="Unidades recebidas", yaxis_title="",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab3:
            entradas = df[df["tipo"] == "Entrada"]
            saidas = df[df["tipo"] == "Saída"]
            c1, c2, c3, c4 = st.columns(4)
            card_kpi(c1, "📥", "Total entradas", int(entradas["quantidade"].sum()))
            card_kpi(c2, "📤", "Total saídas", int(saidas["quantidade"].sum()), "#C73E1D")
            card_kpi(c3, "🕓", "Movimentos", len(df), "#6A4C93")
            card_kpi(c4, "📦", "Stock atual", int(inv["quantidade"].sum()) if not inv.empty else 0, "#F18F01")

            st.divider()
            st.markdown("#### Resumo por mês")
            resumo_mes = (
                df.groupby(["_mes", "tipo"])["quantidade"].sum()
                .unstack(fill_value=0).reset_index()
                .rename(columns={"_mes": "Mês"})
            )
            st.dataframe(resumo_mes, use_container_width=True, hide_index=True)

            botao_pdf(
                resumo_mes, "Relatório Mensal",
                "Resumo por mês e tipo de movimento",
                f"relatorio_{date.today()}.pdf",
            )

# =========================================================
# 9. HISTÓRICO
# =========================================================
elif menu == "🕓 Histórico":
    st.subheader("🕓 Histórico de Movimentos")
    mov = carregar_movimentos()
    if not mov.empty:
        c1, c2, c3 = st.columns([1, 1, 1.2])
        with c1:
            tipo = st.selectbox("Tipo", ["Todos", "Entrada", "Saída", "Eliminação", "Edição"])
        with c2:
            per = st.selectbox("Período", ["Tudo", "Últimos 7 dias", "Últimos 30 dias"])
        with c3:
            busca = st.text_input("🔎 Pesquisar", "")

        df = mov.copy()
        df["_dt"] = pd.to_datetime(df["data"], errors="coerce")

        if tipo != "Todos":
            df = df[df["tipo"] == tipo]
        if per == "Últimos 7 dias":
            df = df[df["_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
        elif per == "Últimos 30 dias":
            df = df[df["_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=30)]
        if busca.strip():
            b = busca.lower()
            df = df[
                df["item"].str.lower().str.contains(b, na=False)
                | df["pessoa"].str.lower().str.contains(b, na=False)
            ]

        st.metric("Movimentos filtrados", len(df))
        st.dataframe(
            renomear(df[["data", "tipo", "item", "categoria", "quantidade", "pessoa", "observacoes"]]),
            use_container_width=True, hide_index=True,
        )

        if not df.empty:
            c_csv, c_pdf = st.columns(2)
            with c_csv:
                st.download_button(
                    "⬇️ CSV",
                    data=df.drop(columns=["_dt"]).to_csv(index=False).encode("utf-8"),
                    file_name=f"movimentos_{date.today()}.csv",
                    mime="text/csv", use_container_width=True,
                )
            with c_pdf:
                botao_pdf(
                    renomear(df.drop(columns=["_dt", "id"], errors="ignore")),
                    "Histórico de Movimentos",
                    f"Tipo: {tipo} | Período: {per}",
                    f"movimentos_{date.today()}.pdf",
                )

# =========================================================
# 10. APAGAR
# =========================================================
elif menu == "🗑️ Apagar Item":
    st.subheader("🗑️ Apagar Item")
    inv = carregar_inventario()
    if not inv.empty:
        st.caption("⚠️ Ação irreversível. Para saída parcial usa **📤 Dar Baixa**.")
        opcoes = {
            f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']}": r["id"]
            for _, r in inv.iterrows()
        }
        escolha = st.selectbox("Item", list(opcoes.keys()))
        conf = st.checkbox("Confirmo que quero eliminar permanentemente.")
        if st.button("🗑️ Eliminar", type="primary", disabled=not conf):
            s, m = apagar_item(opcoes[escolha])
            st.success(f"✅ {m}") if s else st.error(f"❌ {m}")
            if s:
                st.rerun()
