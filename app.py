import os
import ollama
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemma4:e2b")

client = ollama.Client(host=OLLAMA_HOST)

st.title("Chatbot")

with st.sidebar:
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Message Model..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            stream = client.chat(
                model=MODEL_NAME,
                messages=st.session_state.messages,
                stream=True,
            )

            def token_generator():
                for chunk in stream:
                    yield chunk["message"]["content"]

            response = st.write_stream(token_generator())
            st.session_state.messages.append({"role": "assistant", "content": response})

        except ConnectionError:
            st.error(f"Ollama is not running on {OLLAMA_HOST}. Start it with: ollama serve")
        except ollama.ResponseError as e:
            if "not found" in str(e).lower():
                st.error(f"Model not found. Pull it with: ollama pull {MODEL_NAME}")
            else:
                st.error(f"Ollama error: {e}")
