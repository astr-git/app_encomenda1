import streamlit as st
import json
import PIL.Image
from google import genai
from google.genai import types
import pandas as pd
import os
import hashlib
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# --- CONFIGURACOES ---
st.set_page_config(page_title="PackFlow", page_icon="📦", layout="wide")
load_dotenv() 

CHAVE_API = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=CHAVE_API)

ARQUIVO_DB = "banco_encomendas.csv"
ARQUIVO_USUARIOS = "banco_usuarios.csv"
PLATAFORMAS_OPCOES = ["Mercado Livre", "Shopee", "Amazon", "Shein", "Outro", "Não identificado"]
TAMANHO_OPCOES = ["Pequeno", "Médio", "Grande"]

# --- SEGURANCA E HASH ---
def gerar_hash(senha):
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def inicializar_banco_usuarios():
    """Cria o banco de usuarios com reset de segurança caso esteja corrompido"""
    precisa_criar = False
    if not os.path.exists(ARQUIVO_USUARIOS):
        precisa_criar = True
    else:
        try:
            df = pd.read_csv(ARQUIVO_USUARIOS)
            if df.empty or "Senha" not in df.columns:
                os.remove(ARQUIVO_USUARIOS)
                precisa_criar = True
        except:
            os.remove(ARQUIVO_USUARIOS)
            precisa_criar = True
            
    if precisa_criar:
        df_padrao = pd.DataFrame([{
            "Nome": "Administrador",
            "Login": "supervisor",
            "Senha": gerar_hash("admin789"),
            "Role": "supervisor",
            "Trocar_Senha": "Nao"
        }])
        df_padrao.to_csv(ARQUIVO_USUARIOS, index=False, encoding='utf-8')

# --- INICIALIZACAO DE ESTADO ---
inicializar_banco_usuarios()

if 'autenticado' not in st.session_state:
    st.session_state.update({
        'autenticado': False, 'usuario_logado': None, 'nome_usuario': None,
        'role_usuario': None, 'deve_trocar_senha': False, 'uploader_key': 0
    })

# --- FUNCOES DE LOGIN ---
def validar_login(login, senha_digitada):
    try:
        df = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
        senha_hash = gerar_hash(senha_digitada)
        usuario = df[(df['Login'] == login) & (df['Senha'] == senha_hash)]
        return usuario.iloc[0] if not usuario.empty else None
    except:
        return None

# --- INTERFACE DE LOGIN ---
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center;'>PackFlow - Acesso</h1>", unsafe_allow_html=True)
    col_l1, col_login, col_l3 = st.columns([3, 2, 3])
    with col_login:
        with st.container(border=True):
            user = st.text_input("Login")
            pw = st.text_input("Senha", type="password")
            if st.button("Entrar", type="primary", use_container_width=True):
                dados = validar_login(user, pw)
                if dados is not None:
                    st.session_state.update({
                        'autenticado': True, 'usuario_logado': dados['Login'],
                        'nome_usuario': dados['Nome'], 'role_usuario': dados['Role'],
                        'deve_trocar_senha': (dados['Trocar_Senha'] == 'Sim')
                    })
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
    st.stop()

# --- APLICATIVO PRINCIPAL ---
st.title("PackFlow - Gestão de Pacotes")

# (Aqui você mantém o restante da lógica de abas, cadastro e consulta que já criamos)
# ... [O restante do seu código segue aqui sem alterações] ...

st.success(f"Logado como: {st.session_state['nome_usuario']}")
if st.button("Sair"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()
