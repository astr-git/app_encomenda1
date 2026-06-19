import streamlit as st
import json
import PIL.Image
from google import genai
from google.genai import types
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv

# --- CONFIGURACOES GERAIS ---
st.set_page_config(page_title="Gestor de Encomendas", layout="wide")

# Carrega as variaveis ocultas do arquivo .env
load_dotenv() 

# Puxa a chave do ambiente (se nao achar, avisa no console)
CHAVE_API = os.getenv("GEMINI_API_KEY")
if not CHAVE_API:
    st.error("ERRO CRÍTICO: Chave da API não encontrada no arquivo .env!")
    st.stop()

client = genai.Client(api_key=CHAVE_API)

PLATAFORMAS_OPCOES = [
    "Mercado Livre", "Shopee", "Amazon", "Shein", "Petz", 
    "Magalu", "AliExpress", "Americanas", "Casas Bahia", "Outro", "Não identificado"
]

TAMANHO_OPCOES = ["Pequeno", "Médio", "Grande"]

ARQUIVO_DB = "banco_encomendas.csv"

if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0

def extrair_dados(imagem):
    prompt = """
    Analise a etiqueta e extraia em JSON:
    - nome_comprador, bloco, apartamento, nota_fiscal, plataforma.
    Regras:
    1. nota_fiscal: ignore QR Codes de rastreio, busque o numero da NF ou Declaracao de Conteudo.
    2. plataforma: Se nao houver logotipo ou nome claro de marketplace, retorne "Não identificado".
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, imagem],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        mensagem_erro = str(e)
        if "429" in mensagem_erro or "RESOURCE_EXHAUSTED" in mensagem_erro:
            st.warning("O limite de consultas da IA foi atingido. Por favor, aguarde cerca de 1 minuto e tente novamente.")
        else:
            st.error(f"Ocorreu um erro de comunicacao com a IA: {mensagem_erro}")
        return None

def salvar_no_banco(nome, bloco, apto, nf, plataforma, tamanho):
    data_hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    novo_registro = pd.DataFrame([{
        "Data Cadastro": data_hora_atual,
        "Nome do Comprador": nome,
        "Bloco": bloco,
        "Apartamento": apto,
        "Nota Fiscal": nf,
        "Plataforma": plataforma,
        "Tamanho do Pacote": tamanho,
        "Status": "Aguardando Retirada",
        "Data Retirada": "",
        "Quem Retirou": ""
    }])
    
    if os.path.exists(ARQUIVO_DB):
        novo_registro.to_csv(ARQUIVO_DB, mode='a', header=False, index=False, encoding='utf-8')
    else:
        novo_registro.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')

# --- INTERFACE VISUAL ---
st.title("Sistema de Gestão de Encomendas")

aba_cadastro, aba_consulta = st.tabs(["Cadastro de Encomendas", "Consultar Encomendas"])

# ==========================================
# ABA 1: CADASTRO
# ==========================================
with aba_cadastro:
    
    if 'mensagem_sucesso' in st.session_state:
        st.success(st.session_state['mensagem_sucesso'])
        del st.session_state['mensagem_sucesso']

    st.markdown("Utilize a câmera ou faça o upload da foto. A análise iniciará automaticamente.")
    
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("1. Captura da Etiqueta")
        
        # Botões horizontais para escolher o método (Mobile ou PC)
        tipo_captura = st.radio("Como deseja capturar a imagem?", ["📸 Câmera do Celular", "📂 Upload de Arquivo"], horizontal=True)
        
        arquivo_final = None
        
        # Exibe o input correspondente à escolha do usuário
        if tipo_captura == "📸 Câmera do Celular":
            arquivo_final = st.camera_input("Tire a foto da etiqueta", key=f"camera_{st.session_state['uploader_key']}")
        else:
            arquivo_final = st.file_uploader(
                "Escolha ou arraste a imagem aqui", 
                type=["jpg", "jpeg", "png"],
                key=f"uploader_{st.session_state['uploader_key']}"
            )
        
        if arquivo_final:
            imagem_pil = PIL.Image.open(arquivo_final)
            
            # Evita duplicar a imagem na tela se estiver usando a câmera
            if tipo_captura == "📂 Upload de Arquivo":
                st.image(imagem_pil, caption="Etiqueta Carregada", use_container_width=True)
            
            # Identificador único para evitar re-análises acidentais
            nome_identificador = arquivo_final.name if tipo_captura == "📂 Upload de Arquivo" else f"foto_cam_{st.session_state['uploader_key']}"
            
            if 'ultimo_arquivo' not in st.session_state or st.session_state['ultimo_arquivo'] != nome_identificador:
                with st.spinner("Processando dados com Inteligência Artificial..."):
                    resultado_ia = extrair_dados(imagem_pil)
                    if resultado_ia:
                        st.session_state['dados'] = resultado_ia
                        st.session_state['ultimo_arquivo'] = nome_identificador
