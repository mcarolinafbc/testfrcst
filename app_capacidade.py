import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar

# Configuração da Página
st.set_page_config(page_title="Capacity & Forecast Tool", page_icon="⚙️", layout="wide")

st.title("⚙️ Capacity Planning & Forecast Global")
st.markdown("Visão executiva de Capacidade Total Anual vs Expected Delivery.")

# --- BARRA LATERAL ---
st.sidebar.header("📁 Base de Dados")
uploaded_file = st.sidebar.file_uploader("Upload do ficheiro (Excel)", type=["xlsx"])

@st.cache_data
def load_data(file):
    xls = pd.ExcelFile(file)
    df_cont = pd.read_excel(xls, sheet_name='1_Contratos')
    df_cons = pd.read_excel(xls, sheet_name='2_Consumo_Mensal')
    df_equipa = pd.read_excel(xls, sheet_name='3_Equipa')
    df_ausencias = pd.read_excel(xls, sheet_name='4_Ausencias_e_Feriados')
    return df_cont, df_cons, df_equipa, df_ausencias

def get_dias_uteis(ano, mes):
    cal = calendar.monthcalendar(ano, mes)
    return sum(1 for semana in cal for dia, weekday in zip(semana, range(7)) if dia != 0 and weekday < 5)

if uploaded_file is not None:
    df_cont, df_cons, df_equipa, df_ausencias = load_data(uploaded_file)
    
    # ---------------------------------------------------
    # 1. MOTOR DE PROCURA (FORECAST)
    # ---------------------------------------------------
    historico = df_cons.iloc[:, 2:12] 
    ultimos_3_meses = historico.iloc[:, -3:]
    df_cons['Forecast_Mensal_Dias'] = ultimos_3_meses.mean(axis=1)
    
    expected_delivery_mensal = df_cons['Forecast_Mensal_Dias'].sum()
    
    df_cons['Total_Ja_Gasto'] = historico.sum(axis=1, numeric_only=True)
    df_master = pd.merge(df_cont, df_cons[['Cliente', 'Nome_do_Servico', 'Total_Ja_Gasto', 'Forecast_Mensal_Dias']], 
                         on=['Cliente', 'Nome_do_Servico'])
    df_master['Saldo_Atual'] = df_master['Total_Dias_Contratados'] - df_master['Total_Ja_Gasto']
    df_master['Saldo_Expected_Prox_Mes'] = df_master['Saldo_Atual'] - df_master['Forecast_Mensal_Dias']
    
    # ---------------------------------------------------
    # 2. MOTOR DE OFERTA ANUAL (CAPACIDADE POR MÊS)
    # ---------------------------------------------------
    ano_atual = 2026
    meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    
    capacidade_anual = []
    
    for mes in range(1, 13):
        dias_uteis_mes = get_dias_uteis(ano_atual, mes)
        capacidade_total_mes = 0
        
        for idx, row in df_equipa.iterrows():
            try:
                data_entrada = pd.to_datetime(row['Data_Entrada'], format='%d/%m/%Y')
            except:
                data_entrada = pd.to_datetime('01/01/2000')
            
            if data_entrada.year > ano_atual or (data_entrada.year == ano_atual and data_entrada.month > mes):
                continue
                
            dias_base = dias_uteis_mes
            if data_entrada.year == ano_atual and data_entrada.month == mes and data_entrada.day > 1:
                dias_uteis_restantes = get_dias_uteis(ano_atual, mes) - (data_entrada.day * 5/7) 
                dias_base = max(0, int(dias_uteis_restantes))
            
            str_mes_ano = f"{mes:02d}/{ano_atual}"
            ausencias_colab = df_ausencias[
                ((df_ausencias['Nome_Colaborador'] == row['Nome_Colaborador']) | (df_ausencias['Nome_Colaborador'] == 'Todos')) &
                (df_ausencias['Data_ou_Periodo'].astype(str).str.contains(str_mes_ano, na=False))
            ]['Dias_Uteis_Descontados'].sum()
            
            dias_pos_ausencias = dias_base - ausencias_colab
            
            formacao_externa = 5 / 12
            dias_pos_externa = dias_pos_ausencias - formacao_externa
            formacao_interna = dias_pos_externa * 0.05
            
            capacidade_liquida = dias_pos_externa - formacao_interna
            capacidade_total_mes += max(0, capacidade_liquida)
            
        capacidade_anual.append({
            'Mês': meses_nomes[mes-1],
            'Expected Capacity': round(capacidade_total_mes, 1),
            'Expected Delivery (Forecast)': round(expected_delivery_mensal, 1)
        })
        
    df_cap_anual = pd.DataFrame(capacidade_anual)
    
    mes_foco_idx = 10 # Novembro (Índice 10)
    expected_capacity_prox_mes = df_cap_anual.loc[mes_foco_idx, 'Expected Capacity']
    expected_balance_prox_mes = expected_capacity_prox_mes - expected_delivery_mensal
    
    # ---------------------------------------------------
    # 3. INTERFACE VISUAL DO DASHBOARD
    # ---------------------------------------------------
    
    st.divider()
    
    # --- SECÇÃO 1: KPIs DO MÊS ---
    st.subheader(f"🎯 Resumo Expected (Mês de {meses_nomes[mes_foco_idx]} {ano_atual})")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Expected Delivery (Forecast)", value=f"{expected_delivery_mensal:.1f} dias")
    with col2:
        st.metric(label="Expected Capacity (Equipa)", value=f"{expected_capacity_prox_mes:.1f} dias")
    with col3:
        if expected_balance_prox_mes >= 0:
            st.metric(label="Expected Balance (Saldo)", value=f"+{expected_balance_prox_mes:.1f} dias")
        else:
            st.metric(label="Expected Balance (Saldo)", value=f"{expected_balance_prox_mes:.1f} dias", delta="Falta de Capacidade!", delta_color="inverse")
            
    st.divider()
    
    # --- SECÇÃO 2: GRÁFICO ANUAL (CAPACITY VS FORECAST) ---
    st.markdown("### 📈 Expected Capacity vs Delivery (Visão Anual)")
    
    # Criar lista de cores (Azul para todos, Verde para o mês de foco)
    cores_barras = ['#1F4E78'] * 12
    cores_barras[mes_foco_idx] = '#00CC96' # Cor de destaque
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_cap_anual['Mês'], 
        y=df_cap_anual['Expected Capacity'],
        name='Expected Capacity',
        marker_color=cores_barras,
        text=df_cap_anual['Expected Capacity'],
        textposition='auto'
    ))
    fig.add_trace(go.Scatter(
        x=df_cap_anual['Mês'], 
        y=df_cap_anual['Expected Delivery (Forecast)'],
        name='Expected Delivery (Procura)',
        mode='lines+markers',
        line=dict(color='red', width=3, dash='dot'),
        marker=dict(size=8)
    ))
    fig.update_layout(barmode='group', xaxis_title="Mês", yaxis_title="Dias Úteis")
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # --- SECÇÃO 3: SAÚDE DOS CLIENTES E CONTRATOS ---
    st.markdown("### 🏥 Saúde dos Clientes e Estado dos Contratos")
    
    colA, colB = st.columns([1, 2])
    
    with colA:
        st.markdown("**Distribuição de Esforço (Próximo Mês)**")
        fig_pie = px.pie(df_master, values='Forecast_Mensal_Dias', names='Cliente', hole=0.4)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with colB:
        st.markdown("**Visão Detalhada de Saldos**")
        # Alertas de Risco
        contratos_em_risco = df_master[df_master['Saldo_Expected_Prox_Mes'] <= 10]
        if not contratos_em_risco.empty:
            for idx, row in contratos_em_risco.iterrows():
                st.warning(f"**Alerta:** {row['Cliente']} ({row['Nome_do_Servico']}) | Saldo no fim do próximo mês será **{row['Saldo_Expected_Prox_Mes']:.1f} dias**.")
        
        # Tabela
        st.dataframe(df_master[['Cliente', 'Nome_do_Servico', 'Data_Fim', 'Total_Ja_Gasto', 'Forecast_Mensal_Dias', 'Saldo_Expected_Prox_Mes']].style.format({'Total_Ja_Gasto': "{:.1f}", 'Forecast_Mensal_Dias': "{:.1f}", 'Saldo_Expected_Prox_Mes': "{:.1f}"}), use_container_width=True)

else:
    st.info("Por favor, faça o upload do seu ficheiro Excel na barra lateral para inicializar o painel.")
