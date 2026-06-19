<<<<<<< HEAD
import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="DocuMind Graph", page_icon="🧠", layout="wide")
st.title("🧠 DocuMind Graph")
st.caption("Agentic KG-RAG with Negative Graph Expansion")

# --- Sidebar: Document Upload ---
with st.sidebar:
    st.header("📄 Upload Document")
    uploaded_file = st.file_uploader("Choose a PDF or DOCX", type=["pdf", "docx"])

    if uploaded_file:
        if st.button("Ingest Document"):
            with st.spinner("Ingesting..."):
                try:
                    response = requests.post(
                        f"{API_URL}/upload",
                        files={"file": (uploaded_file.name, uploaded_file, uploaded_file.type)},
                        timeout=10,
                    )
                    if response.status_code == 200:
                        st.success(f"✅ {uploaded_file.name} ingested successfully!")
                        st.json(response.json())
                    else:
                        st.error(f"❌ Upload failed: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.warning("⚠️ Backend not running. Start FastAPI first.")

    st.divider()
    cross_doc = st.toggle("🔗 Cross-Document QA", value=False)

# --- Chat ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if query := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{API_URL}/query",
                    json={"query": query, "cross_doc": cross_doc},
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "No answer returned.")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                    # Placeholder panels — will be populated in Day 3
                    with st.expander("📊 Evidence & Risk (coming Day 3)"):
                        st.json(data)
                else:
                    err = f"❌ Query failed: {response.text}"
                    st.error(err)
                    st.session_state.messages.append({"role": "assistant", "content": err})
            except requests.exceptions.ConnectionError:
                err = "⚠️ Backend not running. Start FastAPI first."
                st.warning(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
=======
"""Empty file"""
>>>>>>> 40f0ad3 (adding dockling process and tested it)
