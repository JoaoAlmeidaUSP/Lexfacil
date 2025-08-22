import streamlit as st
import tempfile
import os
import PyPDF2
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import time
from datetime import datetime

# --- CONFIGURAÇÃO DA API (LÓGICA ANTIGA PARA TESTE) ---
# ATENÇÃO: Substitua pela sua chave real para testar.
# Lembre-se de mudar para o método st.secrets assim que validar o funcionamento.
GOOGLE_API_KEY = "AIzaSyC8POlPwAb5S95teCfWHSeAiEiejOTz7R0" 

if not GOOGLE_API_KEY or GOOGLE_API_KEY == "AIzaSyC8POlPwAb5S95teCfWHSeAiEiejOTz7R0":
    st.error("⚠️ ATENÇÃO: A CHAVE API DO GEMINI NÃO FOI DEFINIDA CORRETAMENTE!")
    st.error("Por favor, substitua 'SUA_CHAVE_API_AQUI' pela sua chave API real na variável GOOGLE_API_KEY no código-fonte para poder testar.")
    st.warning("Lembre-se: Após o teste, é altamente recomendável usar o método de 'secrets' do Streamlit para proteger sua chave.")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"❌ Falha ao configurar a API do Gemini com a chave fornecida: {str(e)}")
    st.stop()


# --- CONFIGURAÇÃO DO MODELO GEMINI ---
try:
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash-latest',
        safety_settings=safety_settings
    )
except Exception as e:
    st.error(f"❌ Falha ao configurar o modelo Gemini: {str(e)}")
    st.stop()

# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'texto_lei' not in st.session_state:
    st.session_state.texto_lei = ""
if 'nome_documento' not in st.session_state:
    st.session_state.nome_documento = ""
if 'persona_usuario' not in st.session_state:
    st.session_state.persona_usuario = "👨‍👩‍👧‍👦 Cidadão"

# --- FUNÇÕES AUXILIARES E DE PROCESSAMENTO ---

def extrair_texto_pdf(uploaded_file):
    """Extrai texto de um arquivo PDF carregado."""
    texto = ""
    try:
        # Usando o arquivo em memória diretamente, sem salvar em disco
        leitor = PyPDF2.PdfReader(uploaded_file)
        for pagina in leitor.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto += texto_pagina
        return texto.strip()
    except Exception as e:
        st.error(f"Erro ao processar o PDF: {str(e)}")
        return ""

# --- OTIMIZAÇÃO: CACHING E RATE LIMITING NA CHAMADA DA API ---
@st.cache_data(show_spinner=False) # Cache para evitar chamadas repetidas
def call_gemini_api_with_retry(_prompt_text, task_name="tarefa", max_retries=3):
    """
    Chama a API Gemini com tratamento de erro e retentativas (exponential backoff).
    O decorator @st.cache_data garante que, para o mesmo _prompt_text,
    a função não será executada novamente, retornando o resultado salvo em cache.
    """
    for attempt in range(max_retries):
        try:
            response = model.generate_content(_prompt_text)
            if response.candidates:
                return response.text
            elif response.prompt_feedback and response.prompt_feedback.block_reason:
                return f"Conteúdo bloqueado: {response.prompt_feedback.block_reason.name}"
            else:
                return "Nenhum conteúdo gerado."
        except Exception as e:
            if "429" in str(e): # Erro de Quota
                wait_time = 2 ** attempt # Exponential backoff: 1, 2, 4 segundos
                st.warning(f"⚠️ Cota da API excedida. Tentando novamente em {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                st.error(f"❌ Erro durante a {task_name} com a API Gemini: {str(e)}")
                return f"Erro na API: {str(e)}"
    return "Erro: A API continua indisponível após várias tentativas."


def criar_contexto_inicial():
    """Cria o contexto inicial para o agente conversacional."""
    if not st.session_state.texto_lei:
        return ""

    personas = {
        "👨‍👩‍👧‍👦 Cidadão": "Use linguagem ultra-simples, foque no impacto pessoal e familiar, dê exemplos do cotidiano.",
        "👨‍💼 Empresário": "Foque em impactos comerciais, custos, prazos de adequação, riscos para negócios.",
        "👩‍⚖️ Advogado": "Pode usar termos técnicos, foque em interpretação jurídica, precedentes, aplicação prática.",
        "🏛️ Servidor Público": "Foque na aplicação da norma, procedimentos, competências dos órgãos."
    }
    contexto_persona = personas.get(st.session_state.persona_usuario, personas["👨‍👩‍👧‍👦 Cidadão"])
    texto_contexto = st.session_state.texto_lei[:50000] # Amostra para o contexto

    return f"""
    DOCUMENTO JURÍDICO CARREGADO: {st.session_state.nome_documento}
    PERFIL DO USUÁRIO: {st.session_state.persona_usuario}
    INSTRUÇÕES ESPECÍFICAS: {contexto_persona}

    TEXTO DA LEI/NORMA (INÍCIO):
    {texto_contexto}
    ---
    INSTRUÇÕES PARA O AGENTE:
    Você é o LexFácil, um assistente jurídico. Sua missão é simplificar textos normativos.
    Adapte sua linguagem ao perfil do usuário. Seja objetivo, amigável e baseie-se sempre no documento carregado.
    """

# --- FUNÇÕES PRINCIPAIS COM CACHE ---
@st.cache_data(show_spinner="Analisando legibilidade...")
def analisar_legibilidade_gemini(_texto):
    prompt = f"""
    Analise a legibilidade deste texto jurídico. Forneça uma avaliação sobre:
    1. Complexidade Linguística (1-Fácil a 10-Difícil)
    2. Uso de Jargão Jurídico (Baixo, Médio, Alto)
    3. Estrutura das Frases (Curtas/Longas, Claras/Complexas)
    4. Público-Alvo Ideal
    5. Recomendações para Simplificação (3 a 5 ações)
    Formate a resposta em MARKDOWN.

    Texto para Análise:
    ---
    {_texto}
    """
    return call_gemini_api_with_retry(prompt, "Análise de Legibilidade")

@st.cache_data(show_spinner="Gerando resumo...")
def gerar_resumo_gemini(_texto):
    prompt = f"""
    Gere um resumo conciso e em linguagem acessível do texto jurídico fornecido.
    - Identifique os pontos principais.
    - Explique o significado prático dos artigos mais relevantes.
    - Evite jargões. Se um termo técnico for essencial, explique-o.
    - Use MARKDOWN para melhor legibilidade.

    Texto Jurídico para Resumir:
    ---
    {_texto}
    """
    return call_gemini_api_with_retry(prompt, "Resumo Simplificado")

@st.cache_data(show_spinner="Criando casos práticos...")
def gerar_casos_praticos(_texto):
    texto_amostra = _texto[:30000]
    prompt = f"""
    Com base no texto jurídico, crie 3 casos práticos de como esta lei se aplica no dia a dia.
    Para cada caso, forneça: Situação, Aplicação da Lei, Consequências e Dica Prática.
    Use MARKDOWN.

    Texto da Lei:
    ---
    {texto_amostra}
    """
    return call_gemini_api_with_retry(prompt, "Geração de Casos Práticos")

@st.cache_data(show_spinner="Extraindo prazos...")
def extrair_prazos_importantes(_texto):
    prompt = f"""
    Analise este texto jurídico e identifique TODOS os prazos, datas e períodos importantes.
    Para cada um, forneça: Prazo, Finalidade, Responsável, Consequência do não cumprimento e Artigo/Seção.
    Se não encontrar prazos, informe isso claramente. Use MARKDOWN.

    Texto da Lei:
    ---
    {_texto}
    """
    return call_gemini_api_with_retry(prompt, "Extração de Prazos")

@st.cache_data(show_spinner="Buscando no documento...")
def busca_semantica(_texto, _consulta):
    texto_amostra = _texto[:50000]
    prompt = f"""
    O usuário quer encontrar informações sobre: "{_consulta}"
    Procure no texto jurídico abaixo todas as informações relacionadas.
    Retorne: Trechos Relevantes (com citação do artigo/seção), Explicação Simplificada e Palavras-chave Encontradas.
    Se não encontrar, informe claramente.

    Texto da Lei:
    ---
    {texto_amostra}
    """
    return call_gemini_api_with_retry(prompt, "Busca Semântica")

def processar_pergunta_chat(pergunta):
    """Processa uma pergunta no chat (não usa cache, pois a conversa é dinâmica)."""
    contexto_base = criar_contexto_inicial()
    historico_recente = ""
    ultimas_msgs = st.session_state.chat_messages[-6:]
    for msg in ultimas_msgs:
        papel = "USUÁRIO" if msg["role"] == "user" else "ASSISTENTE"
        historico_recente += f"{papel}: {msg['content']}\n"

    prompt = f"""
    {contexto_base}

    HISTÓRICO DA CONVERSA:
    {historico_recente}

    PERGUNTA ATUAL DO USUÁRIO:
    {pergunta}

    Responda de forma clara, prática e acessível, sempre baseado no documento jurídico carregado.
    """
    return call_gemini_api_with_retry(prompt, "resposta do chat")


# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="LexFácil", layout="wide", initial_sidebar_state="expanded")

# --- SIDEBAR ---
with st.sidebar:
    st.title("📘 LexFácil")
    st.markdown("**Seu assistente jurídico inteligente**")

    st.markdown("### 👤 Seu Perfil")
    persona_escolhida = st.selectbox(
        "Como você quer que eu te ajude?",
        options=["👨‍👩‍👧‍👦 Cidadão", "👨‍💼 Empresário", "👩‍⚖️ Advogado", "🏛️ Servidor Público"],
        index=0,
        help="Escolha seu perfil para respostas personalizadas"
    )
    if persona_escolhida != st.session_state.persona_usuario:
        st.session_state.persona_usuario = persona_escolhida

    st.markdown("### 📄 Carregar Documento")
    uploaded_file = st.file_uploader("Envie o PDF da lei ou norma", type=["pdf"])

    if uploaded_file:
        if uploaded_file.name != st.session_state.get('nome_documento'):
            with st.spinner("Processando documento..."):
                texto_extraido = extrair_texto_pdf(uploaded_file)
                if texto_extraido:
                    st.session_state.clear()
                    st.session_state.texto_lei = texto_extraido
                    st.session_state.nome_documento = uploaded_file.name
                    st.session_state.persona_usuario = persona_escolhida
                    st.session_state.chat_messages = []

                    boas_vindas = f"Olá! Recebi o documento **{uploaded_file.name}**. Como posso te ajudar a entendê-lo?"
                    st.session_state.chat_messages.append({"role": "assistant", "content": boas_vindas})
                    st.success("✅ Documento carregado!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Não foi possível extrair texto do PDF.")

    if st.session_state.texto_lei:
        st.markdown("### 🛠️ Ferramentas Inteligentes")
        
        def adicionar_ao_chat(titulo, conteudo_gerado, pergunta_usuario):
            st.session_state.chat_messages.append({"role": "user", "content": pergunta_usuario})
            st.session_state.chat_messages.append({"role": "assistant", "content": f"## {titulo}\n\n{conteudo_gerado}"})

        if st.button("📊 Análise de Legibilidade", use_container_width=True):
            resultado = analisar_legibilidade_gemini(st.session_state.texto_lei)
            adicionar_ao_chat("📊 Análise de Legibilidade", resultado, "Faça uma análise de legibilidade do documento.")

        if st.button("📄 Resumo Simplificado", use_container_width=True):
            resultado = gerar_resumo_gemini(st.session_state.texto_lei)
            adicionar_ao_chat("📄 Resumo Simplificado", resultado, "Gere um resumo simplificado do documento.")

        if st.button("🎯 Casos Práticos", use_container_width=True):
            resultado = gerar_casos_praticos(st.session_state.texto_lei)
            adicionar_ao_chat("🎯 Casos Práticos", resultado, "Gere casos práticos de aplicação da lei.")

        if st.button("⏰ Prazos Importantes", use_container_width=True):
            resultado = extrair_prazos_importantes(st.session_state.texto_lei)
            adicionar_ao_chat("⏰ Prazos Importantes", resultado, "Quais são os prazos importantes desta lei?")
        
        st.markdown("### 🔍 Busca Inteligente")
        busca_query = st.text_input("Buscar por conceito ou tema:", placeholder="Ex: multas, prazos...")
        if st.button("Buscar", use_container_width=True) and busca_query:
            resultado = busca_semantica(st.session_state.texto_lei, busca_query)
            adicionar_ao_chat(f"🔍 Resultados da Busca: '{busca_query}'", resultado, f"Buscar por: {busca_query}")

        st.markdown("### 📋 Documento Atual")
        st.info(f"**{st.session_state.nome_documento}**\n\n{len(st.session_state.texto_lei):,} caracteres")


# --- ÁREA PRINCIPAL - CHAT ---
st.title("💬 Converse sobre sua Lei")

if not st.session_state.texto_lei:
    st.info("Para começar, carregue um documento PDF na barra lateral.")
else:
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Digite sua pergunta sobre a lei..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                resposta = processar_pergunta_chat(prompt)
                st.markdown(resposta)
                st.session_state.chat_messages.append({"role": "assistant", "content": resposta})

# Footer
st.markdown("---")
st.markdown("🤖 **LexFácil** - Transformando juridiquês em linguagem acessível com IA")
