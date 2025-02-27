import dash
from dash import dcc, html
import plotly.express as px
import pandas as pd
import pyodbc
import logging
from datetime import datetime

# Configuração de logging (opcional, para depuração)
logging.basicConfig(
    filename='logs/dashboard.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Função para conectar ao SQL Server e buscar dados
def fetch_data():
    try:
        conn = pyodbc.connect(
            'DRIVER={SQL Server};'
            'SERVER=192.168.55.168;'      # IP do servidor
            'DATABASE=DBTeste;'     # Substitua pelo nome real do banco
            'UID=sa;'                     # Login do SQL Server
            'PWD=Alpha@2024;'             # Senha do SQL Server
            'Encrypt=optional;'           # Criptografia opcional
        )
        query = "SELECT E3TimeStamp,TAG,Tempo FROM TabelaHorimetro"  # Substitua por sua query real
        df = pd.read_sql(query, conn)
        conn.close()
        logging.info("Dados buscados com sucesso do SQL Server")
        return df
    except Exception as e:
        logging.error(f"Erro ao buscar dados: {str(e)}")
        return pd.DataFrame()  # Retorna DataFrame vazio em caso de erro

# Inicialização do aplicativo Dash
app = dash.Dash(__name__)

# Função para atualizar o layout do dashboard
def update_dashboard():
    df = fetch_data()
    
    if df.empty:
        return html.Div("Erro ao carregar dados ou tabela vazia.")
    
    # Exemplo: Gráfico de barras (ajuste colunas conforme sua tabela)
    fig_bar = px.bar(df, x="coluna_x", y="coluna_y", title="Gráfico de Barras")
    
    # Exemplo: Gráfico de linhas (ajuste colunas conforme sua tabela)
    fig_line = px.line(df, x="coluna_x", y="coluna_y", title="Gráfico de Linhas")
    
    # Layout do dashboard
    return html.Div([
        html.H1("Dashboard Interativo - Elipse E3"),
        html.H3(f"Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
        dcc.Graph(figure=fig_bar),
        dcc.Graph(figure=fig_line),
        dcc.Interval(
            id='interval-component',
            interval=10*1000,  # Atualiza a cada 10 segundos (ajuste conforme necessário)
            n_intervals=0
        )
    ])

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
    app.run_server(host='127.0.0.1', port=8050, debug=False)