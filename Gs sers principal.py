import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys

PRECO_KWH_COMPRADO = 0.80
PRECO_KWH_CREDITO = 0.80
FATOR_EMISSAO_CO2_KG_POR_KWH = 0.2
ARQUIVO_GERACAO = 'dados/geracao_solar_pvgis.csv'
ARQUIVO_GRAFICO = 'resultado_dia_pico.png'

print("Iniciando análise...")

print("Passo 1: Gerando dados simulados de consumo para 2023...")
try:
    datas = pd.date_range(start='2023-01-01 00:00',
                          end='2023-12-31 23:00', freq='H')
    df_consumo = pd.DataFrame(datas, columns=['timestamp'])

    consumo_base = 2
    pico_dia_normal = 15
    pico_dia_hibrido = 5

    df_consumo['dia_semana'] = df_consumo['timestamp'].dt.dayofweek
    df_consumo['hora'] = df_consumo['timestamp'].dt.hour

    def calcular_consumo(row):
        consumo = consumo_base
        if row['dia_semana'] in [1, 2, 3] and (row['hora'] >= 8 and row['hora'] <= 18):
            consumo = pico_dia_normal
        elif row['dia_semana'] in [0, 4] and (row['hora'] >= 8 and row['hora'] <= 18):
            consumo = pico_dia_hibrido
        elif row['dia_semana'] in [5, 6]:
            consumo = consumo_base
        ruido = np.random.normal(0, 0.5)
        return max(0, consumo + ruido)

    df_consumo['consumo_kwh'] = df_consumo.apply(calcular_consumo, axis=1)
    # Seleciona colunas finais
    df_consumo = df_consumo[['timestamp', 'consumo_kwh']]
    print("Dados de consumo gerados com sucesso.")
except Exception as e:
    print(f"Erro ao gerar dados de consumo: {e}")
    sys.exit()


print("Passo 2: Carregando dados de geração solar...")
try:
    df_geracao = pd.read_csv(
        ARQUIVO_GERACAO,
        skiprows=10,
        skipfooter=12,
        engine='python',
        sep=',',
        usecols=['time', 'P']
    )
except FileNotFoundError:
    print(f"Erro: Arquivo {ARQUIVO_GERACAO} não encontrado.")
    print("Verifique se o nome do ficheiro está correto e na pasta 'dados/'.")
    sys.exit()
except ValueError as e:
    print(f"Erro ao ler o CSV de geração: {e}")
    print("Verifique se o ficheiro é o correto (baixado da aba 'Hourly data').")
    sys.exit()

df_geracao.rename(columns={'P': 'geracao_kwh'}, inplace=True)
df_geracao['time_limpo'] = df_geracao['time'].astype(str).str[:11]
df_geracao['timestamp'] = pd.to_datetime(
    df_geracao['time_limpo'], format='%Y%m%d:%H')
df_geracao = df_geracao[['timestamp', 'geracao_kwh']]
print("Dados de geração carregados com sucesso.")


print("Passo 3: Unindo dados de consumo e geração...")
df_completo = pd.merge(df_consumo, df_geracao, on='timestamp')

if df_completo.empty:
    print("---------------------------------------------------------------")
    print("ERRO CRÍTICO: A UNIÃO DOS DADOS FALHOU. NÃO HÁ DATAS EM COMUM.")
    print("Isto significa que os anos dos seus dados ainda não batem.")
    print(
        f"Datas do Consumo (Gerado): {df_consumo['timestamp'].min()} a {df_consumo['timestamp'].max()}")
    print(
        f"Datas da Geração (Ficheiro): {df_geracao['timestamp'].min()} a {df_geracao['timestamp'].max()}")
    print("Verifique o ano no seu ficheiro 'geracao_solar_pvgis.csv'.")
    print("---------------------------------------------------------------")
    sys.exit()

print("Dados unidos com sucesso!")

df_completo['balanco_kwh'] = df_completo['geracao_kwh'] - \
    df_completo['consumo_kwh']
df_completo['energia_comprada_kwh'] = df_completo['balanco_kwh'].apply(
    lambda x: -x if x < 0 else 0)
df_completo['energia_injetada_kwh'] = df_completo['balanco_kwh'].apply(
    lambda x: x if x > 0 else 0)

consumo_total_ano = df_completo['consumo_kwh'].sum()
geracao_total_ano = df_completo['geracao_kwh'].sum()
comprado_total_ano = df_completo['energia_comprada_kwh'].sum()
injetado_total_ano = df_completo['energia_injetada_kwh'].sum()
autoconsumo_total_ano = geracao_total_ano - injetado_total_ano

custo_sem_solar = consumo_total_ano * PRECO_KWH_COMPRADO
custo_com_solar = (comprado_total_ano * PRECO_KWH_COMPRADO) - \
    (injetado_total_ano * PRECO_KWH_CREDITO)
economia_total = custo_sem_solar - custo_com_solar

if custo_sem_solar == 0:
    economia_percentual = 0.0
    print("Aviso: Consumo total foi zero. Não é possível calcular a economia percentual.")
else:
    economia_percentual = (economia_total / custo_sem_solar) * 100

co2_evitado_kg = autoconsumo_total_ano * FATOR_EMISSAO_CO2_KG_POR_KWH

print("\n--- RESULTADOS DA ANÁLISE ANUAL ---")
print(f"Consumo Total do Escritório: {consumo_total_ano:,.0f} kWh")
print(f"Geração Solar Total:         {geracao_total_ano:,.0f} kWh")
print("-" * 30)
print(f"Energia Comprada da Rede:    {comprado_total_ano:,.0f} kWh")
print(f"Energia Injetada na Rede:    {injetado_total_ano:,.0f} kWh")
print(f"Autoconsumo Solar:           {autoconsumo_total_ano:,.0f} kWh")
print("-" * 30)
print(f"Custo ANTES da Solução Solar: R$ {custo_sem_solar:,.2f}")
print(f"Custo COM a Solução Solar:    R$ {custo_com_solar:,.2f}")
print(
    f"ECONOMIA ANUAL:               R$ {economia_total:,.2f} ({economia_percentual:.1f}%)")
print("-" * 30)
print(f"CO2 evitado: {co2_evitado_kg:,.0f} kg por ano")
print("--------------------------------------\n")


print(f"Gerando gráfico '{ARQUIVO_GRAFICO}'...")

df_completo['dia_semana'] = df_completo['timestamp'].dt.dayofweek
df_dia_pico = df_completo[
    (df_completo['timestamp'].dt.month == 4) &
    (df_completo['dia_semana'] == 2)
].copy()

df_dia_pico = df_dia_pico.head(24)

if df_dia_pico.empty:
    print("Não foi possível gerar o gráfico: Não há dados para o 'dia de pico' (Quarta-feira de Abril).")
    print("Isso pode acontecer se os dados não cobrirem esse período.")
else:
    plt.figure(figsize=(12, 7))
    plt.style.use('seaborn-v0_8-darkgrid')

    plt.plot(
        df_dia_pico['timestamp'],
        df_dia_pico['geracao_kwh'],
        label='Geração Solar (kW)',
        color='orange',
        linewidth=3
    )

    plt.fill_between(
        df_dia_pico['timestamp'],
        df_dia_pico['consumo_kwh'],
        label='Consumo Escritório (kW)',
        color='royalblue',
        alpha=0.6
    )

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=2))

    plt.title(
        'Simulação: Geração Solar vs. Consumo (Dia de Pico no Escritório)', fontsize=16)
    plt.ylabel('Potência (kW)', fontsize=12)
    plt.xlabel(
        f'Horas do Dia ({df_dia_pico["timestamp"].dt.date.iloc[0]})', fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True)
    plt.ylim(bottom=0)
    plt.tight_layout()

    plt.savefig(ARQUIVO_GRAFICO)
    print("Análise concluída e gráfico salvo!")
