import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# =========================================================
# CONFIGURAÇÃO
# =========================================================
st.set_page_config(
    page_title="Gestão de Doações — Lar São Vicente",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "inventario.db"
CATEGORIAS = [
    "Alimentação",
    "Higiene Pessoal",
    "Limpeza",
    "Medicamentos",
    "Vestuário",
    "Outros",
]
DIAS_ALERTA = 30





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

        .login-box {
            max-width: 420px; margin: 3rem auto 0 auto;
            background: #ffffff; padding: 2rem 2rem 1.5rem 2rem;
            border-radius: 16px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.08);
            border-top: 5px solid #2E86AB;
        }
        .login-box h2 { margin: 0 0 .3rem 0; color: #2E86AB; text-align:center; }
        .login-box p { text-align:center; color:#666; margin-top:0; }

        .badge { display:inline-block; padding:.15rem .55rem; border-radius:8px;
                 font-size:.8rem; font-weight:600; }
        .badge-ok    { background:#d4edda; color:#155724; }
        .badge-warn  { background:#fff3cd; color:#856404; }
        .badge-danger{ background:#f8d7da; color:#721c24; }

        [data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 700; }
        [data-testid="stMetricLabel"] { font-size: .85rem; color: #555; }
        .stButton>button, .stDownloadButton>button { border-radius: 8px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# BASE DE DADOS
# =========================================================
def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventario (
                id TEXT PRIMARY KEY,
                item TEXT NOT NULL,
                categoria TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                validade TEXT,
                doador TEXT,
                data_entrada TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movimentos (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                tipo TEXT NOT NULL,
                item TEXT NOT NULL,
                categoria TEXT,
                quantidade INTEGER,
                pessoa TEXT,
                observacoes TEXT
            )
            """
        )


def carregar_inventario() -> pd.DataFrame:
    with conectar() as conn:
        return pd.read_sql_query(
            "SELECT * FROM inventario ORDER BY categoria, item", conn
        )


def carregar_movimentos() -> pd.DataFrame:
    with conectar() as conn:
        return pd.read_sql_query(
            "SELECT * FROM movimentos ORDER BY data DESC", conn
        )


def registar_entrada(item, categoria, quantidade, validade, doador):
    with conectar() as conn:
        cur = conn.execute(
            """
            SELECT id FROM inventario
            WHERE LOWER(item) = LOWER(?) AND IFNULL(validade,'') = ?
            """,
            (item, str(validade) if validade else ""),
        )
        existente = cur.fetchone()

        if existente:
            conn.execute(
                "UPDATE inventario SET quantidade = quantidade + ? WHERE id = ?",
                (quantidade, existente[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO inventario
                    (id, item, categoria, quantidade, validade, doador, data_entrada)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    item.strip(),
                    categoria,
                    quantidade,
                    str(validade) if validade else None,
                    doador.strip() or "Anónimo",
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

        conn.execute(
            """
            INSERT INTO movimentos
                (id, data, tipo, item, categoria, quantidade, pessoa, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                datetime.now().isoformat(timespec="seconds"),
                "Entrada",
                item.strip(),
                categoria,
                quantidade,
                doador.strip() or "Anónimo",
                "Doação registada",
            ),
        )


def dar_baixa(item_id, quantidade, destino, observacoes):
    with conectar() as conn:
        cur = conn.execute(
            "SELECT item, categoria, quantidade FROM inventario WHERE id = ?",
            (item_id,),
        )
        row = cur.fetchone()
        if not row:
            return False, "Item não encontrado."

        item, categoria, stock_atual = row
        if quantidade > stock_atual:
            return False, f"Stock insuficiente (disponível: {stock_atual})."

        nova_qtd = stock_atual - quantidade
        if nova_qtd == 0:
            conn.execute("DELETE FROM inventario WHERE id = ?", (item_id,))
        else:
            conn.execute(
                "UPDATE inventario SET quantidade = ? WHERE id = ?",
                (nova_qtd, item_id),
            )

        conn.execute(
            """
            INSERT INTO movimentos
                (id, data, tipo, item, categoria, quantidade, pessoa, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                datetime.now().isoformat(timespec="seconds"),
                "Saída",
                item,
                categoria,
                quantidade,
                destino.strip() or "—",
                observacoes.strip() or "Baixa de stock",
            ),
        )
        return True, "Baixa registada com sucesso."


def apagar_item(item_id):
    with conectar() as conn:
        cur = conn.execute(
            "SELECT item, categoria, quantidade FROM inventario WHERE id = ?",
            (item_id,),
        )
        row = cur.fetchone()
        if not row:
            return False, "Item não encontrado."
        item, categoria, qtd = row
        conn.execute("DELETE FROM inventario WHERE id = ?", (item_id,))
        conn.execute(
            """
            INSERT INTO movimentos
                (id, data, tipo, item, categoria, quantidade, pessoa, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                datetime.now().isoformat(timespec="seconds"),
                "Eliminação",
                item,
                categoria,
                qtd,
                "—",
                "Item eliminado do inventário",
            ),
        )
        return True, "Item eliminado."


# =========================================================
# AUTENTICAÇÃO
# =========================================================
def init_auth():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    if "utilizador" not in st.session_state:
        st.session_state.utilizador = None


def ecra_login():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown(
            """
            <div class="login-box">
                <h2>🏥 Lar São Vicente</h2>
                <p>Sistema de Doações e Inventário</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("form_login", clear_on_submit=False):
            user = st.text_input("👤 Utilizador", placeholder="ex.: admin")
            pw = st.text_input("🔒 Palavra-passe", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)

            if submit:
                usuarios = obter_usuarios()
                if user in usuarios and usuarios[user] == pw:
                    st.session_state.autenticado = True
                    st.session_state.utilizador = user
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas. Tenta novamente.")


def logout():
    st.session_state.autenticado = False
    st.session_state.utilizador = None
    st.rerun()


# =========================================================
# GERAÇÃO DE PDF
# =========================================================
def _registar_fonte_unicode():
    """Tenta registar uma fonte Unicode no reportlab."""
    candidatos = [
        ("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("Arial", "C:/Windows/Fonts/arial.ttf"),
        ("Arial", "/Library/Fonts/Arial.ttf"),
        ("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"),
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
    if pd.isna(valor):
        return ""
    return str(valor)


def gerar_pdf(df: pd.DataFrame, titulo: str, subtitulo: str = "") -> bytes:
    """Gera um PDF em landscape com a tabela passada."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=titulo,
    )

    fonte = _registar_fonte_unicode()
    estilos = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        "TituloCustom",
        parent=estilos["Title"],
        fontName=fonte,
        fontSize=16,
        textColor=colors.HexColor("#2E86AB"),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "SubCustom",
        parent=estilos["Normal"],
        fontName=fonte,
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=2,
    )

    story = [Paragraph(titulo, titulo_style)]
    if subtitulo:
        story.append(Paragraph(subtitulo, sub_style))
    story.append(
        Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} "
            f"por {st.session_state.get('utilizador', '—')}",
            sub_style,
        )
    )
    story.append(Spacer(1, 6 * mm))

    if df.empty:
        story.append(Paragraph("Sem dados para apresentar.", sub_style))
    else:
        cols = list(df.columns)
        dados = [cols] + [
            [_formatar_celula(v) for v in linha] for linha in df.values.tolist()
        ]

        tabela = Table(dados, repeatRows=1)
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, -1), fonte),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd8dc")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#f5f7fa")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(tabela)

    doc.build(story)
    return buffer.getvalue()


def botao_pdf(df: pd.DataFrame, titulo: str, subtitulo: str, nome_ficheiro: str):
    """Renderiza um botão de download de PDF."""
    pdf_bytes = gerar_pdf(df, titulo, subtitulo)
    st.download_button(
        "📄 Exportar PDF",
        data=pdf_bytes,
        file_name=nome_ficheiro,
        mime="application/pdf",
        use_container_width=False,
    )


# =========================================================
# HELPERS DE APRESENTAÇÃO
# =========================================================
def calcular_status_validade(validade_str):
    if not validade_str or pd.isna(validade_str):
        return "Sem validade", "badge-ok"
    try:
        d = pd.to_datetime(validade_str).date()
    except Exception:
        return "Inválida", "badge-warn"
    hoje = date.today()
    if d < hoje:
        return "Vencido", "badge-danger"
    if d <= hoje + timedelta(days=DIAS_ALERTA):
        return "A vencer", "badge-warn"
    return "OK", "badge-ok"


def renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas técnicas para apresentação."""
    mapa = {
        "item": "Item",
        "categoria": "Categoria",
        "quantidade": "Qtd",
        "validade": "Validade",
        "doador": "Doador",
        "data_entrada": "Data Entrada",
        "data": "Data/Hora",
        "tipo": "Tipo",
        "pessoa": "Pessoa",
        "observacoes": "Observações",
    }
    return df.rename(columns={k: v for k, v in mapa.items() if k in df.columns})


def render_tabela(df: pd.DataFrame):
    if df.empty:
        st.info("Sem registos para mostrar.")
        return
    df_show = df.copy()
    if "validade" in df_show.columns:
        df_show["Estado"] = df_show["validade"].apply(
            lambda v: calcular_status_validade(v)[0]
        )
    st.dataframe(renomear_colunas(df_show), use_container_width=True, hide_index=True)


# =========================================================
# INICIALIZAÇÃO
# =========================================================
init_db()
init_auth()

# --- ECRÃ DE LOGIN ---
if not st.session_state.autenticado:
    ecra_login()
    st.stop()

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
    st.markdown(f"### 👤 Olá, **{st.session_state.utilizador}**")
    if st.button("🚪 Terminar sessão", use_container_width=True):
        logout()

    st.divider()
    st.markdown("### 🧭 Navegação")
    menu = st.radio(
        "Menu",
        [
            "📊 Dashboard",
            "📦 Registar Doação",
            "🔍 Consultar Inventário",
            "📤 Dar Baixa / Saída",
            "⚠️ Alertas de Validade",
            "🕓 Histórico de Movimentos",
            "🗑️ Apagar Item",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("💡 Dados guardados automaticamente.")
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
        total_itens = len(inv)
        total_categorias = inv["categoria"].nunique()

        inv_valid = inv.copy()
        inv_valid["_status"] = inv_valid["validade"].apply(
            lambda v: calcular_status_validade(v)[0]
        )
        vencidos = int(inv_valid.loc[inv_valid["_status"] == "Vencido", "quantidade"].sum())
        a_vencer = int(inv_valid.loc[inv_valid["_status"] == "A vencer", "quantidade"].sum())

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📦 Unidades em stock", f"{total_unidades:,}".replace(",", "."))
        c2.metric("🏷️ Itens distintos", total_itens)
        c3.metric("📂 Categorias", total_categorias)
        c4.metric("⚠️ A vencer (30d)", a_vencer)
        c5.metric("🚫 Vencidos", vencidos)

        st.divider()

        col_a, col_b = st.columns([1.1, 1])
        with col_a:
            st.subheader("📊 Stock por Categoria")
            por_cat = (
                inv.groupby("categoria")["quantidade"].sum().sort_values(ascending=False)
            )
            st.bar_chart(por_cat, use_container_width=True)

        with col_b:
            st.subheader("🕓 Últimas Movimentações")
            if mov.empty:
                st.caption("Sem movimentos registados.")
            else:
                st.dataframe(
                    renomear_colunas(
                        mov[["data", "tipo", "item", "quantidade", "pessoa"]].head(8)
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        col_titulo, col_btn = st.columns([3, 1])
        with col_titulo:
            st.subheader("📋 Inventário Completo")
        with col_btn:
            botao_pdf(
                renomear_colunas(inv.drop(columns=["id"])),
                "Inventário Completo",
                "Lar São Vicente de Paulo",
                f"inventario_{date.today()}.pdf",
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
            item = st.text_input("Nome do Item *", placeholder="Ex.: Leite, Arroz, Detergente…")
            categoria = st.selectbox("Categoria *", CATEGORIAS)
            quantidade = st.number_input("Quantidade *", min_value=1, step=1, value=1)
        with col2:
            tem_validade = st.checkbox("Este item tem validade?", value=True)
            validade = st.date_input(
                "Data de Validade",
                value=date.today() + timedelta(days=90),
                disabled=not tem_validade,
            )
            doador = st.text_input("Doador / Origem", placeholder="Nome ou 'Anónimo'")

        submitted = st.form_submit_button("💾 Guardar Registo", use_container_width=True)

        if submitted:
            if not item.strip():
                st.warning("⚠️ Preenche o **Nome do Item**.")
            else:
                registar_entrada(
                    item=item,
                    categoria=categoria,
                    quantidade=int(quantidade),
                    validade=validade if tem_validade else None,
                    doador=doador,
                )
                st.success(f"✅ '{item}' registado com sucesso ({quantidade} un.).")
                st.balloons()


# =========================================================
# 3. CONSULTAR INVENTÁRIO
# =========================================================
elif menu == "🔍 Consultar Inventário":
    st.subheader("🔍 Consultar Inventário")
    inv = carregar_inventario()

    if inv.empty:
        st.info("Ainda não existem registos.")
    else:
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
            b = busca.lower()
            df = df[
                df["item"].str.lower().str.contains(b, na=False)
                | df["doador"].str.lower().str.contains(b, na=False)
            ]

        df = df.sort_values(
            ordem if ordem != "Validade" else "validade",
            ascending=(ordem != "Quantidade"),
            na_position="last",
        )

        m1, m2 = st.columns(2)
        m1.metric("Itens filtrados", len(df))
        m2.metric("Unidades totais", int(df["quantidade"].sum()) if not df.empty else 0)

        render_tabela(df)

        if not df.empty:
            col_csv, col_pdf = st.columns(2)
            with col_csv:
                st.download_button(
                    "⬇️ Exportar CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=f"inventario_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_pdf:
                botao_pdf(
                    renomear_colunas(df.drop(columns=["id"], errors="ignore")),
                    "Inventário Filtrado",
                    f"Filtro: categoria={cat} | busca='{busca or '—'}'",
                    f"inventario_{date.today()}.pdf",
                )


# =========================================================
# 4. DAR BAIXA
# =========================================================
elif menu == "📤 Dar Baixa / Saída":
    st.subheader("📤 Registar Saída / Baixa de Stock")
    inv = carregar_inventario()

    if inv.empty:
        st.info("Não existem itens no inventário.")
    else:
        opcoes = {
            f"{r['item']} — {r['categoria']} | stock: {r['quantidade']} | val: {r['validade'] or '—'}": r["id"]
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
                    value=min(1, stock_max),
                )
                destino = st.text_input("Destino / Beneficiário", placeholder="Ex.: Cozinha, D. Maria…")
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

    if inv.empty:
        st.info("Não existem itens no inventário.")
    else:
        df = inv.copy()
        df["_validade_dt"] = pd.to_datetime(df["validade"], errors="coerce").dt.date
        hoje = date.today()

        vencidos = df[df["_validade_dt"] < hoje]
        a_vencer = df[
            (df["_validade_dt"] >= hoje)
            & (df["_validade_dt"] <= hoje + timedelta(days=DIAS_ALERTA))
        ]
        sem_val = df[df["_validade_dt"].isna()]

        c1, c2, c3 = st.columns(3)
        c1.metric("🚫 Vencidos", len(vencidos))
        c2.metric(f"⚠️ A vencer ({DIAS_ALERTA}d)", len(a_vencer))
        c3.metric("❔ Sem validade", len(sem_val))

        st.divider()

        if not vencidos.empty:
            st.error(f"🚫 **{len(vencidos)} lote(s) vencido(s)** — retirar do stock!")
            render_tabela(vencidos.drop(columns=["_validade_dt"]))

        if not a_vencer.empty:
            st.warning(f"⚠️ **{len(a_vencer)} lote(s) a vencer nos próximos {DIAS_ALERTA} dias**")
            render_tabela(a_vencer.drop(columns=["_validade_dt"]))

        if vencidos.empty and a_vencer.empty:
            st.success(f"✅ Nenhum produto vencido ou a vencer nos próximos {DIAS_ALERTA} dias.")

        if not sem_val.empty:
            with st.expander(f"❔ {len(sem_val)} item(ns) sem validade registada"):
                render_tabela(sem_val.drop(columns=["_validade_dt"]))

        if not vencidos.empty or not a_vencer.empty:
            combinado = pd.concat([vencidos, a_vencer]).drop(columns=["_validade_dt"])
            botao_pdf(
                renomear_colunas(combinado.drop(columns=["id"], errors="ignore")),
                "Alertas de Validade",
                f"Vencidos: {len(vencidos)} | A vencer ({DIAS_ALERTA}d): {len(a_vencer)}",
                f"alertas_{date.today()}.pdf",
            )


# =========================================================
# 6. HISTÓRICO
# =========================================================
elif menu == "🕓 Histórico de Movimentos":
    st.subheader("🕓 Histórico de Movimentos")
    mov = carregar_movimentos()

    if mov.empty:
        st.info("Ainda não existem movimentos registados.")
    else:
        col1, col2, col3 = st.columns([1, 1, 1.2])
        with col1:
            tipo = st.selectbox("Tipo", ["Todos", "Entrada", "Saída", "Eliminação"])
        with col2:
            dias = st.selectbox("Período", ["Tudo", "Últimos 7 dias", "Últimos 30 dias"])
        with col3:
            busca = st.text_input("🔎 Pesquisar", "")

        df = mov.copy()
        df["_dt"] = pd.to_datetime(df["data"], errors="coerce")

        if tipo != "Todos":
            df = df[df["tipo"] == tipo]
        if dias == "Últimos 7 dias":
            df = df[df["_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
        elif dias == "Últimos 30 dias":
            df = df[df["_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=30)]
        if busca.strip():
            b = busca.lower()
            df = df[
                df["item"].str.lower().str.contains(b, na=False)
                | df["pessoa"].str.lower().str.contains(b, na=False)
            ]

        st.metric("Movimentos filtrados", len(df))

        st.dataframe(
            renomear_colunas(
                df[["data", "tipo", "item", "categoria", "quantidade", "pessoa", "observacoes"]]
            ),
            use_container_width=True,
            hide_index=True,
        )

        if not df.empty:
            col_csv, col_pdf = st.columns(2)
            with col_csv:
                st.download_button(
                    "⬇️ Exportar CSV",
                    data=df.drop(columns=["_dt"]).to_csv(index=False).encode("utf-8"),
                    file_name=f"movimentos_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_pdf:
                botao_pdf(
                    renomear_colunas(df.drop(columns=["_dt", "id"], errors="ignore")),
                    "Histórico de Movimentos",
                    f"Tipo: {tipo} | Período: {dias}",
                    f"movimentos_{date.today()}.pdf",
                )


# =========================================================
# 7. APAGAR
# =========================================================
elif menu == "🗑️ Apagar Item":
    st.subheader("🗑️ Apagar Item do Inventário")
    inv = carregar_inventario()

    if inv.empty:
        st.info("Não existem itens para apagar.")
    else:
        st.caption("⚠️ Ação irreversível. Para saída parcial usa **📤 Dar Baixa / Saída**.")

        opcoes = {
            f"{r['item']} — {r['categoria']} | qtd: {r['quantidade']} | val: {r['validade'] or '—'}": r["id"]
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
