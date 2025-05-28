import streamlit as st
import tempfile
import os
import PyPDF2
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import time
from datetime import datetime

# Configuração da API
GOOGLE_API_KEY = "AIzaSyAi-EZdS0Jners99DuB_5DkROiK16ghPnM" 

if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_ACTUAL_API_KEY_HERE": 
    st.error("⚠️ ATENÇÃO: A CHAVE API DO GEMINI NÃO FOI DEFINIDA CORRETAMENTE NO CÓDIGO!")
    st.error("Por favor, substitua 'YOUR_ACTUAL_API_KEY_HERE' pela sua chave API real na variável GOOGLE_API_KEY no código-fonte.")
    st.warning("Lembre-se: Não compartilhe este código com sua chave API real em repositórios públicos.")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
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
    st.error(f"❌ Falha ao configurar a API do Gemini: {str(e)}")
    st.stop()

# Inicialização do session state
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'texto_lei' not in st.session_state:
    st.session_state.texto_lei = ""
if 'nome_documento' not in st.session_state:
    st.session_state.nome_documento = ""
if 'analise_realizada' not in st.session_state:
    st.session_state.analise_realizada = False
if 'resumo_realizado' not in st.session_state:
    st.session_state.resumo_realizado = False
if 'contexto_conversa' not in st.session_state:
    st.session_state.contexto_conversa = ""

# --- Helper Functions ---
def extrair_texto_pdf(caminho_pdf):
    texto = ""
    try:
        with open(caminho_pdf, 'rb') as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            if not leitor.pages:
                return ""
            for pagina_num, pagina in enumerate(leitor.pages):
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina
        return texto.strip()
    except Exception as e:
        st.error(f"Erro ao processar o PDF: {str(e)}")
        return ""

def call_gemini_api(prompt_text, task_name="tarefa"):
    try:
        response = model.generate_content(prompt_text)
        if not response.candidates:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_message = response.prompt_feedback.block_reason.name
                return f"Conteúdo bloqueado: {block_reason_message}"
            else:
                return "Nenhum conteúdo gerado."
        return response.text
    except Exception as e:
        st.error(f"❌ Erro durante a {task_name} com a API Gemini: {str(e)}")
        return f"Erro na API: {str(e)}"

def criar_contexto_inicial():
    """Cria o contexto inicial para o agente conversacional"""
    if st.session_state.texto_lei:
        contexto = f"""
        DOCUMENTO JURÍDICO CARREGADO: {st.session_state.nome_documento}
        
        TEXTO DA LEI/NORMA:
        {st.session_state.texto_lei[:15000]}
        
        INSTRUÇÕES PARA O AGENTE:
        Você é o LexFácil, um assistente jurídico especializado em simplificar textos normativos para o público leigo.
        Sua missão é ajudar as pessoas a compreenderem leis e regulamentos de forma clara e acessível.
        
        DIRETRIZES:
        1. Sempre responda em linguagem simples e acessível
        2. Quando mencionar artigos ou seções, explique seu significado prático
        3. Use exemplos do dia a dia quando possível
        4. Se um termo jurídico for necessário, explique-o brevemente
        5. Seja objetivo mas amigável
        6. Foque sempre no documento carregado pelo usuário
        7. Se não souber algo específico do documento, seja honesto
        8. Sugira análises automáticas quando relevante
        
        Responda sempre baseado no documento carregado acima.
        """
        return contexto
    return ""

def processar_pergunta_chat(pergunta):
    """Processa uma pergunta no chat considerando o contexto da lei"""
    contexto_base = criar_contexto_inicial()
    
    # Histórico das últimas 3 mensagens para contexto
    historico_recente = ""
    if len(st.session_state.chat_messages) > 0:
        ultimas_msgs = st.session_state.chat_messages[-6:]  # Últimas 3 trocas (user + assistant)
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
    
    return call_gemini_api(prompt, "resposta do chat")

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
    return call_gemini_api(prompt, "Análise de Legibilidade")

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
    return call_gemini_api(prompt, "Geração de Resumo")

# --- Interface Streamlit ---
st.set_page_config(page_title="LexFácil", layout="wide", initial_sidebar_state="expanded")

# Sidebar para upload e ferramentas
with st.sidebar:
    st.title("📘 LexFácil")
    st.markdown("**Seu assistente jurídico inteligente**")
    
    # Upload de arquivo
    st.markdown("### 📄 Carregar Documento")
    uploaded_file = st.file_uploader("Envie o PDF da lei ou norma", type=["pdf"])
    
    if uploaded_file:
        if uploaded_file.name != st.session_state.nome_documento:
            # Novo arquivo carregado
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            with st.spinner("Processando documento..."):
                texto_extraido = extrair_texto_pdf(tmp_file_path)
                os.unlink(tmp_file_path)
                
                if texto_extraido:
                    st.session_state.texto_lei = texto_extraido
                    st.session_state.nome_documento = uploaded_file.name
                    st.session_state.chat_messages = []  # Limpa chat anterior
                    st.session_state.analise_realizada = False
                    st.session_state.resumo_realizado = False
                    st.success("✅ Documento carregado!")
                    
                    # Mensagem de boas-vindas automática
                    boas_vindas = f"""Olá! Acabei de receber o documento **{uploaded_file.name}**. 

Agora posso ajudar você a entender este texto jurídico de forma simples e clara. Você pode:

🔍 **Me fazer perguntas** sobre qualquer parte da lei
📊 **Solicitar análise de legibilidade** - para entender o quão complexo é o texto
📄 **Pedir um resumo simplificado** - com os pontos principais explicados

**Como posso ajudar você hoje?**"""
                    
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": boas_vindas,
                        "timestamp": datetime.now()
                    })
                    st.rerun()
                else:
                    st.error("❌ Não foi possível extrair texto do PDF")
        
        # Ferramentas rápidas
        if st.session_state.texto_lei:
            st.markdown("### 🛠️ Ferramentas Rápidas")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Análise", use_container_width=True):
                    if not st.session_state.analise_realizada:
                        with st.spinner("Analisando..."):
                            analise = analisar_legibilidade_gemini(st.session_state.texto_lei)
                            st.session_state.chat_messages.append({
                                "role": "user",
                                "content": "Faça uma análise de legibilidade do documento",
                                "timestamp": datetime.now()
                            })
                            st.session_state.chat_messages.append({
                                "role": "assistant", 
                                "content": f"## 📊 Análise de Legibilidade\n\n{analise}",
                                "timestamp": datetime.now()
                            })
                            st.session_state.analise_realizada = True
                            st.rerun()
                    else:
                        st.info("Análise já realizada - veja no chat!")
            
            with col2:
                if st.button("📄 Resumo", use_container_width=True):
                    if not st.session_state.resumo_realizado:
                        with st.spinner("Resumindo..."):
                            resumo = gerar_resumo_gemini(st.session_state.texto_lei)
                            st.session_state.chat_messages.append({
                                "role": "user",
                                "content": "Gere um resumo simplificado do documento",
                                "timestamp": datetime.now()
                            })
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": f"## 📄 Resumo Simplificado\n\n{resumo}",
                                "timestamp": datetime.now()
                            })
                            st.session_state.resumo_realizado = True
                            st.rerun()
                    else:
                        st.info("Resumo já realizado - veja no chat!")
            
            # Info do documento
            st.markdown("### 📋 Documento Atual")
            st.info(f"**{st.session_state.nome_documento}**\n\n{len(st.session_state.texto_lei):,} caracteres")
    else:
        st.info("Carregue um documento PDF para começar")

# Área principal - Chat
st.title("💬 Converse sobre sua Lei")

if not st.session_state.texto_lei:
    st.markdown("""
    ### Bem-vindo ao LexFácil! 👋
    
    Para começar:
    1. **Carregue um PDF** da lei ou norma na barra lateral
    2. **Converse comigo** sobre o documento de forma natural
    3. **Tire suas dúvidas** em linguagem simples
    
    Estou aqui para tornar o juridiquês acessível! 🎯
    """)
else:
    # Container para o chat
    chat_container = st.container()
    
    # Exibir mensagens do chat
    with chat_container:
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Input para nova mensagem
    if prompt := st.chat_input("Digite sua pergunta sobre a lei..."):
        # Adicionar mensagem do usuário
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now()
        })
        
        # Exibir mensagem do usuário
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Gerar e exibir resposta
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                resposta = processar_pergunta_chat(prompt)
                st.markdown(resposta)
                
                # Adicionar resposta ao histórico
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": resposta,
                    "timestamp": datetime.now()
                })

# Footer
st.markdown("---")
st.markdown("🤖 **LexFácil** - Transformando juridiquês em linguagem humana com IA")

# Sugestões de perguntas (quando há documento carregado)
if st.session_state.texto_lei and len(st.session_state.chat_messages) <= 1:
    st.markdown("### 💡 Sugestões de perguntas:")
    
    sugestoes = [
        "Quais são os principais pontos desta lei?",
        "Como esta lei me afeta no dia a dia?",
        "Quais são as penalidades previstas?",
        "A partir de quando esta lei entra em vigor?",
        "Quem deve cumprir estas regras?",
        "Existe alguma exceção importante?"
    ]
    
    cols = st.columns(3)
    for i, sugestao in enumerate(sugestoes):
        with cols[i % 3]:
            if st.button(sugestao, key=f"sug_{i}", use_container_width=True):
                # Simular clique no chat
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": sugestao,
                    "timestamp": datetime.now()
                })
                
                with st.spinner("Pensando..."):
                    resposta = processar_pergunta_chat(sugestao)
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": resposta,
                        "timestamp": datetime.now()
                    })
                st.rerun()
