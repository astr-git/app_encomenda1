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

# CSS para Estilo e Rodapé
st.markdown("""
    <style>
    .stApp {background-color: #ffffff;}
    .rodape {position: fixed; left: 0; bottom: 0; width: 100%; background-color: transparent; color: #9ca3af; text-align: center; font-size: 13px; padding: 10px; z-index: 100;}
    </style>
    <div class="rodape">PackFlow - Sistema em desenvolvimento - 2026</div>
""", unsafe_allow_html=True)

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

# --- FUNCOES DE ENCOMENDAS ---
def extrair_dados(imagem):
    prompt = "Analise a etiqueta e extraia em JSON: nome_comprador, bloco, apartamento, nota_fiscal, plataforma."
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, imagem], config=types.GenerateContentConfig(response_mime_type="application/json"))
        return json.loads(response.text)
    except: return None

def salvar_no_banco(nome, bloco, apto, nf, plataforma, tamanho, usuario):
    fuso_br = timezone(timedelta(hours=-3))
    data_hora_atual = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
    novo = pd.DataFrame([{"Data Cadastro": data_hora_atual, "Quem Cadastrou": usuario, "Nome do Comprador": nome, "Bloco": bloco, "Apartamento": apto, "Nota Fiscal": nf, "Plataforma": plataforma, "Tamanho do Pacote": tamanho, "Status": "Aguardando Retirada", "Data Retirada": "", "Quem Retirou": ""}])
    if os.path.exists(ARQUIVO_DB):
        df = pd.concat([pd.read_csv(ARQUIVO_DB, dtype=str), novo], ignore_index=True)
    else: df = novo
    df.to_csv(ARQUIVO_DB, index=False)

@st.dialog("Revisar e Salvar")
def modal_salvar(d):
    nome = st.text_input("Nome", value=d.get("nome_comprador", ""))
    bloco = st.text_input("Bloco", value=d.get("bloco", ""))
    apto = st.text_input("Apartamento", value=d.get("apartamento", ""))
    if st.button("Salvar"):
        salvar_no_banco(nome, bloco, apto, d.get("nota_fiscal", ""), d.get("plataforma", ""), "Pequeno", st.session_state['usuario_logado'])
        st.rerun()

# --- LOGIN E SISTEMA ---
if not st.session_state['autenticado']:
    col1, col_login, col3 = st.columns([3, 2, 3])
    with col_login:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
        user = st.text_input("Login")
        pw = st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary", use_container_width=True):
            df = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
            usuario = df[(df['Login'] == user) & (df['Senha'] == gerar_hash(pw))]
            if not usuario.empty:
                d = usuario.iloc[0]
                st.session_state.update({'autenticado': True, 'usuario_logado': d['Login'], 'nome_usuario': d['Nome'], 'role_usuario': d['Role'], 'deve_trocar_senha': (d['Trocar_Senha'] == 'Sim')})
                st.rerun()
            else: st.error("Credenciais inválidas.")
    st.stop()

# --- ABA PRINCIPAL ---
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.markdown(f"**{st.session_state['nome_usuario']}**")
if st.sidebar.button("Sair"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

st.title("PackFlow - Gestão de Pacotes")
abas = ["Cadastro", "Consulta"]
if st.session_state['role_usuario'] == 'supervisor': abas.append("Usuários")
aba_cad, aba_cons, *aba_gestao = st.tabs(abas)

with aba_cad:
    cam = st.radio("Método", ["Câmera", "Upload"])
    img = st.camera_input("Foto") if cam == "Câmera" else st.file_uploader("Upload")
    if img:
        d = extrair_dados(PIL.Image.open(img))
        if d and st.button("Revisar e Salvar"): modal_salvar(d)

with aba_cons:
    if os.path.exists(ARQUIVO_DB):
        df = pd.read_csv(ARQUIVO_DB, dtype=str)
        st.metric("Pendentes", len(df[df["Status"]=="Aguardando Retirada"]))
        st.data_editor(df, use_container_width=True)
    else: st.info("Nenhum dado.")
