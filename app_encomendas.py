import streamlit as st
import json
import PIL.Image
from google import genai
from google.genai import types
import pandas as pd
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# --- CONFIGURACOES GERAIS ---
st.set_page_config(page_title="PackFlow", page_icon="📦", layout="wide")

# --- INJECAO DE CSS PARA COR DE FUNDO E RODAPE ---
st.markdown(
    """
    <style>
    /* Cor de fundo suave */
    .stApp {
        background-color: #f4f6f9;
    }
    
    /* Rodafe fixo com o novo nome */
    .rodape {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: transparent;
        color: #9ca3af; 
        text-align: center;
        font-size: 13px;
        padding: 10px;
        z-index: 100;
        pointer-events: none; 
    }
    </style>
    
    <div class="rodape">PackFlow - Sistema em desenvolvimento - 2026</div>
    """,
    unsafe_allow_html=True
)

load_dotenv() 

CHAVE_API = os.getenv("GEMINI_API_KEY")
if not CHAVE_API:
    st.error("ERRO CRITICO: Chave da API nao encontrada no arquivo .env!")
    st.stop()

client = genai.Client(api_key=CHAVE_API)

PLATAFORMAS_OPCOES = [
    "Mercado Livre", "Shopee", "Amazon", "Shein", "Petz", 
    "Magalu", "AliExpress", "Americanas", "Casas Bahia", "Outro", "Não identificado"
]
TAMANHO_OPCOES = ["Pequeno", "Médio", "Grande"]

ARQUIVO_DB = "banco_encomendas.csv"
ARQUIVO_USUARIOS = "banco_usuarios.csv"

# --- INICIALIZACAO DE SESSOES ---
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
    st.session_state['usuario_logado'] = None
    st.session_state['nome_usuario'] = None
    st.session_state['role_usuario'] = None
    st.session_state['deve_trocar_senha'] = False

# --- FUNCOES DE USUARIOS E SEGURANCA ---
def inicializar_banco_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        df_padrao = pd.DataFrame([{
            "Nome": "Administrador",
            "Login": "supervisor",
            "Senha": "admin789",
            "Role": "supervisor",
            "Trocar_Senha": "Nao"
        }])
        df_padrao.to_csv(ARQUIVO_USUARIOS, index=False, encoding='utf-8')

def validar_login(login, senha):
    try:
        df_usuarios = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
        usuario = df_usuarios[(df_usuarios['Login'] == login) & (df_usuarios['Senha'] == senha)]
        if not usuario.empty:
            return usuario.iloc[0]
        return None
    except Exception:
        return None

def atualizar_senha(login, nova_senha):
    df_usuarios = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
    df_usuarios.loc[df_usuarios['Login'] == login, 'Senha'] = nova_senha
    df_usuarios.loc[df_usuarios['Login'] == login, 'Trocar_Senha'] = 'Nao'
    df_usuarios.to_csv(ARQUIVO_USUARIOS, index=False, encoding='utf-8')

def adicionar_usuario(nome, login, senha):
    df_usuarios = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
    if login.lower() in df_usuarios['Login'].str.lower().values:
        return False
    
    novo_user = pd.DataFrame([{
        "Nome": nome,
        "Login": login,
        "Senha": senha,
        "Role": "operador",
        "Trocar_Senha": "Sim"
    }])
    df_atualizado = pd.concat([df_usuarios, novo_user], ignore_index=True)
    df_atualizado.to_csv(ARQUIVO_USUARIOS, index=False, encoding='utf-8')
    return True

# --- FUNCOES DE ENCOMENDAS ---
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
            st.warning("O limite de consultas da IA foi atingido. Aguarde cerca de 1 minuto e tente novamente.")
        else:
            st.error(f"Erro de comunicacao com a IA: {mensagem_erro}")
        return None

def salvar_no_banco(nome, bloco, apto, nf, plataforma, tamanho, usuario):
    fuso_br = timezone(timedelta(hours=-3))
    data_hora_atual = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
    
    novo_registro = pd.DataFrame([{
        "Data Cadastro": data_hora_atual,
        "Quem Cadastrou": usuario,
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
        try:
            df_existente = pd.read_csv(ARQUIVO_DB, dtype=str)
            df_atualizado = pd.concat([df_existente, novo_registro], ignore_index=True)
            df_atualizado.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')
        except Exception:
            novo_registro.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')
    else:
        novo_registro.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')


# --- DIALOGO DE CONFIRMACAO (POP-UP) ---
@st.dialog("Confirmação de Retirada")
def modal_confirmar(linhas_selecionadas, pessoa_retirou_input):
    st.markdown("Você está prestes a registrar a entrega dos seguintes pacotes:")
    
    for _, row in linhas_selecionadas.iterrows():
        st.markdown(f"📦 **Apto {row['Apartamento']} (Bl {row['Bloco']})** - {row['Nome do Comprador']}")
    
    st.divider()
    
    if st.button("Sim, Confirmar Entrega", type="primary", use_container_width=True):
        df_encomendas = pd.read_csv(ARQUIVO_DB, dtype=str)
        fuso_br = timezone(timedelta(hours=-3))
        data_retirada = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")

        for idx_real, row in linhas_selecionadas.iterrows():
            nome_final = pessoa_retirou_input.strip()
            if not nome_final:
                nome_final = df_encomendas.at[idx_real, "Nome do Comprador"]
                
            df_encomendas.at[idx_real, "Status"] = "Retirado"
            df_encomendas.at[idx_real, "Data Retirada"] = data_retirada
            df_encomendas.at[idx_real, "Quem Retirou"] = nome_final

        df_encomendas.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')
        st.session_state['msg_retirada'] = f"{len(linhas_selecionadas)} pacote(s) entregue(s) com sucesso!"
        st.rerun()


# ==========================================
# EXECUCAO DE SEGURANCA E LOGIN
# ==========================================
inicializar_banco_usuarios()

if not st.session_state['autenticado']:
    st.write("")
    st.write("")
    st.write("")
    
    col1, col_login, col3 = st.columns([1, 1.2, 1])
    
    with col_login:
        # ATUALIZADO: Busca agora pela logo em .png
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)
        else:
            st.markdown("<h2 style='text-align: center; color: #1f2937;'>PackFlow</h2>", unsafe_allow_html=True)
            
        st.markdown("<p style='text-align: center; color: #6b7280; margin-bottom: 20px;'>Controle de Acesso</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            usuario_input = st.text_input("Login")
            senha_input = st.text_input("Senha", type="password")
            
            st.write("")
            
            if st.button("Autenticar", type="primary", use_container_width=True):
                dados_usuario = validar_login(usuario_input, senha_input)
                
                if dados_usuario is not None:
                    st.session_state['autenticado'] = True
                    st.session_state['usuario_logado'] = dados_usuario['Login']
                    st.session_state['nome_usuario'] = dados_usuario['Nome']
                    st.session_state['role_usuario'] = dados_usuario['Role']
                    st.session_state['deve_trocar_senha'] = (dados_usuario['Trocar_Senha'] == 'Sim')
                    st.rerun()
                else:
                    st.error("Credenciais invalidas. Tente novamente.")
    st.stop()

# ==========================================
# TROCA DE SENHA OBRIGATORIA
# ==========================================
if st.session_state['deve_trocar_senha']:
    st.write("")
    st.write("")
    
    col_vazia1, col_senha, col_vazia3 = st.columns([1, 1.2, 1])
    
    with col_senha:
        # ATUALIZADO: Busca agora pela logo em .png
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)
            
        st.warning(f"Olá, {st.session_state['nome_usuario']}! Esta é a sua primeira vez no sistema.")
        st.markdown("<h3 style='text-align: center;'>Alteração de Senha Obrigatória</h3>", unsafe_allow_html=True)
        
        with st.container(border=True
