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
# Atualizado com o novo nome e um icone de pacote na aba do navegador
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
        # Tenta carregar a imagem do PackFlow. Se nao achar o arquivo, exibe em texto.
        if os.path.exists("logo.jpg"):
            st.image("logo.jpg", use_container_width=True)
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
        # Se a logo existir, coloca na tela de troca de senha tambem
        if os.path.exists("logo.jpg"):
            st.image("logo.jpg", use_container_width=True)
            
        st.warning(f"Olá, {st.session_state['nome_usuario']}! Esta é a sua primeira vez no sistema.")
        st.markdown("<h3 style='text-align: center;'>Alteração de Senha Obrigatória</h3>", unsafe_allow_html=True)
        
        with st.container(border=True):
            nova_senha = st.text_input("Digite sua nova senha", type="password")
            confirmar_senha = st.text_input("Confirme a nova senha", type="password")
            
            st.write("")
            
            if st.button("Salvar Nova Senha", type="primary", use_container_width=True):
                if nova_senha == "" or confirmar_senha == "":
                    st.error("As senhas não podem estar em branco.")
                elif nova_senha != confirmar_senha:
                    st.error("As senhas não coincidem.")
                else:
                    atualizar_senha(st.session_state['usuario_logado'], nova_senha)
                    st.session_state['deve_trocar_senha'] = False
                    st.success("Senha atualizada com sucesso! Carregando sistema...")
                    st.rerun()
    st.stop() 

# ==========================================
# APLICATIVO AUTENTICADO
# ==========================================

# Insere a logo no topo do menu lateral
if os.path.exists("logo.jpg"):
    st.sidebar.image("logo.jpg", use_container_width=True)
else:
    st.sidebar.markdown("## PackFlow")

st.sidebar.divider()
st.sidebar.markdown(f"Usuario: **{st.session_state['nome_usuario']}**")
st.sidebar.caption(f"Perfil: {st.session_state['role_usuario'].capitalize()}")

if st.sidebar.button("Encerrar Sessao"):
    st.session_state['autenticado'] = False
    st.session_state['usuario_logado'] = None
    st.session_state['nome_usuario'] = None
    st.session_state['role_usuario'] = None
    st.session_state['deve_trocar_senha'] = False
    st.rerun()

st.title("PackFlow - Gestão de Entregas")

abas_nomes = ["Cadastro de Encomendas", "Consultar Encomendas"]
eh_supervisor = (st.session_state['role_usuario'] == 'supervisor')

if eh_supervisor:
    abas_nomes.append("Gestão de Usuários")

objetos_abas = st.tabs(abas_nomes)
aba_cadastro = objetos_abas[0]
aba_consulta = objetos_abas[1]

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
    if 'msg_retirada' in st.session_state:
        st.success(st.session_state['msg_retirada'])
        del st.session_state['msg_retirada']

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
        
        # --- SECAO DE RETIRADA EM LOTE ---
        st.subheader("Baixa de Encomendas (Pendentes)")
        st.caption("Marque a caixa na coluna 'Selecionar' para os pacotes que estão sendo retirados agora.")
        
        pendentes = df_filtrado[df_filtrado["Status"] == "Aguardando Retirada"].copy()
        
        if not pendentes.empty:
            pendentes.insert(0, "Selecionar", False)
            
            edit_pendentes = st.data_editor(
                pendentes,
                hide_index=True,
                use_container_width=True,
                disabled=["Data Cadastro", "Quem Cadastrou", "Nome do Comprador", "Bloco", "Apartamento", "Nota Fiscal", "Plataforma", "Tamanho do Pacote", "Status"],
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
                    "Data Retirada": None, 
                    "Quem Retirou": None   
                }
            )
            
            linhas_selecionadas = edit_pendentes[edit_pendentes["Selecionar"] == True]
            
            c1, c2 = st.columns([2, 1])
            with c1:
                pessoa_retirou = st.text_input("Quem está retirando? (Opcional - deixe em branco para assumir o titular)")
            with c2:
                st.write("") 
                st.write("")
                if st.button("Confirmar Entrega", type="primary", use_container_width=True):
                    if linhas_selecionadas.empty:
                        st.error("Marque pelo menos um pacote na tabela acima para dar baixa.")
                    else:
                        modal_confirmar(linhas_selecionadas, pessoa_retirou)
        else:
            st.success("Tudo limpo! Nao ha encomendas aguardando retirada para os filtros selecionados.")
        
        st.divider()
        
        # --- HISTORICO COMPLETO ---
        st.subheader("Historico Completo")
        st.caption("Abaixo estao exibidos todos os registros (Pendentes e Retirados). De um clique duplo sobre as celulas para corrigir erros. As alteracoes sao salvas automaticamente.")
        
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

# ==========================================
# ABA 3: GESTÃO DE USUÁRIOS (SÓ SUPERVISOR)
# ==========================================
if eh_supervisor:
    with objetos_abas[2]:
        st.subheader("Cadastrar Novo Operador")
        st.markdown("Crie credenciais de acesso para a equipe de portaria. A senha deverá ser alterada por eles no primeiro login.")
        
        with st.form("form_novo_usuario", clear_on_submit=True):
            col_u1, col_u2 = st.columns(2)
            nome_novo = col_u1.text_input("Nome Completo do Operador")
            login_novo = col_u2.text_input("Login de Acesso (Ex: joao.silva)")
            senha_provisoria = st.text_input("Senha Provisoria", type="password")
            
            btn_criar = st.form_submit_button("Criar Usuario", type="primary")
            
            if btn_criar:
                if nome_novo == "" or login_novo == "" or senha_provisoria == "":
                    st.error("Todos os campos sao obrigatorios.")
                elif " " in login_novo:
                    st.error("O campo 'Login' nao pode conter espacos em branco.")
                else:
                    sucesso = adicionar_usuario(nome_novo, login_novo, senha_provisoria)
                    if sucesso:
                        st.success(f"Usuario '{login_novo}' criado com sucesso! Ele sera obrigado a trocar de senha no primeiro acesso.")
                    else:
                        st.error(f"O login '{login_novo}' ja existe no sistema. Escolha outro nome de acesso.")
        
        st.divider()
        st.subheader("Usuarios Cadastrados")
        
        df_usuarios = pd.read_csv(ARQUIVO_USUARIOS, dtype=str)
        df_visualizacao = df_usuarios[['Nome', 'Login', 'Role', 'Trocar_Senha']]
        st.dataframe(df_visualizacao, use_container_width=True, hide_index=True)
