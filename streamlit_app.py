import streamlit as st
import tempfile
import os
import PyPDF2
import google.generativeai as genai

# Configuração da API do Gemini
GOOGLE_API_KEY = "AIzaSyA07VjFHe932cYVO_qTHBf6-42apNDjtok"

if not GOOGLE_API_KEY:
    st.error("⚠️ Configure sua chave API do Gemini")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"❌ Falha na API: {str(e)}")
    st.stop()

# Função para extrair texto do PDF
def extrair_texto_pdf(caminho_pdf):
    texto = ""
    try:
        with open(caminho_pdf, 'rb') as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            for pagina in leitor.pages:
                texto += pagina.extract_text() or ""
        return texto if texto.strip() else ""
    except Exception as e:
        st.error(f"Erro no PDF: {str(e)}")
        return ""

# Funções que usam apenas o Gemini
def analisar_legibilidade_gemini(texto):
    prompt = f"""
    Analise a legibilidade deste texto jurídico (em português) considerando:
    1. Complexidade linguística (escala de 1-10)
    2. Densidade conceitual
    3. Uso de termos técnicos
    4. Estrutura das frases
    5. Recomendações para simplificação

    Retorne em formato MARKDOWN com títulos e bullet points.

    Texto: {texto[:15000]}  # Limita o tamanho
    """
    response = model.generate_content(prompt)
    return response.text

def gerar_resumo_gemini(texto):
    prompt = f"""
    Gere um resumo conciso em português deste texto jurídico, mantendo:
    - Os pontos principais
    - Artigos e parágrafos relevantes
    - Efeitos práticos
    Use linguagem acessível e formato MARKDOWN.

    Texto: {texto[:15000]}
    """
    response = model.generate_content(prompt)
    return response.text

# Interface
st.set_page_config(page_title="LexFácil", layout="centered")
st.title("📘 LexFácil - Leis para Todos")
st.subheader("Textos normativos com linguagem acessível")

uploaded_file = st.file_uploader("Envie o PDF da lei", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.getvalue())
        texto = extrair_texto_pdf(tmp.name)
        os.unlink(tmp.name)

    if not texto:
        st.warning("PDF sem texto extraível")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["📝 Texto", "📊 Legibilidade IA", "✂️ Resumo IA"])
    
    with tab1:
        st.subheader("Texto Extraído")
        st.text_area("", value=texto[:10000] + ("..." if len(texto) > 10000 else ""), height=300)

    with tab2:
        st.subheader("Análise de Legibilidade")
        if st.button("Analisar com IA"):
            analise = analisar_legibilidade_gemini(texto)
            st.markdown(analise)

    with tab3:
        st.subheader("Resumo Automático")
        if st.button("Gerar Resumo com IA"):
            resumo = gerar_resumo_gemini(texto)
            st.markdown(resumo)

st.markdown("---")
st.caption("Desenvolvido com Gemini AI")
