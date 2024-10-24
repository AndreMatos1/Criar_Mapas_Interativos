import pandas as pd
import folium
import json
import streamlit as st
from folium import FeatureGroup
from folium import GeoJsonTooltip
from streamlit_folium import folium_static
from folium.plugins import Fullscreen  # Importar o plugin Fullscreen

# Função para calcular a média das coordenadas de um município (polígono)
def calculate_mean_coordinates(coordinates):
    if isinstance(coordinates[0][0], list):
        coordinates = coordinates[0]
    mean_lat = sum(coord[1] for coord in coordinates) / len(coordinates)
    mean_lon = sum(coord[0] for coord in coordinates) / len(coordinates)
    return mean_lat, mean_lon

# Configuração do Streamlit
st.set_page_config(page_title="Criar Mapas Interativos", page_icon="🌍", layout="wide")
st.title("Mapa de Cidades por Estado")

# Inicializar estado de sessão para controlar exibição
if "files_loaded" not in st.session_state:
    st.session_state["files_loaded"] = False

# Verificar se os arquivos foram carregados e redirecionar para a tela do mapa
if not st.session_state["files_loaded"]:
    # Exibir campos de upload de arquivo apenas se os arquivos ainda não foram carregados
    st.write("Por favor, faça o upload do arquivo em Excel e do arquivo JSON.")

    # Carregar o arquivo Excel com as cidades geocodificadas
    excel_file = st.file_uploader("Carregar arquivo Excel com as cidades e regiões.", type=["xlsx"])
    if excel_file is not None:
        df = pd.read_excel(excel_file)
        df.columns = df.columns.str.strip()  # Remover espaços extras nos nomes das colunas

        # Verificar se a coluna 'Cidade' está presente
        if 'Cidade' not in df.columns:
            st.error("A coluna 'Cidade' não foi encontrada no arquivo Excel. Verifique se há espaços extras ou outro erro.")
        else:
            st.session_state['df'] = df  # Armazenar o DataFrame no estado da sessão
            st.success(f"Arquivo {excel_file.name} carregado com sucesso!")

    # Carregar o arquivo JSON com os limites dos municípios
    json_file = st.file_uploader("Carregar arquivo JSON da UF correspondente às cidades do arquivo Excel.", type=["json"])
    if json_file is not None:
        municipios_geojson = json.load(json_file)
        st.session_state['municipios_geojson'] = municipios_geojson  # Armazenar o GeoJSON no estado da sessão

    # Verificar se ambos os arquivos foram carregados
    if 'df' in st.session_state and 'municipios_geojson' in st.session_state:
        st.session_state["files_loaded"] = True  # Atualizar o estado para indicar que os arquivos foram carregados
        st.rerun()  # Redirecionar para atualizar a página e mostrar o mapa

# Exibir o mapa apenas se os arquivos foram carregados
if st.session_state["files_loaded"]:
    df = st.session_state['df']  # Recuperar o DataFrame do estado da sessão
    municipios_geojson = st.session_state['municipios_geojson']  # Recuperar o GeoJSON do estado da sessão

    # Converter a coluna 'Cidade' para minúsculas
    df['Cidade'] = df['Cidade'].str.lower()

    municipio_coords = []
    for feature in municipios_geojson['features']:
        coordinates = feature['geometry']['coordinates']
        mean_lat, mean_lon = calculate_mean_coordinates(coordinates)
        municipio_coords.append((mean_lat, mean_lon))

    mean_lat = sum(coord[0] for coord in municipio_coords) / len(municipio_coords)
    mean_lon = sum(coord[1] for coord in municipio_coords) / len(municipio_coords)

    mapa = folium.Map(location=[mean_lat, mean_lon], zoom_start=6)

    # Adicionar o plugin Fullscreen
    Fullscreen(position='topright').add_to(mapa)

    estado_sp_layer = FeatureGroup(name='Estado', show=True)
    folium.GeoJson(
        municipios_geojson,
        style_function=lambda x: {
            'fillColor': 'lightgray',
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.2
        }
    ).add_to(estado_sp_layer)
    estado_sp_layer.add_to(mapa)

    colors = ['#0066CC', '#009900', '#FFA95B', '#68D668', '#AB87CB', '#8b0000', '#ff6347',
              '#f5deb3', '#00008b', '#006400', '#5f9ea0', '#4b0082', '#ffffff',
              '#ffc0cb', '#87cefa', '#90ee90', '#808080', '#000000', '#d3d3d3']
    mesorregioes = df['Região'].unique()
    color_map = {meso: colors[i % len(colors)] for i, meso in enumerate(mesorregioes)}

    meso_layers = {meso: FeatureGroup(name=meso, show=False) for meso in mesorregioes}

    for feature in municipios_geojson['features']:
        municipio_nome = feature['properties']['name'].lower()
        row = df[df['Cidade'] == municipio_nome]
        if not row.empty:
            mesorregiao = row['Região'].values[0]
            color = color_map[mesorregiao]

            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 0.5,
                    'fillOpacity': 0.6
                },
                tooltip=GeoJsonTooltip(fields=['name'], aliases=['Cidade:'])
            ).add_to(meso_layers[mesorregiao])

    for meso, layer in meso_layers.items():
        layer.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)

    # Exibir o mapa
    #st.subheader("Mapa de Cidades por Regiões")
    folium_static(mapa)  # Renderiza o mapa interativo no Streamlit

    # Salvar o mapa como um arquivo HTML
    html_file = "mapa_interativo.html"
    mapa.save(html_file)

    # Botão para download do arquivo HTML
    with open(html_file, 'rb') as f:
        st.download_button("Baixar Mapa em HTML", f, file_name=html_file, mime="text/html")
