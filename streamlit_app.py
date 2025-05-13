import streamlit as st
import tempfile
import os
import PyPDF2
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- Configuration ---
# WARNING: HARDCODING API KEYS IS A SECURITY RISK!
# Replace "YOUR_ACTUAL_API_KEY_HERE" with your real Google API Key.
# Do NOT commit this file to a public GitHub repository with your real key.
GOOGLE_API_KEY = "AIzaSyAi-EZdS0Jners99DuB_5DkROiK16ghPnM" # <--- PASTE YOUR ACTUAL API KEY HERE

if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_ACTUAL_API_KEY_HERE": # Check if placeholder is still there
    st.error("⚠️ ATENÇÃO: A CHAVE API DO GEMINI NÃO FOI DEFINIDA CORRETAMENTE NO CÓDIGO!")
    st.error("Por favor, substitua 'YOUR_ACTUAL_API_KEY_HERE' pela sua chave API real na variável GOOGLE_API_KEY no código-fonte.")
    st.warning("Lembre-se: Não compartilhe este código com sua chave API real em repositórios públicos.")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    # Configuration for safety settings - adjust as needed
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash-latest', # or 'gemini-pro'
        safety_settings=safety_settings
    )
except Exception as e:
    st.error(f"❌ Falha ao configurar a API do Gemini: {str(e)}")
    st.stop()

# --- Helper Functions ---
def extrair_texto_pdf(caminho_pdf):
    texto = ""
    try:
        with open(caminho_pdf, 'rb') as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            if not leitor.pages:
                st.warning("PDF parece estar vazio ou não contém páginas.")
                return ""
            for pagina_num, pagina in enumerate(leitor.pages):
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina
        return texto.strip()
    except PyPDF2.errors.PdfReadError:
        st.error("Erro ao ler o PDF. O arquivo pode estar corrompido ou protegido por senha.")
        return ""
    except Exception as e:
        st.error(f"Erro inesperado ao processar o PDF: {str(e)}")
        return ""

def call_gemini_api(prompt_text, task_name="tarefa"):
    """Generic function to call Gemini API and handle response."""
    try:
        response = model.generate_content(prompt_text)

        if not response.candidates:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_message = response.prompt_feedback.block_reason.name
                st.error(f"⚠️ A {task_name} foi bloqueada pela API. Razão: {block_reason_message}")
                return f"Conteúdo bloqueado: {block_reason_message}"
            else:
                st.error(f"⚠️ A {task_name} não retornou conteúdo. Resposta da API: {response}")
                return "Nenhum conteúdo gerado."
        return response.text
    except Exception as e:
        st.error(f"❌ Erro durante a {task_name} com a API Gemini: {str(e)}")
        return f"Erro na API: {str(e)}"

def analisar_legibilidade_gemini(texto):
    prompt = f"""
    Analise a legibilidade deste texto jurídico (em português) considerando os seguintes critérios.
    Para cada critério, forneça uma avaliação e, se aplicável, sugestões de melhoria.

    1.  **Complexidade Linguística Geral:**
        *   Avaliação (escala de 1-Fácil a 10-Muito Difícil):
        *   Justificativa:
    2.  **Densidade Conceitual:**
        *   Avaliação (Baixa, Média, Alta):
        *   Exemplos de conceitos densos (se houver):
    3.  **Uso de Termos Técnicos (Jargão Jurídico):**
        *   Avaliação (Moderado, Frequente, Excessivo):
        *   Exemplos de termos técnicos chave:
        *   Sugestões para simplificar ou explicar termos:
    4.  **Estrutura das Frases:**
        *   Avaliação (Comprimento médio, Clareza, Uso de voz passiva/ativa):
        *   Exemplos de frases complexas (se houver):
        *   Sugestões para melhorar a clareza das frases:
    5.  **Coerência e Coesão:**
        *   Avaliação (Como as ideias se conectam, clareza do fluxo lógico):
    6.  **Público-Alvo Ideal:**
        *   Para quem este texto é mais adequado em sua forma atual?
    7.  **Recomendações Gerais para Simplificação:**
        *   Liste 3-5 ações concretas para tornar o texto mais acessível a um público leigo.

    Formato de Resposta: Utilize estritamente MARKDOWN, com títulos (usando ## ou ###) e bullet points (usando * ou -).

    Texto para Análise:
    ---
    {texto[:18000]}
    ---
    """
    return call_gemini_api(prompt, task_name="Análise de Legibilidade")

def gerar_resumo_gemini(texto):
    prompt = f"""
    Você é um assistente especializado em simplificar textos jurídicos para o público leigo.
    Sua tarefa é gerar um resumo conciso e em linguagem acessível do texto jurídico fornecido.
    O resumo deve:
    1.  Identificar e explicar os pontos principais do texto de forma clara.
    2.  Mencionar artigos, parágrafos ou seções relevantes, explicando seu significado prático.
    3.  Descrever os efeitos práticos ou as consequências do que está estabelecido no texto.
    4.  Evitar jargões jurídicos sempre que possível. Se um termo técnico for essencial, explique-o brevemente.
    5.  Ser estruturado de forma lógica e fácil de seguir.
    6.  Utilizar formato MARKDOWN para melhor legibilidade (títulos, bullet points, negrito).

    Texto Jurídico para Resumir:
    ---
    {texto[:18000]}
    ---

    Resumo Acessível:
    """
    return call_gemini_api(prompt, task_name="Geração de Resumo")

# --- Streamlit Interface ---
st.set_page_config(page_title="LexFácil", layout="wide", initial_sidebar_state="collapsed")
# st.image("https://lexfacil.com.br/wp-content/uploads/2023/09/logo-lexfacil-azul-claro.png", width=200) # Your logo
st.title("📘 LexFácil - Leis para Todos")
st.subheader("Textos normativos com linguagem acessível, por IA")

uploaded_file = st.file_uploader("Envie o PDF da lei, portaria, ou outro texto normativo", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name

    texto_extraido = ""
    try:
        with st.spinner("Extraindo texto do PDF..."):
            texto_extraido = extrair_texto_pdf(tmp_file_path)
    finally:
        os.unlink(tmp_file_path)

    if not texto_extraido:
        st.warning("⚠️ Não foi possível extrair texto do PDF. O arquivo pode conter apenas imagens, estar protegido ou ser incompatível.")
        st.stop()

    st.success("Texto extraído com sucesso!")

    tab1, tab2, tab3 = st.tabs(["📝 Texto Completo Extraído", "📊 Análise de Legibilidade (IA)", "✂️ Resumo Simplificado (IA)"])

    with tab1:
        st.subheader("Texto Extraído do PDF")
        st.caption(f"Total de caracteres extraídos: {len(texto_extraido)}")
        st.text_area("Conteúdo do PDF:", value=texto_extraido, height=400, key="texto_completo")
        st.caption("Nota: A extração de texto de PDFs pode não ser perfeita, especialmente em layouts complexos ou documentos digitalizados como imagem.")

    with tab2:
        st.subheader("Análise de Legibilidade Detalhada")
        st.markdown("""
        Clique no botão abaixo para que a Inteligência Artificial analise o texto jurídico quanto à sua legibilidade,
        considerando complexidade linguística, uso de jargões, estrutura das frases e outros fatores.
        Serão fornecidas recomendações para simplificação.
        """)
        if st.button("🔍 Analisar Legibilidade com IA", key="analisar_legibilidade_btn"):
            if texto_extraido:
                with st.spinner("Analisando... Isso pode levar alguns instantes."):
                    analise = analisar_legibilidade_gemini(texto_extraido)
                st.markdown("### Resultado da Análise de Legibilidade:")
                st.markdown(analise)
            else:
                st.warning("Nenhum texto disponível para análise.")

    with tab3:
        st.subheader("Resumo Simplificado do Texto")
        st.markdown("""
        Peça à Inteligência Artificial para gerar um resumo conciso do texto jurídico,
        focando nos pontos principais, artigos relevantes e seus efeitos práticos, tudo em linguagem acessível.
        """)
        if st.button("📄 Gerar Resumo com IA", key="gerar_resumo_btn"):
            if texto_extraido:
                with st.spinner("Gerando resumo... Por favor, aguarde."):
                    resumo = gerar_resumo_gemini(texto_extraido)
                st.markdown("### Resumo Gerado pela IA:")
                st.markdown(resumo)
            else:
                st.warning("Nenhum texto disponível para resumir.")
else:
    st.info("Aguardando o envio de um arquivo PDF...")

st.markdown("---")
st.caption("Desenvolvido com Google Gemini AI | Protótipo LexFácil")
