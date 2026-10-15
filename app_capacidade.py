import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import calendar

# Configuração da Página
st.set_page_config(page_title="Capacity & Forecast Tool", page_icon="⚙️", layout="wide")

st.title("⚙️ Capacity Planning & Forecast de Contratos")
st.markdown("Monitorização inteligente de consumo de clientes versus a capacidade de entrega da equipa.")

# --- BARRA LATERAL ---
st.sidebar.header("📁 Base de Dados")
st.sidebar.markdown("Faça o upload do seu Excel mestre para atualizar o dashboard.")
uploaded_file = st.sidebar.file_uploader("Upload do ficheiro (Excel)", type=["xlsx"])

# Função para carregar os dados
@st.cache_data
def load_data(file):
    xls = pd.ExcelFile(file)
    df_cont = pd.read_excel(xls, sheet_name='1_Contratos')
    df_cons = pd.read_excel(xls, sheet_name='2_Consumo_Mensal')
    df_equipa = pd.read_excel(xls, sheet_name='3_Equipa')
    df_ausencias = pd.read_excel(xls, sheet_name='4_Ausencias_e_Feriados')
    return df_cont, df_cons, df_equipa, df_ausencias

# Variáveis globais de mês e dias úteis
MES_PROJECAO = "Nov 2026"
DIAS_UTEIS_MES = 21

if uploaded_file is not None:
    df_cont, df_cons, df_equipa, df_ausencias = load_data(uploaded_file)
    
    # ==========================================
    # 1. MOTOR DE PROCURA (FORECAST DE CLIENTES)
    # ==========================================
    # Assumindo que as colunas de datas começam no índice 2
    # Procurar a última coluna que não tem nome "Unnamed"
    cols = list(df_cons.columns)
    
    # Calcular o Forecast baseado nos últimos 3 meses preenchidos
    # Para simplificação visual, pegamos as 3 colunas antes das vazias
    historico = df_cons.iloc[:, 2:12] # Baseado na estrutura do seu excel
    ultimos_3_meses = historico.iloc[:, -3:]
    df_cons['Forecast_Mensal_Dias'] = ultimos_3_meses.mean(axis=1)
    
    procura_total = df_cons['Forecast_Mensal_Dias'].sum()
    
    # Fundir com os contratos para ver saldos
    # Calcular o total já gasto até à data (Soma horizontal do histórico)
    df_cons['Total_Ja_Gasto'] = historico.sum(axis=1, numeric_only=True)
    
    df_master = pd.merge(df_cont, df_cons[['Cliente', 'Nome_do_Servico', 'Total_Ja_Gasto', 'Forecast_Mensal_Dias']], 
                         on=['Cliente', 'Nome_do_Servico'])
    
    df_master['Saldo_Atual'] = df_master['Total_Dias_Contratados'] - df_master['Total_Ja_Gasto']
    df_master['Saldo_Apos_Prox_Mes'] = df_master['Saldo_Atual'] - df_master['Forecast_Mensal_Dias']
    
    # ==========================================
    # 2. MOTOR DE OFERTA (CAPACIDADE DA EQUIPA)
    # ==========================================
    resultados_cap = []
    
    for idx, row in df_equipa.iterrows():
        nome = row['Nome_Colaborador']
        
        dias_base = DIAS_UTEIS_MES # Usamos o fixo de Novembro 2026 para a projeção
        
        # Descontos de Ausências (Lendo da aba 4 para 11/2026)
        ausencias_colab = df_ausencias[
            ((df_ausencias['Nome_Colaborador'] == nome) | (df_ausencias['Nome_Colaborador'] == 'Todos')) &
            (df_ausencias['Data_ou_Periodo'].astype(str).str.contains('11/2026', na=False))
        ]['Dias_Uteis_Descontados'].sum()
        
        dias_pos_ausencias = dias_base - ausencias_colab
        
        # Formações
        formacao_externa = 5 / 12
        dias_pos_externa = dias_pos_ausencias - formacao_externa
        formacao_interna = dias_pos_externa * 0.05
        
        capacidade_liquida = dias_pos_externa - formacao_interna
        
        resultados_cap.append({
            'Consultor': nome,
            'Dias Úteis Brutos': dias_base,
            'Ausências/Feriados': ausencias_colab,
            'Capacidade Líquida': round(capacidade_liquida, 2)
        })

    df_cap = pd.DataFrame(resultados_cap)
    oferta_total = df_cap['Capacidade Líquida'].sum()
    
    balanco_final = oferta_total - procura_total
    
    # ==========================================
    # 3. INTERFACE VISUAL DO DASHBOARD
    # ==========================================
    
    st.divider()
    
    # --- SECÇÃO 1: ALERTAS E BALANÇO GERAL ---
    st.subheader(f"⚖️ Balanço da Operação ({MES_PROJECAO})")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Procura (Forecast Clientes)", value=f"{procura_total:.1f} dias")
    with col2:
        st.metric(label="Oferta (Capacidade Equipa)", value=f"{oferta_total:.1f} dias")
    with col3:
        if balanco_final >= 0:
            st.metric(label="Balanço Final (Folga)", value=f"+{balanco_final:.1f} dias")
        else:
            st.error(f"Falta de Capacidade! Faltam {abs(balanco_final):.1f} dias.")
            
    # ALERTAS DE CONTRATO (DIAS A ESGOTAR)
    st.markdown("### 🚨 Alertas de Contratos")
    contratos_em_risco = df_master[df_master['Saldo_Apos_Prox_Mes'] <= 10]
    
    if not contratos_em_risco.empty:
        for idx, row in contratos_em_risco.iterrows():
            st.warning(f"**Atenção:** {row['Cliente']} ({row['Nome_do_Servico']}) | O saldo após o próximo mês será de apenas **{row['Saldo_Apos_Prox_Mes']:.1f} dias**.")
    else:
        st.success("✅ Todos os contratos têm saldo saudável para suportar a previsão do próximo mês.")
    
    st.divider()
    
    # --- SECÇÃO 2: GRÁFICOS VISUAIS ---
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("**Procura: Para onde vão os nossos dias?**")
        fig_pie = px.pie(df_master, values='Forecast_Mensal_Dias', names='Cliente', 
                         title='Distribuição de Esforço por Cliente')
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with colB:
        st.markdown("**Oferta: De onde vêm os nossos dias?**")
        fig_bar = px.bar(df_cap, x='Consultor', y='Capacidade Líquida', 
                         title='Capacidade Líquida por Consultor', text='Capacidade Líquida')
        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    st.divider()
    
    # --- SECÇÃO 3: TABELAS DE DETALHE ---
    st.markdown("### 📋 Visão Detalhada de Contratos e Forecast")
    st.dataframe(df_master[['Cliente', 'Nome_do_Servico', 'Data_Fim', 'Total_Dias_Contratados', 'Total_Ja_Gasto', 'Saldo_Atual', 'Forecast_Mensal_Dias', 'Saldo_Apos_Prox_Mes']].style.format({'Total_Ja_Gasto': "{:.1f}", 'Forecast_Mensal_Dias': "{:.1f}", 'Saldo_Apos_Prox_Mes': "{:.1f}"}), use_container_width=True)

else:
    st.info("Por favor, faça o upload do seu ficheiro Excel na barra lateral para inicializar o painel.")
