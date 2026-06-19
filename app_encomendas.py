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
st.set_page_config(page_title="Gestor de Encomendas", layout="wide")

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

# --- VARIAVEIS DE SESSAO ---
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

# --- FUNCOES PRINCIPAIS ---
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

def salvar_no_banco(nome, bloco, apto, nf, plataforma, tamanho, usuario):
    # Fuso horario do Brasil (UTC-3)
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

# ==========================================
# TELA DE LOGIN (CONTROLE DE ACESSO)
# ==========================================
if not st.session_state['autenticado']:
    st.subheader("Controle de Acesso - Sistema de Portaria")
    
    col_login, _ = st.columns([1, 2])
    with col_login:
        usuario_input = st.text_input("Usuario")
        senha_input = st.text_input("Senha", type="password")
        
        if st.button("Autenticar", type="primary", use_container_width=True):
            usuarios_validos = {
                "portaria_dia": "senha123",
                "portaria_noite": "senha456",
                "supervisor": "admin789"
            }
            
            if usuario_input in usuarios_validos and usuarios_validos[usuario_input] == senha_input:
                st.session_state['autenticado'] = True
                st.session_state['usuario_logado'] = usuario_input
                st.rerun()
            else:
                st.error("Credenciais invalidas. Tente novamente.")
    st.stop()

# ==========================================
# APLICATIVO AUTENTICADO
# ==========================================

st.sidebar.markdown(f"Usuario Conectado: **{st.session_state['usuario_logado']}**")
if st.sidebar.button("Encerrar Sessao"):
    st.session_state['autenticado'] = False
    st.session_state['usuario_logado'] = None
    st.rerun()

st.title("Sistema de Gestao de Encomendas")

aba_cadastro, aba_consulta = st.tabs(["Cadastro de Encomendas", "Consultar Encomendas"])

# ==========================================
# ABA 1: CADASTRO
# ==========================================
with aba_cadastro:
    if 'mensagem_sucesso' in st.session_state:
        st.success(st.session_state['mensagem_sucesso'])
        del st.session_state['mensagem_sucesso']

    st.markdown("Utilize a camera ou faca o upload da foto. A analise iniciara automaticamente.")
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("1. Captura da Etiqueta")
        tipo_captura = st.radio("Como deseja capturar a imagem?", ["Camera do Celular", "Upload de Arquivo"], horizontal=True)
        arquivo_final = None
        
        if tipo_captura == "Camera do Celular":
            arquivo_final = st.camera_input("Tire a foto da etiqueta", key=f"camera_{st.session_state['uploader_key']}")
        else:
            arquivo_final = st.file_uploader("Escolha ou arraste a imagem aqui", type=["jpg", "jpeg", "png"], key=f"uploader_{st.session_state['uploader_key']}")
        
        if arquivo_final:
            imagem_pil = PIL.Image.open(arquivo_final)
            if tipo_captura == "Upload de Arquivo":
                st.image(imagem_pil, caption="Etiqueta Carregada", use_container_width=True)
            
            nome_identificador = arquivo_final.name if tipo_captura == "Upload de Arquivo" else f"foto_cam_{st.session_state['uploader_key']}"
            
            if 'ultimo_arquivo' not in st.session_state or st.session_state['ultimo_arquivo'] != nome_identificador:
                with st.spinner("Processando dados com Inteligencia Artificial..."):
                    resultado_ia = extrair_dados(imagem_pil)
                    if resultado_ia:
                        st.session_state['dados'] = resultado_ia
                        st.session_state['ultimo_arquivo'] = nome_identificador

    with col2:
        st.subheader("2. Conferir e Salvar")
        if 'dados' in st.session_state:
            d = st.session_state['dados']
            
            nome = st.text_input("Nome do Comprador", value=d.get("nome_comprador", ""))
            c_bloco, c_apto = st.columns(2)
            bloco = c_bloco.text_input("Bloco", value=d.get("bloco", ""))
            apto = c_apto.text_input("Apartamento", value=d.get("apartamento", ""))
            nf = st.text_input("Nota Fiscal / Declaracao", value=d.get("nota_fiscal", ""))
            
            plataforma_ia = d.get("plataforma", "Não identificado")
            try:
                index_padrao = PLATAFORMAS_OPCOES.index(plataforma_ia)
            except:
                index_padrao = PLATAFORMAS_OPCOES.index("Não identificado")
                
            c_plat, c_tam = st.columns(2)
            plataforma = c_plat.selectbox("Plataforma / Marketplace", options=PLATAFORMAS_OPCOES, index=index_padrao)
            tamanho = c_tam.selectbox("Tamanho do Pacote", options=TAMANHO_OPCOES, index=0)
            
            st.write("") 
            if st.button("Salvar Registro", type="primary", use_container_width=True):
                salvar_no_banco(nome, bloco, apto, nf, plataforma, tamanho, st.session_state['usuario_logado'])
                st.session_state['mensagem_sucesso'] = f"Encomenda de {nome} salva com sucesso!"
                del st.session_state['dados']
                if 'ultimo_arquivo' in st.session_state:
                    del st.session_state['ultimo_arquivo']
                st.session_state['uploader_key'] += 1
                st.rerun()
        else:
            st.info("Aguardando captura ou upload da imagem...")

# ==========================================
# ABA 2: CONSULTA E RETIRADA
# ==========================================
with aba_consulta:
    if os.path.exists(ARQUIVO_DB):
        df_encomendas = pd.read_csv(ARQUIVO_DB, dtype=str)
        df_encomendas.fillna("", inplace=True)
        
        st.subheader("Filtros de Pesquisa")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            filtro_nome = st.text_input("Pesquisar por Nome:")
        with col_f2:
            opcoes_blocos = ["Todos"] + [str(i) for i in range(1, 19)]
            filtro_bloco = st.selectbox("Filtrar por Bloco:", opcoes_blocos)
        with col_f3:
            if filtro_bloco == "Todos":
                filtro_apto = st.text_input("Filtrar por Apartamento (Ex: 104):")
            else:
                bloco_int = int(filtro_bloco)
                andares = 20 if bloco_int in [17, 18] else 5
                aptos_validos = ["Todos"]
                for andar in range(1, andares + 1):
                    for unid in range(1, 9):
                        aptos_validos.append(f"{andar}{unid:02d}")
                filtro_apto = st.selectbox("Filtrar por Apartamento:", aptos_validos)
                
        df_filtrado = df_encomendas.copy()
        
        if filtro_nome.strip():
            df_filtrado = df_filtrado[df_filtrado["Nome do Comprador"].str.contains(filtro_nome, case=False, na=False)]
        if filtro_bloco != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Bloco"].astype(str).str.lstrip('0') == filtro_bloco]
        if filtro_apto and filtro_apto != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Apartamento"].astype(str) == filtro_apto]
            
        st.divider()
        st.subheader("Registrar Retirada de Encomenda")
        pendentes = df_filtrado[df_filtrado["Status"] == "Aguardando Retirada"]
        
        if not pendentes.empty:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                opcoes_pendentes = pendentes.apply(
                    lambda row: f"{row['Apartamento']} (Bl {row['Bloco']}) - {row['Nome do Comprador']} [{row['Tamanho do Pacote']}]", axis=1).tolist()
                
                with c1:
                    pacote_selecionado = st.selectbox("Selecione o pacote pendente:", opcoes_pendentes)
                with c2:
                    pessoa_retirou = st.text_input("Nome da pessoa que retirou:")
                with c3:
                    st.write("") 
                    st.write("")
                    if st.button("Confirmar Entrega", type="primary"):
                        if pessoa_retirou.strip() == "":
                            st.error("Informe quem retirou!")
                        else:
                            idx_real = pendentes.index[opcoes_pendentes.index(pacote_selecionado)]
                            df_encomendas.at[idx_real, "Status"] = "Retirado"
                            
                            # Fuso horario do Brasil para a retirada
                            fuso_br = timezone(timedelta(hours=-3))
                            df_encomendas.at[idx_real, "Data Retirada"] = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
                            
                            df_encomendas.at[idx_real, "Quem Retirou"] = pessoa_retirou
                            df_encomendas.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')
                            st.success("Retirada registrada com sucesso!")
                            st.rerun() 
        else:
            st.success("Tudo limpo! Nao ha encomendas aguardando retirada para os filtros selecionados.")
        
        st.divider()
        st.subheader("Historico Completo (Editavel)")
        st.caption("Dica: De um clique duplo sobre as celulas para corrigir erros. As alteracoes sao salvas automaticamente.")
        
        df_exibicao = df_filtrado.sort_values(by="Data Cadastro", ascending=False)
        
        edited_df = st.data_editor(
            df_exibicao,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed", 
            column_config={
                "Plataforma": st.column_config.SelectboxColumn("Plataforma", options=PLATAFORMAS_OPCOES, required=True),
                "Tamanho do Pacote": st.column_config.SelectboxColumn("Tamanho do Pacote", options=TAMANHO_OPCOES, required=True),
                "Data Cadastro": st.column_config.TextColumn(disabled=True),
                "Quem Cadastrou": st.column_config.TextColumn(disabled=True),
                "Status": st.column_config.TextColumn(disabled=True),
                "Data Retirada": st.column_config.TextColumn(disabled=True),
                "Quem Retirou": st.column_config.TextColumn(disabled=True),
            }
        )
        
        if not edited_df.equals(df_exibicao):
            df_encomendas.update(edited_df)
            df_encomendas.to_csv(ARQUIVO_DB, index=False, encoding='utf-8')
            st.rerun()
        
        csv_download = df_filtrado.to_csv(index=False, encoding='utf-8').encode('utf-8')
        st.download_button(
            label="Baixar Relatorio Filtrado (CSV)",
            data=csv_download,
            file_name="historico_encomendas_filtrado.csv",
            mime="text/csv"
        )
    else:
        st.info("O banco de dados esta vazio. Cadastre uma encomenda primeiro.")
