import streamlit as st
import tempfile
import os
import PyPDF2
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import time
from datetime import datetime

# Configuração da API
GOOGLE_API_KEY = "AIzaSyAi-EZdS0Jners99DuB_5DkROiK16ghPnM"  # Replace with your actual API key

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
if 'persona_usuario' not in st.session_state:
    st.session_state.persona_usuario = "👨‍👩‍👧‍👦 Cidadão"
if 'casos_praticos' not in st.session_state:
    st.session_state.casos_praticos = []
if 'prazos_extraidos' not in st.session_state:
    st.session_state.prazos_extraidos = []

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
        personas = {
            "👨‍👩‍👧‍👦 Cidadão": "Use linguagem ultra-simples, foque no impacto pessoal e familiar, dê exemplos do cotidiano",
            "👨‍💼 Empresário": "Foque em impactos comerciais, custos, prazos de adequação, riscos para negócios",
            "👩‍⚖️ Advogado": "Pode usar termos técnicos, foque em interpretação jurídica, precedentes, aplicação prática",
            "🏛️ Servidor Público": "Foque na aplicação da norma, procedimentos, competências dos órgãos"
        }
        
        contexto_persona = personas.get(st.session_state.persona_usuario, personas["👨‍👩‍👧‍👦 Cidadão"])
        
        contexto = f"""
        DOCUMENTO JURÍDICO CARREGADO: {st.session_state.nome_documento}
        
        TEXTO DA LEI/NORMA:
        {st.session_state.texto_lei[:15000]}
        
        PERFIL DO USUÁRIO: {st.session_state.persona_usuario}
        INSTRUÇÕES ESPECÍFICAS: {contexto_persona}
        
        INSTRUÇÕES PARA O AGENTE:
        Você é o LexFácil, um assistente jurídico especializado em simplificar textos normativos.
        Sua missão é ajudar as pessoas a compreenderem leis e regulamentos de forma clara e acessível.
        
        DIRETRIZES:
        1. Adapte sua linguagem ao perfil do usuário selecionado
        2. Quando mencionar artigos ou seções, explique seu significado prático
        3. Use exemplos relevantes ao perfil do usuário
        4. Se um termo jurídico for necessário, explique conforme o nível do usuário
        5. Seja objetivo mas amigável
        6. Foque sempre no documento carregado pelo usuário
        7. Se não souber algo específico do documento, seja honesto
        8. Sugira funcionalidades úteis (casos práticos, análise de prazos, etc.)
        
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
    """Gera um resumo simplificado da lei"""
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

def gerar_casos_praticos(texto):
    """Gera casos práticos baseados na lei"""
    prompt = f"""
    Com base neste texto jurídico, crie 3 casos práticos/exemplos reais de como esta lei se aplica no dia a dia.
    
    Para cada caso, forneça:
    1. **Situação**: Descreva um cenário específico e realista
    2. **Aplicação da Lei**: Como a lei se aplica neste caso
    3. **Consequências**: O que acontece na prática
    4. **Dica Prática**: Uma orientação útil
    
    Casos devem ser:
    - Realistas e específicos
    - Fáceis de entender
    - Relevantes para diferentes perfis de pessoas
    - Escritos em linguagem simples
    
    Use formato MARKDOWN com títulos e seções claras.
    
    Texto da Lei:
    ---
    {texto[:15000]}
    ---
    """
    return call_gemini_api(prompt, "Geração de Casos Práticos")

def extrair_prazos_importantes(texto):
    """Extrai prazos e datas importantes da lei"""
    prompt = f"""
    Analise este texto jurídico e identifique TODOS os prazos, datas e períodos importantes mencionados.
    
    Para cada prazo encontrado, forneça:
    1. **Prazo**: O período específico (dias, meses, anos)
    2. **Para que serve**: O que deve ser feito neste prazo
    3. **Quem deve cumprir**: Responsável pela ação
    4. **Consequência**: O que acontece se não cumprir
    5. **Artigo/Seção**: Onde está previsto no texto
    
    Organize em ordem de importância/urgência.
    Use formato MARKDOWN com emojis para facilitar visualização.
    
    Se não encontrar prazos específicos, informe que a lei não estabelece prazos determinados.
    
    Texto da Lei:
    ---
    {texto[:15000]}
    ---
    """
    return call_gemini_api(prompt, "Extração de Prazos")

def busca_semantica(texto, consulta):
    """Realiza busca semântica no texto da lei"""
    prompt = f"""
    O usuário quer encontrar informações sobre: "{consulta}"
    
    Procure no texto jurídico abaixo todas as informações relacionadas a esta consulta.
    Considere sinônimos, conceitos relacionados e contexto.
    
    Retorne:
    1. **Trechos Relevantes**: Cite os artigos/parágrafos específicos
    2. **Explicação Simplificada**: O que significa na prática
    3. **Palavras-chave Encontradas**: Termos relacionados identificados
    
    Se não encontrar nenhuma informação relacionada, informe claramente.
    
    Consulta do usuário: {consulta}
    
    Texto da Lei:
    ---
    {texto[:15000]}
    ---
    """
    return call_gemini_api(prompt, "Busca Semântica")

# --- Interface Streamlit ---
st.set_page_config(page_title="LexFácil", layout="wide", initial_sidebar_state="expanded")

# Sidebar para upload e ferramentas
with st.sidebar:
    st.title("📘 LexFácil")
    st.markdown("**Seu assistente jurídico inteligente**")
    
    # Seletor de Persona
    st.markdown("### 👤 Seu Perfil")
    personas = {
        "👨‍👩‍👧‍👦 Cidadão": "Linguagem simples e exemplos do dia a dia",
        "👨‍💼 Empresário": "Foco em impactos comerciais e negócios", 
        "👩‍⚖️ Advogado": "Análise técnica e jurídica detalhada",
        "🏛️ Servidor Público": "Aplicação prática da norma"
    }
    
    persona_escolhida = st.selectbox(
        "Como você quer que eu te ajude?",
        options=list(personas.keys()),
        index=list(personas.keys()).index(st.session_state.persona_usuario),
        help="Escolha seu perfil para respostas personalizadas"
    )
    
    if persona_escolhida != st.session_state.persona_usuario:
        st.session_state.persona_usuario = persona_escolhida
        st.success(f"✅ Perfil alterado para {persona_escolhida}")
        # Rerun para aplicar mudanças
        time.sleep(1)
        st.rerun()
    
    st.info(personas[st.session_state.persona_usuario])
    
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
            st.markdown("### 🛠️ Ferramentas Inteligentes")
            
            # Primeira linha - Análises básicas
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
                        st.info("Análise já realizada!")
            
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
                        st.info("Resumo já realizado!")
            
            # Segunda linha - Funcionalidades avançadas
            col3, col4 = st.columns(2)
            with col3:
                if st.button("🎯 Casos Práticos", use_container_width=True):
                    with st.spinner("Criando exemplos..."):
                        casos = gerar_casos_praticos(st.session_state.texto_lei)
                        st.session_state.chat_messages.append({
                            "role": "user",
                            "content": "Gere casos práticos de aplicação da lei",
                            "timestamp": datetime.now()
                        })
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": f"## 🎯 Casos Práticos\n\n{casos}",
                            "timestamp": datetime.now()
                        })
                        st.session_state.casos_praticos.append(casos)
                        st.rerun()
            
            with col4:
                if st.button("⏰ Prazos", use_container_width=True):
                    with st.spinner("Extraindo prazos..."):
                        prazos = extrair_prazos_importantes(st.session_state.texto_lei)
                        st.session_state.chat_messages.append({
                            "role": "user",
                            "content": "Quais são os prazos importantes desta lei?",
                            "timestamp": datetime.now()
                        })
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": f"## ⏰ Prazos Importantes\n\n{prazos}",
                            "timestamp": datetime.now()
                        })
                        st.session_state.prazos_extraidos.append(prazos)
                        st.rerun()
            
            # Busca semântica
            st.markdown("### 🔍 Busca Inteligente")
            busca_query = st.text_input("Buscar por conceito ou tema:", placeholder="Ex: multas, prazos, obrigações...")
            if st.button("Buscar", use_container_width=True) and busca_query:
                with st.spinner("Buscando..."):
                    resultado_busca = busca_semantica(st.session_state.texto_lei, busca_query)
                    st.session_state.chat_messages.append({
                        "role": "user",
                        "content": f"Buscar por: {busca_query}",
                        "timestamp": datetime.now()
                    })
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": f"## 🔍 Resultados da Busca: '{busca_query}'\n\n{resultado_busca}",
                        "timestamp": datetime.now()
                    })
                    st.rerun()
            
            # Info do documento
            st.markdown("### 📋 Documento Atual")
            st.info(f"**{st.session_state.nome_documento}**\n\n{len(st.session_state.texto_lei):,} caracteres\n\n👤 **Modo:** {st.session_state.persona_usuario}")
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

# Sugestões de perguntas personalizadas por persona
if st.session_state.texto_lei and len(st.session_state.chat_messages) <= 1:
    st.markdown("### 💡 Perguntas sugeridas para seu perfil:")
    
    sugestoes_por_persona = {
        "👨‍👩‍👧‍👦 Cidadão": [
            "Como esta lei me afeta no dia a dia?",
            "Quais são meus direitos e deveres?", 
            "O que acontece se eu não cumprir?",
            "Esta lei já está valendo?",
            "Preciso fazer algo para me adequar?",
            "Tem alguma multa prevista?"
        ],
        "👨‍💼 Empresário": [
            "Quais os impactos para minha empresa?",
            "Quanto vai custar me adequar?",
            "Quais são os prazos de adequação?",
            "Que documentos preciso providenciar?",
            "Posso ser multado? Qual valor?",
            "Como isso afeta meus funcionários?"
        ],
        "👩‍⚖️ Advogado": [
            "Quais são as principais mudanças?",
            "Como interpretar o artigo X?",
            "Há conflitos com outras normas?",
            "Quais as sanções previstas?",
            "Como é a aplicação prática?",
            "Existem regulamentações complementares?"
        ],
        "🏛️ Servidor Público": [
            "Como aplicar esta norma?",
            "Quais são os procedimentos?",
            "Que competência tem meu órgão?",
            "Como fiscalizar o cumprimento?",
            "Que documentos são necessários?",
            "Como instruir os processos?"
        ]
    }
    
    sugestoes = sugestoes_por_persona.get(st.session_state.persona_usuario, sugestoes_por_persona["👨‍👩‍👧‍👦 Cidadão"])
    
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

# Footer
st.markdown("---")
st.markdown("🤖 **LexFácil** - Transformando juridiquês em linguagem humana com IA")
