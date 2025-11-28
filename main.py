import streamlit as st
import pandas as pd
import re
import zipfile
from groq import Groq

# Configuración de página
st.set_page_config(page_title="Analizador de Bodas", page_icon="💍")

st.title("💍 Analizador de Bodas (Versión Móvil)")
st.markdown("Sube tu chat exportado de WhatsApp (.txt o .zip).")

# --- Lógica de Parseo Ligera ---
def parse_whatsapp_chat(file_obj):
    try:
        content = file_obj.read()
        try:
            string_data = content.decode("utf-8")
        except:
            string_data = content.decode("latin-1")
            
        lines = string_data.split('\n')
        data = []
        pattern = r'^\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*([^:]+):\s(.+)$'
        
        for line in lines:
            line = line.strip()
            if not line: continue
            match = re.match(pattern, line)
            if match:
                data.append(f"{match.group(3)}: {match.group(4)}")
                
        return "\n".join(data) # Devolvemos texto directo para ahorrar memoria
    except Exception as e:
        return ""

# --- Interfaz ---
api_key = st.text_input("Tu API Key de Groq:", type="password")

uploaded_file = st.file_uploader("Archivo del chat", type=["txt", "zip"])

if uploaded_file and api_key:
    if st.button("Analizar Chat"):
        with st.spinner("Procesando..."):
            texto_chat = ""
            if uploaded_file.name.endswith('.zip'):
                with zipfile.ZipFile(uploaded_file) as z:
                    for name in z.namelist():
                        if name.endswith('.txt'):
                            with z.open(name) as f:
                                texto_chat = parse_whatsapp_chat(f)
                            break
            else:
                texto_chat = parse_whatsapp_chat(uploaded_file)

            # Recorte para no saturar
            if len(texto_chat) > 30000: texto_chat = texto_chat[-30000:]

            try:
                client = Groq(api_key=api_key)
                prompt = f"""
                Actúa como asistente de bodas. Extrae los datos FINALES confirmados de este chat.
                Si no hay dato, pon "No especificado". Usa EMOJIS.
                
                CHAT:
                {texto_chat}
                
                FORMATO REQUERIDO:
                📅 Fecha:
                ⛪ Ceremonia (Lugar/Hora):
                🎉 Banquete (Lugar/Hora):
                🤵 Novio (Dirección):
                👰 Novia (Dirección):
                📦 Paquete:
                👥 Invitados:
                """
                
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama3-8b-8192",
                )
                
                st.success("¡Análisis completado!")
                st.code(chat_completion.choices[0].message.content)
                
            except Exception as e:
                st.error(f"Error: {e}")
