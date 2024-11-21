import pandas as pd
import folium
import json
import streamlit as st
from folium import FeatureGroup, GeoJsonTooltip
from streamlit_folium import folium_static
from folium.plugins import Fullscreen
import os

# Função para calcular a média das coordenadas de um município (polígono)
def calculate_mean_coordinates(coordinates):
    if isinstance(coordinates[0][0], list):
        coordinates = coordinates[0]
    mean_lat = sum(coord[1] for coord in coordinates) / len(coordinates)
    mean_lon = sum(coord[0] for coord in coordinates) / len(coordinates)
    return mean_lat, mean_lon

# Configuração do Streamlit
st.set_page_config(page_title="Criar Mapas Interativos", page_icon="🌍")
st.title("Mapa de Cidades por Estado")

# Inicializar estado de sessão para controlar exibição
if "files_loaded" not in st.session_state:
    st.session_state["files_loaded"] = False

# Verificar se os arquivos foram carregados e redirecionar para a tela do mapa
if not st.session_state["files_loaded"]:
    # Carregar o arquivo Excel com as cidades geocodificadas
    excel_file = st.file_uploader("Carregar arquivo Excel com as cidades e regiões.", type=["xlsx"])
    if excel_file is not None:
        df = pd.read_excel(excel_file)
        df.columns = df.columns.str.strip()

        # Verificar se a coluna 'Cidade' está presente
        if 'Cidade' not in df.columns:
            st.error("A coluna 'Cidade' não foi encontrada no arquivo Excel. Verifique se há espaços extras ou outro erro.")
        else:
            st.session_state['df'] = df
            st.success(f"Arquivo {excel_file.name} carregado com sucesso!")

    # Selecionar o estado brasileiro
    estados = ["Selecione Estado", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", 
               "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
    estado_selecionado = st.selectbox("Selecione Estado", estados)

    # Verificar se o usuário selecionou um estado válido
    if estado_selecionado != "Selecione Estado":
        json_path = f"Json_Polígonos_Geom_Cidades_Brasil/limites_mun_{estado_selecionado}.json"
        
        if os.path.exists(json_path):
            # Abrir o arquivo JSON com a codificação utf-8
            with open(json_path, 'r', encoding='utf-8') as json_file:
                municipios_geojson = json.load(json_file)
                st.session_state['municipios_geojson'] = municipios_geojson
                st.session_state["files_loaded"] = True
                st.rerun()  # Redirecionar para atualizar a página e mostrar o mapa
        else:
            st.error(f"Arquivo JSON para o estado {estado_selecionado} não encontrado.")

# Exibir o mapa apenas se os arquivos foram carregados
if st.session_state["files_loaded"]:
    df = st.session_state['df']
    municipios_geojson = st.session_state['municipios_geojson']

    # Converter a coluna 'Cidade' para minúsculas
    df['Cidade'] = df['Cidade'].str.lower()

    municipio_coords = []
    for feature in municipios_geojson['features']:
        coordinates = feature['geometry']['coordinates']
        mean_lat, mean_lon = calculate_mean_coordinates(coordinates)
        municipio_coords.append((mean_lat, mean_lon))

    mean_lat = sum(coord[0] for coord in municipio_coords) / len(municipio_coords)
    mean_lon = sum(coord[1] for coord in municipio_coords) / len(municipio_coords)

    mapa = folium.Map(location=[mean_lat, mean_lon], zoom_start=7)

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

    colors = ['#0066CC', '#009900', '#FF8211', '#EBE600', '#AB87CB', '#37C8FB', '#FF4D2F',
              '#2683B2', '#EA9AD1', '#777777', '#95951B', '#47DBEB', '#09FF09',
              '#FC8CE7', '#A3D9FB', '#5DF977', '#A1A1A1', '#007456', '#FFFF00']
    mesorregioes = df['Região'].unique()
    color_map = {meso: colors[i % len(colors)] for i, meso in enumerate(mesorregioes)}

    meso_layers = {meso: FeatureGroup(name=meso, show=True) for meso in mesorregioes}

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

    folium_static(mapa)

    # Salvar o mapa como um arquivo HTML
    html_file = "mapa_interativo.html"
    mapa.save(html_file)

    # Botão para download do arquivo HTML
    with open(html_file, 'rb') as f:
        st.download_button("Baixar Mapa em HTML", f, file_name=html_file, mime="text/html")
