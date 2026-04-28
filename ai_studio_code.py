import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import numpy as np
import requests

st.set_page_config(page_title="DataScout Pro Ultimate", layout="wide")

LIGAS = {
    "Premier League": "9", 
    "Brasileirão": "24", 
    "La Liga": "12", 
    "Serie A (ITA)": "11", 
    "Bundesliga": "20", 
    "Ligue 1": "13"
}

# --- MOTOR DE EXTRAÇÃO COM CAMUFLAGEM (SPOOFING) ---
@st.cache_data(ttl=86400)
def get_full_data(league_id):
    def scrape(cat):
        url = f"https://fbref.com/en/comps/{league_id}/{cat}/players"
        
        # Cabeçalhos para fingir ser um navegador real
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        time.sleep(6) # Delay maior para segurança
        
        try:
            # Em vez de pd.read_html direto, usamos requests para baixar o HTML primeiro
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                return pd.DataFrame()
            
            # Passamos o texto do HTML para o Pandas
            storage = pd.read_html(response.text, header=1)
            if len(storage) == 0:
                return pd.DataFrame()
            
            df = storage[0]
            if 'Player' in df.columns:
                df = df[df['Player'] != 'Player'].copy()
                return df
            return pd.DataFrame()
        except:
            return pd.DataFrame()

    df_std = scrape("stats")
    
    if df_std.empty or 'Player' not in df_std.columns:
        return None

    # Tenta Shooting para dados extras
    df_shoot = scrape("shooting")
    
    if not df_shoot.empty and 'Player' in df_shoot.columns:
        cols_to_use = [c for c in df_shoot.columns if c not in ['Nation', 'Pos', 'Squad', 'Age', 'Born', 'Matches']]
        try:
            df_final = pd.merge(df_std, df_shoot[cols_to_use], on=['Player'], how='left', suffixes=('', '_drop'))
            df_final = df_final.loc[:, ~df_final.columns.str.contains('_drop')]
            for col in df_final.columns:
                if col not in ['Player', 'Squad', 'Pos']:
                    df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
            return df_final
        except:
            return df_std
    
    return df_std

# --- INTERFACE ---
st.title("🚀 DataScout Pro: Camuflagem Ativa")

with st.sidebar:
    st.header("Configuração")
    liga_nome = st.selectbox("Selecione a Liga", list(LIGAS.keys()))
    if st.button("🔄 Forçar Atualização"):
        st.cache_data.clear()
        st.rerun()

df = get_full_data(LIGAS[liga_nome])

if df is not None and not df.empty and 'Player' in df.columns:
    st.success(f"Dados de {liga_nome} carregados!")
    menu = st.tabs(["📊 Comparativo Radar", "🧬 Busca por Similaridade", "🔝 Rankings"])

    with menu[0]:
        c1, c2 = st.columns(2)
        p1 = c1.selectbox("Jogador 1", df['Player'].unique(), index=0)
        p2 = c2.selectbox("Jogador 2", df['Player'].unique(), index=1)
        
        colunas_num = [c for c in df.columns if c not in ['Player', 'Squad', 'Pos', 'Age', 'Nation']]
        m_escolhidas = st.multiselect("Métricas", colunas_num, default=['Gls', 'xG', 'Ast', 'xA'])
        
        if len(m_escolhidas) >= 3:
            df_radar = df.copy()
            for m in m_escolhidas:
                max_val = df_radar[m].max()
                if max_val > 0: df_radar[m] = df_radar[m] / max_val
            
            d1 = df_radar[df_radar['Player'] == p1].iloc[0]
            d2 = df_radar[df_radar['Player'] == p2].iloc[0]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=[d1[m] for m in m_escolhidas], theta=m_escolhidas, fill='toself', name=p1))
            fig.add_trace(go.Scatterpolar(r=[d2[m] for m in m_escolhidas], theta=m_escolhidas, fill='toself', name=p2, fillcolor='rgba(255, 0, 0, 0.3)'))
            st.plotly_chart(fig, use_container_width=True)

    with menu[1]:
        st.subheader("🧬 Similaridade")
        ref_p = st.selectbox("Referência", df['Player'].unique())
        if st.button("Buscar"):
            # Lógica simples de similaridade
            metrics = ['Gls', 'xG', 'Sh', 'Ast']
            df_sim = df.copy()
            for m in metrics: df_sim[m] = df_sim[m] / df_sim[m].max()
            alvo = df_sim[df_sim['Player'] == ref_p][metrics].values[0]
            df['Sim_Score'] = [np.linalg.norm(alvo - x) for x in df_sim[metrics].values]
            st.table(df.sort_values('Sim_Score').head(6)[['Player', 'Squad', 'Gls', 'xG', 'Ast']])

    with menu[2]:
        st.subheader("🔝 Top 15")
        metrica_top = st.selectbox("Métrica:", [c for c in df.columns if c not in ['Player', 'Squad', 'Pos']])
        st.dataframe(df.nlargest(15, metrica_top)[['Player', 'Squad', metrica_top]])

else:
    st.error("Acesso bloqueado pelo FBref.")
    st.info("DICA: Como o Streamlit é um servidor público, o FBref bloqueia com frequência. Tente rodar o arquivo no seu computador (Localhost) para ter 100% de estabilidade.")
