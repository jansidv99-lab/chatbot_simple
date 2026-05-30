import os
import ollama
import streamlit as st
from dotenv import load_dotenv
from opentelemetry import trace as otel_trace

load_dotenv()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemma4:e2b")
PHOENIX_ENDPOINT = os.environ.get("PHOENIX_ENDPOINT", "")
PHOENIX_PROJECT = os.environ.get("PHOENIX_PROJECT", "chatbot")

if PHOENIX_ENDPOINT:
    from phoenix.otel import register  # noqa: PLC0415
    from opentelemetry.instrumentation.ollama import OllamaInstrumentor  # noqa: PLC0415
    register(endpoint=PHOENIX_ENDPOINT, project_name=PHOENIX_PROJECT)
    OllamaInstrumentor().instrument()

tracer = otel_trace.get_tracer(__name__)
client = ollama.Client(host=OLLAMA_HOST)


def stream_response(client, model, messages):
    stream = client.chat(model=model, messages=messages, stream=True)
    for chunk in stream:
        yield chunk["message"]["content"]


def generate_suggestions(client, model, messages):
    prompt = messages + [{
        "role": "user",
        "content": (
            "Give me 3 short follow-up questions I could ask about this topic. "
            "Reply with just the questions, one per line, no numbering or bullets."
        )
    }]
    try:
        result = client.chat(model=model, messages=prompt, stream=False)
        lines = result["message"]["content"].strip().splitlines()
        return [line.strip() for line in lines if line.strip()][:3]
    except Exception:
        return []


st.markdown("""
<style>
/* ── Background ─────────────────────────────────────────── */
.stApp {
    background-color: #0e0e1a;
}

/* ── Sidebar ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #151528;
    border-right: 1px solid #2a2a4a;
}

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {
    background-color: #6c63ff;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    transition: background-color 0.2s ease;
}
.stButton > button:hover {
    background-color: #5a52d5;
    border: none;
    color: #ffffff;
}
.stButton > button:active {
    background-color: #4a43b5;
    border: none;
    color: #ffffff;
}

/* ── Chat input box ──────────────────────────────────────── */
[data-testid="stChatInput"] {
    background-color: #1a1a30 !important;
    border: 1px solid #3a3a60 !important;
    border-radius: 12px !important;
}

/* ── Title ───────────────────────────────────────────────── */
h1 {
    color: #7c73ff !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

with st.sidebar:
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.suggestions = []
        st.rerun()

    if st.session_state.suggestions:
        st.divider()
        st.markdown("**You might want to ask:**")
        for s in st.session_state.suggestions:
            st.markdown(f"- *{s}*")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Message Model..."):
    st.session_state.suggestions = []
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with tracer.start_as_current_span("chat_turn") as agent_span:
            agent_span.set_attribute("openinference.span.kind", "AGENT")
            agent_span.set_attribute("input.value", prompt)
            try:
                with tracer.start_as_current_span("stream_response") as chain_span:
                    chain_span.set_attribute("openinference.span.kind", "CHAIN")
                    response = st.write_stream(stream_response(client, MODEL_NAME, st.session_state.messages))
                    chain_span.set_attribute("output.value", response)

                st.session_state.messages.append({"role": "assistant", "content": response})

                with tracer.start_as_current_span("generate_suggestions") as chain_span:
                    chain_span.set_attribute("openinference.span.kind", "CHAIN")
                    st.session_state.suggestions = generate_suggestions(client, MODEL_NAME, st.session_state.messages)

                agent_span.set_attribute("output.value", response)

            except ConnectionError:
                st.error(f"Ollama is not running on {OLLAMA_HOST}. Start it with: ollama serve")
            except ollama.ResponseError as e:
                if "not found" in str(e).lower():
                    st.error(f"Model not found. Pull it with: ollama pull {MODEL_NAME}")
                else:
                    st.error(f"Ollama error: {e}")
