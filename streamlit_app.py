import streamlit as st
import tempfile
import os
import re
import nltk
from nltk.tokenize import sent_tokenize
import PyPDF2
import warnings
import google.generativeai as genai
import json

# Silenciar avisos para não assustar o usuário
warnings.filterwarnings("ignore")

# Certifique-se de baixar os recursos do NLTK necessários
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Configuração da API do Gemini (substitua pela sua chave)
GOOGLE_API_KEY = "AIzaSyA07VjFHe932cYVO_qTHBf6-42apNDjtok"  # ← Insira sua chave API aqui

# Verifica se a chave foi configurada (ALTERAÇÃO FEITA AQUI)
if not GOOGLE_API_KEY:
    st.error("⚠️ A chave da API do Google Gemini não foi configurada. Por favor, configure a variável GOOGLE_API_KEY no código.")
    st.stop()

# Inicializa o modelo Gemini
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"❌ Falha ao conectar com a API do Gemini: {str(e)}")
    st.stop()

# Restante do código permanece igual...
# Função para extrair texto de PDF com tratamento de erros melhorado
def extrair_texto_pdf(caminho_pdf):
    texto_completo = ""
    try:
        with open(caminho_pdf, 'rb') as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            num_paginas = len(leitor.pages)
            
            if num_paginas == 0:
                st.warning("O PDF não contém páginas ou está protegido.")
                return ""
            
            with st.spinner(f"Extraindo texto de {num_paginas} páginas..."):
                for pagina in leitor.pages:
                    texto_pagina = pagina.extract_text()
                    if texto_pagina:  # Verifica se há texto extraído
                        texto_completo += texto_pagina + "\n"
                    
            return texto_completo if texto_completo.strip() else ""
        
    except PyPDF2.PdfReadError:
        st.error("Não foi possível ler o PDF. O arquivo pode estar corrompido ou protegido.")
        return ""
    except Exception as e:
        st.error(f"Erro inesperado ao extrair texto: {str(e)}")
        return ""

# Interface Streamlit
st.set_page_config(page_title="LexFácil", layout="centered", initial_sidebar_state="expanded")

st.title("📘 LexFácil")
st.subheader("Torne textos legislativos mais fáceis de entender")

# Upload do arquivo
uploaded_file = st.file_uploader("Envie o PDF da lei ou edital", type=["pdf"], accept_multiple_files=False)

if uploaded_file is not None:
    try:
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        # Extrai o texto
        texto = extrair_texto_pdf(tmp_path)
        
        # Remove o arquivo temporário
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if not texto:
            st.warning("Não foi possível extrair texto do PDF. O arquivo pode ser uma imagem ou estar protegido.")
            st.stop()
            
        # Mostra as abas somente se a extração foi bem sucedida
        tab1, tab2, tab3 = st.tabs(["📝 Texto", "📊 Legibilidade", "✂️ Resumo"])
        
        with tab1:
            st.subheader("Texto Extraído")
            st.text_area("Texto", value=texto[:10000] + ("..." if len(texto) > 10000 else ""), height=300)
            st.download_button("Baixar Texto Completo", data=texto, file_name="texto_extraido.txt")
            
        with tab2:
            st.subheader("Análise de Legibilidade")
            # Adicione aqui sua função de análise de legibilidade
            
        with tab3:
            st.subheader("Resumo Automático")
            # Adicione aqui sua função de resumo
            
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {str(e)}")
        st.stop()
else:
    st.info("👆 Por favor, faça upload de um arquivo PDF para começar.")

# Rodapé
st.markdown("---")
st.markdown("Desenvolvido para tornar as leis mais acessíveis")
