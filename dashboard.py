import dash
from dash import dcc, html, dash_table
import plotly.express as px
import pandas as pd
import pyodbc
import logging
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    filename='logs/dashboard.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Função para converter horas decimais em HH:mm
def format_duration(hours):
    if pd.isna(hours) or hours < 0:
        return "00:00"
    total_seconds = int(hours * 3600)
    hours_part = total_seconds // 3600
    minutes_part = (total_seconds % 3600) // 60
    return f"{hours_part:02d}:{minutes_part:02d}"

# Função para conectar e buscar dados com pyodbc
def fetch_data():
    try:
        logging.info("Tentando conectar ao SQL Server com pyodbc...")
        conn = pyodbc.connect(
            'DRIVER={SQL Server};'
            'SERVER=192.168.55.168;'
            'DATABASE=DBTeste;'
            'UID=sa;'
            'PWD=Alpha@2024;'
            'Encrypt=optional;'
        )
        query = """
            SELECT DataInicial, DataFinal, TAG, Tipo, Falha, Descrição, Horímetro, Operador
            FROM TabelaManutencao
            ORDER BY TAG, DataInicial
        """
        df = pd.read_sql(query, conn)
        conn.close()

        df['DataInicial'] = pd.to_datetime(df['DataInicial'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df['DataFinal'] = pd.to_datetime(df['DataFinal'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df['DataInicial'] = df['DataInicial'].replace('-', pd.NaT)
        df['DataFinal'] = df['DataFinal'].replace('-', pd.NaT)
        df['Descrição'] = df['Descrição'].fillna('').replace('-', '')
        df = df.sort_values(by=['TAG', 'DataInicial']).reset_index(drop=True)
        
        df_processed = df.copy()
        i = 0
        while i < len(df_processed) - 1:
            current_row = df_processed.iloc[i]
            next_row = df_processed.iloc[i + 1]
            if (pd.isna(current_row['DataFinal']) or current_row['DataFinal'] == '-') and \
               current_row['TAG'] == next_row['TAG'] and \
               (pd.isna(next_row['DataInicial']) or next_row['DataInicial'] == '-'):
                df_processed.at[i, 'DataFinal'] = next_row['DataFinal']
                df_processed.at[i, 'Descrição'] = f"{current_row['Descrição']} | {next_row['Descrição']}"
                df_processed = df_processed.drop(i + 1).reset_index(drop=True)
            else:
                i += 1
        
        df_processed['DuracaoHoras'] = (df_processed['DataFinal'] - df_processed['DataInicial']).dt.total_seconds() / 3600
        df_processed['DuracaoHoras'] = df_processed['DuracaoHoras'].fillna(0)
        df_processed['Horímetro'] = pd.to_numeric(df_processed['Horímetro'], errors='coerce')
        df_processed['Falha'] = df_processed['Falha'].fillna('Sem Falha').replace('', 'Sem Falha')
        df_processed['DataInicial'] = df_processed['DataInicial'].dt.strftime('%d-%m-%Y')
        df_processed['DataFinal'] = df_processed['DataFinal'].dt.strftime('%d-%m-%Y')
        
        df_processed = df_processed.rename(columns={
            'DataInicial': 'Início da Manutenção',
            'DataFinal': 'Fim da Manutenção',
            'TAG': 'TAG',
            'Tipo': 'Tipo',
            'Falha': 'Falha',
            'Descrição': 'Descrição',
            'Horímetro': 'Horímetro',
            'Operador': 'Operador',
            'DuracaoHoras': 'Duração da Manutenção'
        })
        df_processed['Duração da Manutenção'] = df_processed['Duração da Manutenção'].apply(format_duration)
        
        logging.info("Dados buscados e processados com sucesso")
        return df_processed
    except Exception as e:
        logging.error(f"Erro ao buscar dados: {str(e)}")
        return pd.DataFrame()

# Inicialização do aplicativo Dash
app = dash.Dash(__name__)

# Paleta de cores
CINZA_ESCURO = '#4B4B4B'
VERMELHO_ESCURO = '#8B0000'
VERMELHO_VIVO = '#FF4040'
CINZA_CLARO = '#D3D3D3'

# Estilo base
BASE_STYLE = {
    'backgroundColor': CINZA_ESCURO,
    'color': 'white',
    'fontFamily': 'Arial',
    'padding': '20px',
}

# Função para calcular KPIs
def calculate_kpis(df):
    if df.empty:
        return {"mttr": 0, "perc_falhas": 0, "horas_totais": 0, "horimetro_medio": 0}
    df_numeric = df.copy()
    df_numeric['Duração da Manutenção'] = df_numeric['Duração da Manutenção'].apply(
        lambda x: sum(int(i) * 60 ** (1 - idx) for idx, i in enumerate(x.split(':'))) / 60
    )
    mttr = df_numeric['Duração da Manutenção'].mean()
    perc_falhas = (df_numeric['Falha'] != 'Sem Falha').sum() / len(df_numeric) * 100
    horas_totais = df_numeric['Duração da Manutenção'].sum()
    horimetro_medio = df_numeric['Horímetro'].mean()
    return {
        "mttr": round(mttr, 2),
        "perc_falhas": round(perc_falhas, 2),
        "horas_totais": round(horas_totais, 2),
        "horimetro_medio": round(horimetro_medio, 2) if not pd.isna(horimetro_medio) else 0
    }

# Função para atualizar o dashboard
def update_dashboard():
    df = fetch_data()
    
    if df.empty:
        return html.Div([
            html.H1("Erro ao Conectar ao Banco de Dados", style={'color': VERMELHO_ESCURO, 'textAlign': 'center'}),
            html.P("Não foi possível acessar a tabela 'TabelaManutencao' no banco 'DBTeste'. Verifique o log para detalhes.", 
                   style={'color': CINZA_CLARO, 'textAlign': 'center'})
        ], style=BASE_STYLE)
    
    kpis = calculate_kpis(df)
    
    # Gráfico de barras
    fig_bar = px.bar(df, x="Tipo", title="Manutenções por Tipo",
                     color_discrete_sequence=[VERMELHO_ESCURO])
    fig_bar.update_layout(
        plot_bgcolor=CINZA_ESCURO, 
        paper_bgcolor=CINZA_ESCURO, 
        font_color=CINZA_CLARO,
        yaxis_title="Quantidade",
        title_font=dict(size=20, family='Arial', color=CINZA_CLARO),
        title=dict(text="<b>Manutenções por Tipo</b>")
    )

    # Gráfico de linhas
    fig_line = px.line(df.dropna(subset=['Início da Manutenção', 'Duração da Manutenção']), 
                       x="Início da Manutenção", y="Duração da Manutenção", color="TAG",
                       title="Duração de Manutenção ao Longo do Tempo")
    fig_line.update_layout(
        plot_bgcolor=CINZA_ESCURO, 
        paper_bgcolor=CINZA_ESCURO, 
        font_color=CINZA_CLARO,
        title_font=dict(size=20, family='Arial', color=CINZA_CLARO),
        title=dict(text="<b>Duração de Manutenção ao Longo do Tempo</b>")
    )

    # Gráfico de pizza
    falha_counts = df['Falha'].value_counts().reset_index()
    falha_counts.columns = ['Falha', 'Contagem']
    fig_pie = px.pie(falha_counts, names='Falha', values='Contagem', title="Distribuição de Tipos de Falha",
                     color_discrete_sequence=[VERMELHO_ESCURO, CINZA_CLARO, VERMELHO_VIVO])
    fig_pie.update_layout(
        plot_bgcolor=CINZA_ESCURO, 
        paper_bgcolor=CINZA_ESCURO, 
        font_color=CINZA_CLARO,
        title_font=dict(size=20, family='Arial', color=CINZA_CLARO),
        title=dict(text="<b>Distribuição de Tipos de Falha</b>")
    )

    # Tabela interativa
    table = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df.columns],
        style_table={'overflowX': 'auto', 'border': f'1px solid {CINZA_CLARO}', 'borderRadius': '10px'},
        style_cell={
            'textAlign': 'center',
            'backgroundColor': CINZA_ESCURO, 
            'color': CINZA_CLARO, 
            'border': f'1px solid {CINZA_CLARO}'
        },
        style_header={
            'backgroundColor': VERMELHO_ESCURO, 
            'fontWeight': 'bold', 
            'color': 'white', 
            'border': f'1px solid {CINZA_CLARO}',
            'textAlign': 'center'
        },
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#5A5A5A'}]
    )

    # Layout do dashboard
    return html.Div([
        html.H1("Histórico de Manutenção", 
                style={'color': VERMELHO_VIVO, 'textAlign': 'center', 'marginBottom': '10px'}),
        html.H3(f"Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                style={'color': CINZA_CLARO, 'textAlign': 'center', 'fontSize': '14px'}),

        # KPIs em caixas modernas com títulos em negrito usando Markdown
        html.Div([
            html.Div([
                dcc.Markdown("**Tempo Médio de Reparo**", style={'fontSize': '14px', 'color': CINZA_CLARO}),
                html.H4(f"{kpis['mttr']} horas", style={'color': VERMELHO_VIVO, 'margin': '0'})
            ], style={'backgroundColor': '#5A5A5A', 'padding': '15px', 'border': f'2px solid {CINZA_CLARO}', 'borderRadius': '10px', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),
            html.Div([
                dcc.Markdown("**Manutenções com Falha**", style={'fontSize': '14px', 'color': CINZA_CLARO}),
                html.H4(f"{kpis['perc_falhas']}%", style={'color': VERMELHO_VIVO, 'margin': '0'})
            ], style={'backgroundColor': '#5A5A5A', 'padding': '15px', 'border': f'2px solid {CINZA_CLARO}', 'borderRadius': '10px', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),
            html.Div([
                dcc.Markdown("**Horas Totais de Manutenção**", style={'fontSize': '14px', 'color': CINZA_CLARO}),
                html.H4(f"{kpis['horas_totais']} horas", style={'color': VERMELHO_VIVO, 'margin': '0'})
            ], style={'backgroundColor': '#5A5A5A', 'padding': '15px', 'border': f'2px solid {CINZA_CLARO}', 'borderRadius': '10px', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),
            html.Div([
                dcc.Markdown("**Horímetro Médio**", style={'fontSize': '14px', 'color': CINZA_CLARO}),
                html.H4(f"{kpis['horimetro_medio']}", style={'color': VERMELHO_VIVO, 'margin': '0'})
            ], style={'backgroundColor': '#5A5A5A', 'padding': '15px', 'border': f'2px solid {CINZA_CLARO}', 'borderRadius': '10px', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '30px'}),

        # Gráficos com bordas
        html.Div(dcc.Graph(figure=fig_bar), style={'border': f'1px solid {CINZA_CLARO}', 'borderRadius': '10px', 'marginBottom': '20px'}),
        html.Div(dcc.Graph(figure=fig_line), style={'border': f'1px solid {CINZA_CLARO}', 'borderRadius': '10px', 'marginBottom': '20px'}),
        html.Div(dcc.Graph(figure=fig_pie), style={'border': f'1px solid {CINZA_CLARO}', 'borderRadius': '10px', 'marginBottom': '20px'}),

        # Tabela
        html.H3("Histórico Completo", style={'color': VERMELHO_VIVO, 'textAlign': 'center', 'marginBottom': '15px'}),
        table,

        # Intervalo de atualização
        dcc.Interval(id='interval-component', interval=10*1000, n_intervals=0)
    ], style=BASE_STYLE)

# Callback para atualização automática
@app.callback(
    dash.dependencies.Output('page-content', 'children'),
    [dash.dependencies.Input('interval-component', 'n_intervals')]
)
def refresh_dashboard(n):
    return update_dashboard()

# Configuração inicial do layout
app.layout = html.Div(id='page-content', children=update_dashboard())

# Rodar o servidor
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)