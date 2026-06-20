import streamlit as st
import streamlit.components.v1
import requests
import html
from typing import Dict, Any

API_URL = "http://localhost:8000"

st.set_page_config(page_title="DocuMind Graph", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    color: #e2e8f0;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem; }

.hero {
    text-align: center;
    padding: 2.5rem 1rem 1.5rem;
    background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.1) 100%);
    border-radius: 20px;
    border: 1px solid rgba(99,102,241,0.25);
    margin-bottom: 2rem;
}
.hero h1 {
    font-size: 2.8rem; font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #c084fc, #38bdf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;
}
.hero p { color: #94a3b8; font-size: 1rem; margin-top: 0.5rem; letter-spacing: 0.05em; }
.hero-badges { display: flex; justify-content: center; gap: 0.6rem; margin-top: 1rem; flex-wrap: wrap; }
.badge {
    background: rgba(99,102,241,0.2); border: 1px solid rgba(99,102,241,0.4);
    color: #a5b4fc; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 500;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e1b4b 100%);
    border-right: 1px solid rgba(99,102,241,0.2);
}
.sidebar-label {
    font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.1em; color: #6366f1; margin-bottom: 0.5rem;
}

[data-testid="stFileUploader"] {
    background: rgba(15,23,42,0.6) !important;
    border: 2px dashed rgba(99,102,241,0.4) !important;
    border-radius: 12px !important;
}

.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    padding: 0.6rem 1.5rem !important; font-weight: 600 !important; font-size: 0.875rem !important;
    width: 100% !important; transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(99,102,241,0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(99,102,241,0.5) !important;
}

[data-testid="stChatMessage"] {
    background: rgba(30,27,75,0.5) !important; border: 1px solid rgba(99,102,241,0.15) !important;
    border-radius: 16px !important; margin-bottom: 0.75rem !important;
    padding: 1rem !important; backdrop-filter: blur(10px);
}
[data-testid="stChatInput"] {
    background: rgba(15,23,42,0.8) !important; border: 1px solid rgba(99,102,241,0.4) !important;
    border-radius: 14px !important; color: #e2e8f0 !important;
}

.metric-card {
    background: rgba(30,27,75,0.6); border: 1px solid rgba(99,102,241,0.2);
    border-radius: 14px; padding: 1.2rem; text-align: center; backdrop-filter: blur(10px);
}
.metric-value {
    font-size: 1.8rem; font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #c084fc);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.metric-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.25rem; }

.status-online {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: rgba(34,197,94,0.15); border: 1px solid rgba(34,197,94,0.3);
    color: #4ade80; padding: 0.3rem 0.8rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
}
.status-offline {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3);
    color: #f87171; padding: 0.3rem 0.8rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
}

/* Risk badges */
.risk-high   { color:#f87171; background:rgba(239,68,68,0.15);  border:1px solid rgba(239,68,68,0.3);  padding:0.25rem 0.75rem; border-radius:8px; font-size:0.8rem; font-weight:700; }
.risk-medium { color:#fb923c; background:rgba(251,146,60,0.15); border:1px solid rgba(251,146,60,0.3); padding:0.25rem 0.75rem; border-radius:8px; font-size:0.8rem; font-weight:700; }
.risk-low    { color:#4ade80; background:rgba(74,222,128,0.15); border:1px solid rgba(74,222,128,0.3); padding:0.25rem 0.75rem; border-radius:8px; font-size:0.8rem; font-weight:700; }
.risk-none   { color:#94a3b8; background:rgba(148,163,184,0.1); border:1px solid rgba(148,163,184,0.2); padding:0.25rem 0.75rem; border-radius:8px; font-size:0.8rem; font-weight:700; }

/* Evidence cards */
.evidence-card {
    background: rgba(15,23,42,0.7); border-left: 3px solid #6366f1;
    border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem;
    font-size: 0.85rem; color: #cbd5e1;
}
.evidence-card.risk-card { border-left-color: #f87171; }
.evidence-tag {
    display: inline-block; background: rgba(99,102,241,0.2); color: #a5b4fc;
    padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.7rem;
    font-weight: 600; text-transform: uppercase; margin-right: 0.4rem;
}
.evidence-tag.risk-tag { background: rgba(239,68,68,0.2); color: #fca5a5; }

/* Confidence bar */
.conf-bar-bg {
    background: rgba(99,102,241,0.1); border-radius: 999px;
    height: 8px; overflow: hidden; margin-top: 0.3rem;
}
.conf-bar-fill {
    height: 100%; border-radius: 999px;
    background: linear-gradient(90deg, #6366f1, #c084fc);
    transition: width 0.6s ease;
}

/* Provenance pill */
.prov-search  { background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600; }
.prov-pos-exp { background:rgba(74,222,128,0.15); color:#4ade80; border:1px solid rgba(74,222,128,0.3); padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600; }
.prov-neg-exp { background:rgba(239,68,68,0.15);  color:#f87171; border:1px solid rgba(239,68,68,0.3);  padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600; }

[data-testid="stExpander"] {
    background: rgba(15,23,42,0.5) !important; border: 1px solid rgba(99,102,241,0.2) !important; border-radius: 12px !important;
}
hr { border-color: rgba(99,102,241,0.2) !important; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0f172a; }
::-webkit-scrollbar-thumb { background: #4338ca; border-radius: 3px; }

/* Keep scrollbar styling */

/* Force sidebar always visible */
[data-testid="stSidebar"] {
    transform: none !important;
    min-width: 300px !important;
    width: 300px !important;
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { margin-left: 0 !important; left: 0 !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def check_backend() -> bool:
    try:
        return requests.get(f"{API_URL}/", timeout=2).status_code == 200
    except Exception:
        return False

def risk_badge(level: str) -> str:
    icons = {"High": "🔴", "Medium": "🟡", "Low": "🟢", "None": "⚪"}
    cls = f"risk-{level.lower()}" if level in ("High","Medium","Low") else "risk-none"
    return f'<span class="{cls}">{icons.get(level,"⚪")} {level}</span>'

def confidence_bar(score: float) -> str:
    pct = int(score * 100)
    color = "#4ade80" if pct >= 80 else "#fb923c" if pct >= 50 else "#f87171"
    return f"""
    <div style="font-size:0.75rem;color:#94a3b8;">Confidence: <b style="color:{color}">{pct}%</b></div>
    <div class="conf-bar-bg"><div class="conf-bar-fill" style="width:{pct}%;background:{color}"></div></div>
    """

def render_evidence_card(node: Dict, is_risk: bool = False) -> str:
    ntype   = str(node.get("type", "node")).upper()
    page    = node.get("page", "?")
    content = html.escape(html.unescape(str(node.get("content", ""))))[:300]
    doc_id  = node.get("doc_id", "")
    tag_cls = "risk-tag" if is_risk else ""
    card_cls = "evidence-card risk-card" if is_risk else "evidence-card"
    doc_str = f" · <span style='color:#64748b;font-size:0.7rem'>{html.escape(doc_id)}</span>" if doc_id else ""
    return f"""
    <div class="{card_cls}">
        <span class="evidence-tag {tag_cls}">{ntype}</span>
        <span style="color:#64748b;font-size:0.75rem">Page {page}{doc_str}</span>
        <div style="margin-top:0.4rem">{content}</div>
    </div>"""


# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "docs_ingested" not in st.session_state:
    st.session_state.docs_ingested = []

from typing import Dict, Any


# ── Explainability renderer ───────────────────────────────────────────────────
def _render_explainability(evidence: Dict, risk: str, conf: float, data: Dict) -> None:
    supporting     = evidence.get("supporting", [])
    exceptions     = evidence.get("exceptions", [])
    contradictions = evidence.get("contradictions", [])
    risks_ev       = evidence.get("risks", [])
    warnings       = evidence.get("warnings", [])
    limitations    = evidence.get("limitations", [])

    all_risk_nodes = exceptions + contradictions + risks_ev + warnings + limitations

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Confidence",  f"{int(conf*100)}%")
    m2.metric("Supporting",  len(supporting))
    m3.metric("Exceptions",  len(all_risk_nodes))
    m4.metric("Risk Level",  risk or "None")

    st.markdown("---")

    if supporting:
        st.markdown("**✅ Supporting Evidence**")
        for node in supporting[:6]:
            st.markdown(render_evidence_card(node), unsafe_allow_html=True)
            prov = node.get("provenance", "hybrid_search")
            prov_cls = "prov-search" if "search" in prov else "prov-pos-exp"
            st.markdown(f'<span class="{prov_cls}">📌 {prov}</span>', unsafe_allow_html=True)

    if all_risk_nodes:
        st.markdown("**⚠️ Exceptions / Contradictions / Risks**")
        for node in all_risk_nodes[:5]:
            st.markdown(render_evidence_card(node, is_risk=True), unsafe_allow_html=True)
            st.markdown('<span class="prov-neg-exp">⚡ negative expansion</span>', unsafe_allow_html=True)

    st.markdown("---")
    if conf >= 0.85:
        st.success(f"✅ High confidence ({int(conf*100)}%) — strong supporting evidence, low risk.")
    elif conf >= 0.65:
        st.warning(f"⚠️ Medium confidence ({int(conf*100)}%) — answer qualified by exceptions found.")
    else:
        st.error(f"🔴 Low confidence ({int(conf*100)}%) — significant contradictions or risks detected.")


# Force sidebar open via JS click on the expand button
st.components.v1.html("""
<script>
function expandSidebar() {
    const btn = window.parent.document.querySelector('[data-testid="collapsedControl"]');
    if (btn) { btn.click(); }
    const btn2 = window.parent.document.querySelector('[data-testid="stSidebarCollapsedControl"]');
    if (btn2) { btn2.click(); }
}
setTimeout(expandSidebar, 500);
</script>
""", height=0)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🧠 DocuMind Graph</h1>
    <p>Agentic KG-RAG · Negative Graph Expansion · Risk-Aware Answers</p>
    <div class="hero-badges">
        <span class="badge">🦙 Llama 3.3 70B</span>
        <span class="badge">👁️ Llama 3.2 Vision</span>
        <span class="badge">🔍 Weaviate Hybrid</span>
        <span class="badge">🕸️ NetworkX Graph</span>
        <span class="badge">⚡ 100% Free Tier</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    backend_ok = check_backend()
    if backend_ok:
        st.markdown('<div class="status-online">● Backend Online</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-offline">● Backend Offline</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">📄 Document Upload</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"], label_visibility="collapsed")

    if uploaded_file:
        st.markdown(f"**{uploaded_file.name}** · `{round(uploaded_file.size/1024, 1)} KB`")
        if st.button("⚡ Ingest Document"):
            with st.spinner("Parsing → Embedding → Building graph... (may take 1-2 mins)"):
                try:
                    response = requests.post(
                        f"{API_URL}/upload",
                        files={"file": (uploaded_file.name, uploaded_file, uploaded_file.type)},
                        timeout=300,
                    )
                    if response.status_code in (200, 201):
                        data = response.json()
                        st.session_state.docs_ingested.append(uploaded_file.name)
                        st.success(f"✅ Ingested! {data.get('graph_nodes', '?')} nodes · {data.get('graph_edges', '?')} edges")
                    else:
                        st.error(f"Upload failed: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.warning("⚠️ Start FastAPI backend first.")
                except requests.exceptions.ReadTimeout:
                    st.warning("⏳ Still processing... check the FastAPI terminal. Refresh graph stats in a moment.")

    st.divider()

    if st.session_state.docs_ingested:
        st.markdown('<div class="sidebar-label">📚 Ingested Documents</div>', unsafe_allow_html=True)
        for i, doc in enumerate(st.session_state.docs_ingested):
            col_doc, col_del = st.columns([5, 1])
            with col_doc:
                st.markdown(f"✅ `{doc}`")
            with col_del:
                if st.button("🗑", key=f"del_{i}", help=f"Remove {doc}"):
                    try:
                        requests.delete(f"{API_URL}/document/{doc}", timeout=5)
                    except Exception:
                        pass
                    st.session_state.docs_ingested.pop(i)
                    st.rerun()
        st.divider()

    st.divider()
    st.markdown('<div class="sidebar-label">🗑️ Data Management</div>', unsafe_allow_html=True)
    if st.button("⚠️ Reset & Clear Weaviate"):
        with st.spinner("Clearing all stored data..."):
            try:
                r = requests.post(f"{API_URL}/reset", timeout=30)
                if r.status_code == 200:
                    st.session_state.docs_ingested = []
                    st.success("✅ Cleared. Re-ingest your documents.")
                else:
                    st.error(f"Reset failed: {r.text}")
            except Exception as e:
                st.error(str(e))

    if st.button("🔁 Reindex Negative Edges"):
        with st.spinner("Re-running negative edge detection..."):
            try:
                r = requests.post(f"{API_URL}/reindex", timeout=30)
                if r.status_code == 200:
                    d = r.json()
                    st.success(f"✅ {d.get('negative_edges_created', 0)} negative edges created.")
                else:
                    st.error(f"Reindex failed: {r.text}")
            except Exception as e:
                st.error(str(e))

    st.markdown('<div class="sidebar-label">⚙️ Settings</div>', unsafe_allow_html=True)
    cross_doc    = st.toggle("🔗 Cross-Document QA",   value=False)
    show_evidence = st.toggle("🔍 Show Evidence Panel", value=True)

    st.divider()

    st.markdown('<div class="sidebar-label">📊 Session Stats</div>', unsafe_allow_html=True)
    s1, s2 = st.columns(2)
    with s1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{len(st.session_state.messages)//2}</div>
            <div class="metric-label">Queries</div></div>""", unsafe_allow_html=True)
    with s2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{len(st.session_state.docs_ingested)}</div>
            <div class="metric-label">Docs</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_graph = st.tabs(["💬 Chat", "🕸️ Knowledge Graph"])


# ── Knowledge Graph Tab ───────────────────────────────────────────────────────
with tab_graph:
    st.markdown("### 🕸️ Live Knowledge Graph")
    st.caption("Real-time interactive view of nodes and edges. **Green solid** = positive · **Red dashed** = negative/risk")

    try:
        stats = requests.get(f"{API_URL}/graph/stats", timeout=3).json()
    except Exception:
        stats = {}

    gc1, gc2, gc3, gc4 = st.columns(4)
    gc1.metric("🔵 Total Nodes",    stats.get("total_nodes", "—"))
    gc2.metric("🔗 Total Edges",    stats.get("total_edges", "—"))
    gc3.metric("✅ Positive Edges", stats.get("positive_edges", "—"))
    gc4.metric("⚠️ Negative Edges", stats.get("negative_edges", "—"))

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Visualize Graph", key="viz_btn"):
        with st.spinner("Rendering interactive graph..."):
            try:
                r = requests.get(f"{API_URL}/graph", timeout=15)
                if r.status_code == 200:
                    st.iframe(r.text, height=680)
                else:
                    st.error("Failed to load graph from backend.")
            except requests.exceptions.ConnectionError:
                st.warning("⚠️ Backend not running.")


# ── Chat Tab ──────────────────────────────────────────────────────────────────
with tab_chat:

    # ── Render chat history ───────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(html.unescape(msg["content"]))

            if msg["role"] == "assistant" and "meta" in msg:
                meta      = msg["meta"]
                risk      = meta.get("risk_level", "None")
                conf      = meta.get("confidence_score", 0.0)
                evidence  = meta.get("evidence", {})

                # Inline risk + confidence
                st.markdown(
                    f'{risk_badge(risk)}&nbsp;&nbsp;',
                    unsafe_allow_html=True
                )
                st.markdown(confidence_bar(conf), unsafe_allow_html=True)

                # Explainability panel
                if show_evidence:
                    with st.expander("🔍 Evidence · Citations · Provenance"):
                        _render_explainability(evidence, risk, conf, meta)

    # ── Query input ───────────────────────────────────────────────────────────
    if query := st.chat_input("Ask anything about your documents..."):
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("🔍 Searching · 🕸️ Expanding graph · 🧠 Generating..."):
                try:
                    response = requests.post(
                        f"{API_URL}/query",
                        json={"query": query, "cross_doc": cross_doc},
                        timeout=60,
                    )
                    if response.status_code == 200:
                        data     = response.json()
                        answer   = html.unescape(data.get("answer") or data.get("response", "No answer returned."))
                        risk     = data.get("risk_level", "None")
                        conf     = float(data.get("confidence_score", 0.0))
                        evidence = data.get("evidence", {})

                        st.markdown(answer)

                        # Inline risk badge + confidence bar
                        st.markdown(risk_badge(risk), unsafe_allow_html=True)
                        st.markdown(confidence_bar(conf), unsafe_allow_html=True)

                        # Explainability panel
                        if show_evidence:
                            with st.expander("🔍 Evidence · Citations · Provenance"):
                                _render_explainability(evidence, risk, conf, data)

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "meta": data,
                        })

                    else:
                        err = f"❌ Query failed: {response.text}"
                        st.error(err)
                        st.session_state.messages.append({"role": "assistant", "content": err})

                except requests.exceptions.ConnectionError:
                    err = "⚠️ Backend not running. Run: `uvicorn main:app --reload --port 8000`"
                    st.warning(err)
                    st.session_state.messages.append({"role": "assistant", "content": err})



