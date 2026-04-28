import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import numpy as np

# Configuração da página
st.set_page_config(page_title="DataScout Pro Ultimate", layout="wide")

# --- CONFIGURAÇÕES ---
LIGAS = {
    "Premier League": "9", 
    "Brasileirão": "24", 
    "La Liga": "12", 
    "Serie A (ITA)": "11", 
    "Bundesliga": "20", 
    "Ligue 1": "13"
}

# --- MOTOR DE EXTRAÇÃO (VERSÃO ROBUSTA) ---
@st.cache_data(ttl=86400)
def get_full_data(league_id):
    def scrape(cat):
        # Forçamos o uso da URL em inglês para garantir nomes de colunas consistentes
        url = f"https://fbref.com/en/comps/{league_id}/{cat}/players"
        
        # Delay de segurança para evitar bloqueio (Rate Limit do FBref)
        time.sleep(5) 
        
        try:
            # Simulando um navegador para diminuir chances de bloqueio
            storage = pd.read_html(url, header=1)
            if len(storage) == 0:
                return pd.DataFrame()
            
            df = storage[0]
            
            # Limpeza: Remove linhas que repetem o cabeçalho no meio da tabela
            if 'Player' in df.columns:
                df = df[df['Player'] != 'Player'].copy()
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()

    # Tenta pegar a primeira tabela (Estatísticas Gerais)
    df_std = scrape("stats")
    
    # Se a primeira tabela falhar, retorna None para o app tratar
    if df_std.empty or 'Player' not in df_std.columns:
        return None

    # Tenta pegar a segunda tabela (Finalizações)
    df_shoot = scrape("shooting")
    
    # Se a segunda tabela existir, faz o merge. Se não, usa só a primeira.
    if not df_shoot.empty and 'Player' in df_shoot.columns:
        # Colunas úteis da segunda tabela (evitando repetir info básica)
        cols_to_use = [c for c in df_shoot.columns if c not in ['Nation', 'Pos', 'Squad', 'Age', 'Born', 'Matches']]
        try:
            df_final = pd.merge(df_std, df_shoot[cols_to_use], on=['Player'], how='left', suffixes=('', '_drop'))
            df_final = df_final.loc[:, ~df_final.columns.str.contains('_drop')]
            
            # Converte colunas para numérico
            for col in df_final.columns:
                if col not in ['Player', 'Squad', 'Pos']:
                    df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
            return df_final
        except:
            return df_std
    
    return df_std

# --- LÓGICA DE SIMILARIDADE ---
def buscar_similares(df, nome_jogador, metricas):
    if nome_jogador not in df['Player'].values: return None
    
    df_norm = df.copy()
    for m in metricas:
        if m in df_norm.columns and df_norm[m].max() != 0:
            df_norm[m] = df_norm[m] / df_norm[m].max()
            
    alvo = df_norm[df_norm['Player'] == nome_jogador][metricas].values[0]
    
    distancias = []
    for idx, row in df_norm.iterrows():
        dist = np.linalg.norm(alvo - row[metricas].values)
        distancias.append(dist)
    
    df['Similaridade_Score'] = distancias
    return df.sort_values(by='Similaridade_Score').head(6)

# --- INTERFACE ---
st.title("🚀 DataScout Pro: Expert Edition")

with st.sidebar:
    st.header("Configuração")
    liga_nome = st.selectbox("Selecione a Liga", list(LIGAS.keys()))
    st.info("Nota: O FBref limita o acesso. Se der erro, aguarde 1 minuto e mude a liga.")

# Carregamento dos dados
df = get_full_data(LIGAS[liga_nome])

# VERIFICAÇÃO DE SEGURANÇA
if df is not None and not df.empty and 'Player' in df.columns:
    
    menu = st.tabs(["📊 Comparativo Radar", "🧬 Busca por Similaridade", "🔝 Rankings"])

    # --- TAB 1: COMPARATIVO ---
    with menu[0]:
        c1, c2 = st.columns(2)
        with c1:
            p1 = st.selectbox("Jogador 1", df['Player'].unique(), index=0)
        with c2:
            p2 = st.selectbox("Jogador 2", df['Player'].unique(), index=1)
        
        # Filtra métricas numéricas para o radar
        metricas_default = ['Gls', 'xG', 'Ast', 'xA']
        colunas_num = [c for c in df.columns if c not in ['Player', 'Squad', 'Pos', 'Age', 'Nation']]
        
        m_escolhidas = st.multiselect("Métricas para o Radar", colunas_num, default=[m for m in metricas_default if m in colunas_num])
        
        if len(m_escolhidas) >= 3:
            # Normalização temporária para o gráfico
            df_radar = df.copy()
            for m in m_escolhidas:
                max_val = df_radar[m].max()
                if max_val > 0: df_radar[m] = df_radar[m] / max_val
            
            d1 = df_radar[df_radar['Player'] == p1].iloc[0]
            d2 = df_radar[df_radar['Player'] == p2].iloc[0]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=[d1[m] for m in m_escolhidas], theta=m_escolhidas, fill='toself', name=p1))
            fig.add_trace(go.Scatterpolar(r=[d2[m] for m in m_escolhidas], theta=m_escolhidas, fill='toself', name=p2, fillcolor='rgba(255, 0, 0, 0.3)'))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), title="Comparação de Performance (Relativa ao melhor da liga)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Selecione pelo menos 3 métricas.")

    # --- TAB 2: SIMILARIDADE ---
    with menu[1]:
        st.subheader("🧬 Encontre jogadores com estilo parecido")
        ref_p = st.selectbox("Selecione o Jogador de Referência", df['Player'].unique(), key="sim_box")
        
        # Usamos métricas de estilo (chutes e gols)
        metricas_estilo = [m for m in ['Gls', 'xG', 'Sh', 'SoT', 'Dist'] if m in df.columns]
        
        if st.button("Buscar Jogadores Similares"):
            similares = buscar_similares(df, ref_p, metricas_estilo)
            st.write(f"Jogadores matematicamente mais parecidos com {ref_p}:")
            st.dataframe(similares[['Player', 'Squad', 'Age', 'Pos'] + metricas_estilo])

    # --- TAB 3: RANKINGS ---
    with menu[2]:
        st.subheader("🔝 Top 15 da Liga")
        metrica_top = st.selectbox("Ordenar por:", [c for c in df.columns if c not in ['Player', 'Squad', 'Pos', 'Nation']])
        top15 = df.nlargest(15, metrica_top)[['Player', 'Squad', 'Age', 'Pos', metrica_top]]
        st.dataframe(top15.style.background_gradient(cmap='Greens'))

else:
    # MENSAGEM DE ERRO CASO O FBREF BLOQUEIE
    st.error("⚠️ Não foi possível encontrar a coluna 'Player' nos dados.")
    st.warning("Isso geralmente acontece porque o FBref bloqueou o acesso temporário do servidor do Streamlit (Rate Limit).")
    st.info("O que fazer? \n1. Espere 1 ou 2 minutos e atualize a página. \n2. Tente selecionar outra liga na barra lateral. \n3. Se estiver rodando localmente, verifique sua conexão.")
