import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import numpy as np

st.set_page_config(page_title="DataScout Pro Ultimate", layout="wide")

# --- CONFIGURAÇÕES ---
LIGAS = {
    "Brasileirão": "24", "Premier League": "9", "La Liga": "12", 
    "Serie A (ITA)": "11", "Bundesliga": "20", "Ligue 1": "13"
}

# --- MOTOR DE EXTRAÇÃO (MELHORADO) ---
@st.cache_data(ttl=86400)
def get_full_data(league_id):
    def scrape(cat):
        url = f"https://fbref.com/en/comps/{league_id}/{cat}/players"
        time.sleep(3) # Respeitando o limite do FBref
        try:
            df = pd.read_html(url, header=1)[0]
            df = df[df['Player'] != 'Player'].copy()
            # Remove colunas duplicadas que aparecem no merge depois
            cols_to_keep = ['Player', 'Squad', 'Age', 'Pos'] + [c for c in df.columns if c not in ['Player', 'Nation', 'Pos', 'Squad', 'Age', 'Born', 'Matches']]
            return df[cols_to_keep]
        except:
            return pd.DataFrame()

    # Puxa duas tabelas e junta (Merge)
    df_std = scrape("stats")
    df_shoot = scrape("shooting")
    
    if not df_shoot.empty:
        # Junta as tabelas pelo nome do jogador e time
        df_final = pd.merge(df_std, df_shoot, on=['Player', 'Squad', 'Age', 'Pos'], suffixes=('', '_drop'))
        # Remove colunas repetidas
        df_final = df_final.loc[:, ~df_final.columns.str.contains('_drop')]
        
        # Limpeza Numérica
        for col in df_final.columns:
            if col not in ['Player', 'Squad', 'Pos']:
                df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
        return df_final
    return df_std

# --- LÓGICA DE SIMILARIDADE ---
def buscar_similares(df, nome_jogador, metricas):
    if nome_jogador not in df['Player'].values: return None
    
    # Normaliza os dados para o cálculo de distância
    df_norm = df.copy()
    for m in metricas:
        if df_norm[m].max() != 0:
            df_norm[m] = df_norm[m] / df_norm[m].max()
            
    alvo = df_norm[df_norm['Player'] == nome_jogador][metricas].values[0]
    
    # Cálculo de Distância Euclidiana (quem está mais perto matematicamente)
    distancias = []
    for idx, row in df_norm.iterrows():
        dist = np.linalg.norm(alvo - row[metricas].values)
        distancias.append(dist)
    
    df['Similaridade'] = distancias
    return df.sort_values(by='Similaridade').head(6) # O primeiro é ele mesmo

# --- INTERFACE ---
st.title("🚀 DataScout Pro Ultimate")

liga = st.sidebar.selectbox("Liga", list(LIGAS.keys()))
df = get_full_data(LIGAS[liga])

if df is not None:
    menu = st.tabs(["📊 Comparativo", "🧬 Busca por Similaridade", "🔝 Rankings"])

    # --- TABELA DE COMPARAÇÃO ---
    with menu[0]:
        c1, c2 = st.columns(2)
        p1 = c1.selectbox("Jogador 1", df['Player'].unique(), index=0)
        p2 = c2.selectbox("Jogador 2", df['Player'].unique(), index=1)
        
        m_escolhidas = st.multiselect("Métricas", [c for c in df.columns if c not in ['Player', 'Squad', 'Pos']], default=['Gls', 'xG', 'Ast', 'xA', 'Sh'])
        
        # Cards de Destaque
        d1 = df[df['Player'] == p1].iloc[0]
        d2 = df[df['Player'] == p2].iloc[0]
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric(f"Gols {p1}", d1['Gls'])
        col_m2.metric(f"Gols {p2}", d2['Gls'], delta=float(d2['Gls']-d1['Gls']))
        col_m3.metric(f"xG {p1}", d1['xG'])
        col_m4.metric(f"xG {p2}", d2['xG'], delta=round(float(d2['xG']-d1['xG']), 2))

        # Radar
        df_radar = df.copy()
        for m in m_escolhidas: df_radar[m] = df_radar[m] / df_radar[m].max()
        r1 = df_radar[df_radar['Player'] == p1].iloc[0]
        r2 = df_radar[df_radar['Player'] == p2].iloc[0]
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=[r1[m] for m in m_escolhidas], theta=m_escolhidas, fill='toself', name=p1))
        fig.add_trace(go.Scatterpolar(r=[r2[m] for m in m_escolhidas], theta=m_escolhidas, fill='toself', name=p2))
        st.plotly_chart(fig)

    # --- TABELA DE SIMILARIDADE ---
    with menu[1]:
        st.subheader("Encontre jogadores com estilo de jogo parecido")
        ref_p = st.selectbox("Selecione o Jogador de Referência", df['Player'].unique())
        
        metricas_estilo = ['Gls', 'xG', 'Sh', 'SoT', 'Dist', 'FK', 'PK']
        
        if st.button("Buscar Sósias"):
            similares = buscar_similares(df, ref_p, metricas_estilo)
            st.write(f"Jogadores mais parecidos com {ref_p} baseados em finalizações:")
            st.table(similares[['Player', 'Squad', 'Age', 'Pos', 'Gls', 'xG']])

    # --- TABELA DE RANKINGS ---
    with menu[2]:
        st.subheader("Top 10 por Métrica")
        metrica_top = st.selectbox("Escolha a métrica", [c for c in df.columns if c not in ['Player', 'Squad', 'Pos']])
        top10 = df.nlargest(10, metrica_top)[['Player', 'Squad', 'Age', metrica_top]]
        st.table(top10)

else:
    st.warning("Carregando dados...")