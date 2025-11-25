import streamlit as st
import pandas as pd
import re
import io
import zipfile
from groq import Groq

# ============================
# CONFIGURACIÓN DE LA PÁGINA
# ============================
st.set_page_config(page_title="Analizador de Bodas IA", page_icon="💍")

st.title("💍 Analizador de Bodas IA")
st.markdown("Sube tu chat de WhatsApp (exportado con o sin archivos) para extraer los detalles finales.")

# ============================
# 1. PARSEADOR (Tu lógica original)
# ============================
def parse_whatsapp_chat(file_obj):
    try:
        # Intentamos leer el archivo
        content = file_obj.read()
        try:
            string_data = content.decode("utf-8")
        except UnicodeDecodeError:
            string_data = content.decode("latin-1")
            
        lines = string_data.split('\n')
        pattern = r'^\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*([^:]+):\s(.+)$'
        data = []
        date_formats_to_try = ['%d/%m/%y %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%d/%m/%y %H:%M', '%d/%m/%Y %H:%M']

        for line in lines:
            line = line.strip()
            if not line: continue
            match = re.match(pattern, line)
            if match:
                date_str, time_str, sender, message = match.groups()
                timestamp = pd.NaT
                date_str = date_str.replace('-', '/')
                date_time_str = f"{date_str} {time_str}".strip()
                for fmt in date_formats_to_try:
                    try:
                        timestamp = pd.to_datetime(date_time_str, format=fmt)
                        break 
                    except: continue 
                if pd.isna(timestamp): continue 
                
                # Simplificar multimedia para ahorrar tokens
                if re.search(r'(omitido|adjunto|archivo)', message, re.IGNORECASE) or message.startswith('<adjunto:'):
                    message = "[ARCHIVO MULTIMEDIA]"
                
                data.append([timestamp, sender.strip(), message])
            else:
                if data: data[-1][2] += " " + line

        return pd.DataFrame(data, columns=["Timestamp", "Remitente", "Mensaje"]).dropna(subset=["Timestamp"]) 
    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
        return pd.DataFrame()

# ============================
# 2. INTERFAZ DE CARGA
# ============================
# Input para la API Key (para seguridad)
api_key = st.text_input("Ingresa tu API Key de Groq (gsk_...)", type="password")
if not api_key:
    st.warning("Necesitas una API Key gratuita de console.groq.com para continuar.")
    st.stop()

uploaded_file = st.file_uploader("Sube el archivo .txt o .zip del chat", type=["txt", "zip"])

if uploaded_file is not None:
    df_chat = pd.DataFrame()
    
    # Procesar ZIP o TXT
    with st.spinner('Leyendo archivo...'):
        if uploaded_file.name.endswith('.zip'):
            with zipfile.ZipFile(uploaded_file) as z:
                txt_files = [n for n in z.namelist() if n.endswith('.txt') and not n.startswith('__')]
                if txt_files:
                    with z.open(txt_files[0]) as f:
                        df_chat = parse_whatsapp_chat(f)
                else:
                    st.error("El ZIP no contiene archivos .txt válidos.")
        else:
            df_chat = parse_whatsapp_chat(uploaded_file)

    if not df_chat.empty:
        st.success(f"✅ Chat cargado: {len(df_chat)} mensajes.")
        
        if st.button("✨ Generar Resumen Final"):
            
            # ============================
            # 3. LÓGICA IA (GROQ)
            # ============================
            client = Groq(api_key=api_key)
            
            # Preparamos el texto (Recorte inteligente)
            conversacion = "\n".join(df_chat.apply(lambda r: f"{r['Remitente']}: {r['Mensaje']}", axis=1))
            if len(conversacion) > 25000: conversacion = conversacion[-25000:] # Groq soporta mucho contexto

            prompt = f"""
            Eres un asistente experto en bodas. Analiza el siguiente chat y extrae los datos FINALES confirmados.
            Usa EMOJIS. Si no está el dato, pon "❓ Pendiente".
            Combina direcciones y horas en la misma línea.

            CHAT:
            ---
            {conversacion}
            ---

            FORMATO DE RESPUESTA:
            📅 **Fecha de la Boda:**
            ⛪ **Ceremonia (Lugar y Hora):**
            🎉 **Recepción (Lugar y Hora):**
            🤵 **Casa del Novio (Dirección y Hora):**
            👰 **Casa de la Novia (Dirección y Hora):**
            📦 **Paquete Contratado:**
            👥 **Invitados:**
            """

            with st.spinner('La IA está pensando...'):
                try:
                    completion = client.chat.completions.create(
                        model="llama3-8b-8192", # Modelo rapidísimo y muy bueno
                        messages=[
                            {"role": "system", "content": "Eres un asistente útil."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                    )
                    
                    resultado = completion.choices[0].message.content
                    st.text_area("Resultado (Copia y pega)", value=resultado, height=300)
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Error en la IA: {e}")