import streamlit as st
import re
import zipfile
import io
from groq import Groq

# Configuración de página
st.set_page_config(page_title="Analizador de Bodas", page_icon="💍")

st.title("💍 Analizador de Bodas (Versión Móvil)")
st.markdown("Sube tu chat exportado de WhatsApp (.txt o .zip).")

# --- Lógica de Parseo Optimizada (Streaming) ---
# Esta versión NO lee todo el archivo a la memoria RAM de golpe.
# Lee línea por línea para evitar el error "Ran out of memory" en Render.
def parse_whatsapp_chat(file_obj):
    data = []
    text_stream = None
    
    try:
        # Intentamos envolver el archivo en un lector de texto UTF-8
        # file_obj viene de Streamlit o ZipFile y es bytes, necesitamos texto
        text_stream = io.TextIOWrapper(file_obj, encoding='utf-8', errors='replace')
        
        # Patrón regex para detectar mensajes
        pattern = r'^\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*([^:]+):\s(.+)$'
        
        # Iteramos línea por línea (memoria eficiente)
        for line in text_stream:
            line = line.strip()
            if not line: continue
            
            match = re.match(pattern, line)
            if match:
                # Solo guardamos el remitente y el mensaje, ignoramos la fecha para ahorrar espacio
                data.append(f"{match.group(3)}: {match.group(4)}")
                
        # Devolvemos el texto unido
        return "\n".join(data)

    except Exception as e:
        return f"Error leyendo el archivo: {e}"
    finally:
        # Es buena práctica "desconectar" el wrapper del archivo original si es posible,
        # aunque Streamlit maneja el cierre del archivo uploaded_file.
        if text_stream:
            text_stream.detach() 

# --- Interfaz ---
api_key = st.text_input("Tu API Key de Groq:", type="password")

uploaded_file = st.file_uploader("Archivo del chat", type=["txt", "zip"])

if uploaded_file and api_key:
    if st.button("Analizar Chat"):
        with st.spinner("Procesando..."):
            texto_chat = ""
            
            try:
                if uploaded_file.name.endswith('.zip'):
                    with zipfile.ZipFile(uploaded_file) as z:
                        # Buscamos el primer .txt dentro del zip
                        for name in z.namelist():
                            if name.endswith('.txt'):
                                with z.open(name) as f:
                                    texto_chat = parse_whatsapp_chat(f)
                                break
                else:
                    texto_chat = parse_whatsapp_chat(uploaded_file)

                # Verificamos si obtuvimos texto
                if not texto_chat or len(texto_chat) < 10:
                    st.error("No se pudieron extraer mensajes. Verifica que el archivo sea un chat válido.")
                else:
                    # Recorte de seguridad para la API (máximo ~30k caracteres)
                    if len(texto_chat) > 30000: 
                        texto_chat = texto_chat[-30000:]

                    # Llamada a Groq
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
                st.error(f"Ocurrió un error: {e}")
