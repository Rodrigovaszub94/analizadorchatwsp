import streamlit as st
import re
import zipfile
import io
import gc  # Garbage Collector para liberar memoria
from groq import Groq

# Configuración de página
st.set_page_config(page_title="Analizador de Bodas", page_icon="💍")

st.title("💍 Analizador de Bodas (Versión Móvil)")
st.info("💡 IMPORTANTE: Al exportar de WhatsApp, elige **'Sin Archivos'**. Si subes videos o fotos, el servidor fallará.")

# --- Lógica de Parseo Optimizada ---
def parse_whatsapp_chat(file_obj):
    data = []
    text_stream = None
    
    try:
        text_stream = io.TextIOWrapper(file_obj, encoding='utf-8', errors='replace')
        pattern = r'^\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*([^:]+):\s(.+)$'
        
        # Leemos línea por línea
        for line in text_stream:
            line = line.strip()
            if not line: continue
            
            match = re.match(pattern, line)
            if match:
                # Guardamos remitente y mensaje
                data.append(f"{match.group(3)}: {match.group(4)}")
        
        # Liberamos el stream lo antes posible
        if text_stream:
            text_stream.detach()
            text_stream = None
            
        return "\n".join(data)

    except Exception as e:
        return ""

# --- Interfaz ---
api_key = st.text_input("Tu API Key de Groq:", type="password")

uploaded_file = st.file_uploader("Archivo del chat (Máx 20MB)", type=["txt", "zip"])

if uploaded_file and api_key:
    # 1. VALIDACIÓN DE TAMAÑO (CRÍTICO PARA RENDER GRATUITO)
    # Si el archivo pesa más de 20MB, lo rechazamos antes de que explote la RAM.
    FILE_SIZE_LIMIT = 20 * 1024 * 1024  # 20 MB
    
    if uploaded_file.size > FILE_SIZE_LIMIT:
        st.error(f"❌ El archivo es demasiado grande ({uploaded_file.size / 1024 / 1024:.2f} MB).")
        st.warning("El servidor gratuito solo soporta chats de texto. Por favor, exporta el chat de WhatsApp seleccionando **'Sin Archivos'**.")
    else:
        if st.button("Analizar Chat"):
            with st.spinner("Procesando..."):
                texto_chat = ""
                error_msg = None
                
                try:
                    # Procesamiento ZIP
                    if uploaded_file.name.endswith('.zip'):
                        try:
                            with zipfile.ZipFile(uploaded_file) as z:
                                txt_files = [n for n in z.namelist() if n.endswith('.txt')]
                                if not txt_files:
                                    error_msg = "No se encontró ningún archivo .txt dentro del ZIP."
                                else:
                                    # Tomamos el primer txt (suele ser '_chat.txt')
                                    with z.open(txt_files[0]) as f:
                                        texto_chat = parse_whatsapp_chat(f)
                        except zipfile.BadZipFile:
                            error_msg = "El archivo ZIP parece estar dañado."
                    
                    # Procesamiento TXT
                    else:
                        texto_chat = parse_whatsapp_chat(uploaded_file)

                    # Validación de contenido
                    if not texto_chat or len(texto_chat) < 10:
                        if not error_msg:
                            error_msg = "No se pudo leer texto del chat. Asegúrate de que no esté vacío."
                        st.error(error_msg)
                    
                    else:
                        # Recorte inteligente para la IA (Últimos 25,000 caracteres)
                        # Esto asegura que nos centremos en las decisiones finales
                        if len(texto_chat) > 25000: 
                            texto_chat = texto_chat[-25000:]

                        # Llamada a Groq
                        client = Groq(api_key=api_key)
                        prompt = f"""
                        Actúa como asistente de bodas. Extrae los datos FINALES confirmados de este chat.
                        Si no hay dato, pon "No especificado". Usa EMOJIS.
                        
                        CHAT (Últimos mensajes):
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
                        st.markdown("### Resultados:")
                        st.code(chat_completion.choices[0].message.content)
                        
                        # Limpieza forzada de memoria
                        del texto_chat
                        gc.collect()
                
                except Exception as e:
                    st.error(f"Ocurrió un error inesperado: {e}")
