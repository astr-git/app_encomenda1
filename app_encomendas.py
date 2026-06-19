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

# --- CONFIGURACOES GERAIS ---
st.set_page_config(page_title="PackFlow", page_icon="📦", layout="wide")

st.markdown("""<style>.stApp {background-color: #ffffff;} .rodape {position: fixed; left: 0; bottom: 0; width: 100%; background-color: transparent; color: #9ca3af; text-align: center; font-size: 13px; padding: 10px; z-index: 100;} </style><div class="rodape">PackFlow - Sistema em desenvolvimento - 2026</div>""", unsafe_allow_html=True)

load_dotenv() 
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

ARQUIVO_DB = "banco_encomendas.csv"
ARQUIVO_USUARIOS = "banco_usuarios.csv"
PLATAFORMAS_OPCOES = ["Mercado Livre", "Shopee", "Amazon", "Shein", "Petz", "Magalu", "AliExpress", "Americanas", "Casas Bahia", "Outro", "Não identificado"]
TAMANHO_OPCOES = ["Pequeno", "Médio", "Grande"]

# --- FUNCOES DE SEGURANCA ---
def gerar_hash(senha): return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def inicializar_banco_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        df = pd.DataFrame([{"Nome": "Administrador", "Login": "supervisor", "Senha": gerar_hash("admin789"), "Role": "supervisor", "Trocar_Senha": "Nao"}])
        df.to_csv(ARQUIVO_USUARIOS, index=False)

inicializar_banco_usuarios()

if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario_logado': None, 'nome_usuario': None, 'role_usuario': None, 'deve_trocar_senha': False, 'uploader_key': 0})

# --- LOGIN ---
if not st.session_state['autenticado']:
    col1, col_login, col3 = st.columns([3, 2, 3])
    with col_login:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
        else: st.markdown("<h2 style='text-align: center;'>PackFlow</h2>", unsafe_allow_html=True)
        
        user = st.text_input("Login")
        pw = st.text_input("Senha", type="password")
        if st.button("Autenticar", type="primary", use_container_width=True):
            df = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
            usuario = df[(df['Login'] == user) & (df['Senha'] == gerar_hash(pw))]
            if not usuario.empty:
                d = usuario.iloc[0]
                st.session_state.update({'autenticado': True, 'usuario_logado': d['Login'], 'nome_usuario': d['Nome'], 'role_usuario': d['Role'], 'deve_trocar_senha': (d['Trocar_Senha'] == 'Sim')})
                st.rerun()
            else: st.error("Credenciais inválidas.")
    st.stop()

# --- TROCA SENHA ---
if st.session_state['deve_trocar_senha']:
    st.warning("Primeiro acesso: Altere sua senha.")
    nova = st.text_input("Nova Senha", type="password")
    if st.button("Salvar"):
        df = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
        df.loc[df['Login'] == st.session_state['usuario_logado'], ['Senha', 'Trocar_Senha']] = [gerar_hash(nova), 'Nao']
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        st.session_state['deve_trocar_senha'] = False
        st.rerun()
    st.stop()

# --- SISTEMA ---
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.markdown(f"**{st.session_state['nome_usuario']}** ({st.session_state['role_usuario']})")
if st.sidebar.button("Sair"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

st.title("PackFlow - Gestão de Pacotes")
abas = ["Cadastro", "Consulta"]
if st.session_state['role_usuario'] == 'supervisor': abas.append("Gestão de Usuários")
aba_cad, aba_cons, *aba_gestao = st.tabs(abas)

with aba_cad:
    # (Inserir aqui a lógica de captura de imagem da aba_cadastro anterior)
    st.info("Funcionalidade de Cadastro Ativa.")

with aba_cons:
    # (Inserir aqui a lógica de consulta, métricas e data_editor da aba_consulta anterior)
    st.info("Funcionalidade de Consulta Ativa.")

if st.session_state['role_usuario'] == 'supervisor':
    with aba_gestao[0]:
        st.info("Funcionalidade de Gestão de Usuários Ativa.")
