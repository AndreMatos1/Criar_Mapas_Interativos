import json
import os

import folium
import pandas as pd
import streamlit as st
from folium import FeatureGroup, GeoJsonTooltip
from folium.plugins import Fullscreen
from streamlit_folium import folium_static


# Função para calcular a média das coordenadas de um município (polígono)
def calculate_mean_coordinates(coordinates):
    if isinstance(coordinates[0][0], list):
        coordinates = coordinates[0]
    mean_lat = sum(coord[1] for coord in coordinates) / len(coordinates)
    mean_lon = sum(coord[0] for coord in coordinates) / len(coordinates)
    return mean_lat, mean_lon


def load_geojson_for_states(selected_states):
    combined_features = []
    missing_states = []

    for uf in selected_states:
        json_path = f"Json_Polígonos_Geom_Cidades_Brasil/limites_mun_{uf}.json"
        if not os.path.exists(json_path):
            missing_states.append(uf)
            continue

        with open(json_path, 'r', encoding='utf-8') as json_file:
            geojson_data = json.load(json_file)
            for feature in geojson_data.get('features', []):
                feature.setdefault('properties', {})['uf'] = uf
                combined_features.append(feature)

    return {
        'type': 'FeatureCollection',
        'features': combined_features
    }, missing_states


# Configuração do Streamlit
st.set_page_config(page_title="Criar Mapas Interativos", page_icon="🌍")
st.title("Mapa de Cidades por Estado")

# Inicializar estado de sessão para controlar exibição
if "files_loaded" not in st.session_state:
    st.session_state["files_loaded"] = False

# Verificar se os arquivos foram carregados e redirecionar para a tela do mapa
if not st.session_state["files_loaded"]:
    excel_file = st.file_uploader(
        "Carregar arquivo Excel com as colunas Cidade, Região e UF.",
        type=["xlsx"],
    )

    if excel_file is not None:
        df = pd.read_excel(excel_file)
        df.columns = df.columns.str.strip()

        required_columns = {"Cidade", "Região", "UF"}
        missing_columns = required_columns - set(df.columns)

        if missing_columns:
            st.error(
                "As seguintes colunas obrigatórias não foram encontradas: "
                f"{', '.join(sorted(missing_columns))}."
            )
        else:
            df['Cidade'] = df['Cidade'].astype(str).str.lower().str.strip()
            df['UF'] = df['UF'].astype(str).str.upper().str.strip()
            df['Região'] = df['Região'].astype(str).str.strip()

            estados_detectados = sorted(df['UF'].dropna().unique().tolist())
            municipios_geojson, missing_states = load_geojson_for_states(estados_detectados)

            if missing_states:
                st.error(f"Arquivo JSON não encontrado para: {', '.join(missing_states)}")
            elif not municipios_geojson['features']:
                st.error("Nenhum município foi carregado para as UFs da planilha.")
            else:
                st.session_state['df'] = df
                st.session_state['municipios_geojson'] = municipios_geojson
                st.session_state['estados_detectados'] = estados_detectados
                st.session_state["files_loaded"] = True
                st.success(
                    f"Arquivo {excel_file.name} carregado com sucesso! "
                    f"UFs identificadas: {', '.join(estados_detectados)}"
                )
                st.rerun()

    # Nota de rodapé no Streamlit
    st.markdown(
        """
        <hr style="margin-top: 50px;">
        <div style="text-align: center; font-size: 12px; color: gray;">
            Developed by André Matos
        </div>
        """,
        unsafe_allow_html=True,
    )

# Exibir o mapa apenas se os arquivos foram carregados
if st.session_state["files_loaded"]:
    df = st.session_state['df']
    municipios_geojson = st.session_state['municipios_geojson']
    estados_detectados = st.session_state.get('estados_detectados', [])

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

    estado_layer = FeatureGroup(name='Contorno dos estados da planilha', show=True)
    folium.GeoJson(
        municipios_geojson,
        style_function=lambda x: {
            'fillColor': 'lightgray',
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.2,
        },
    ).add_to(estado_layer)
    estado_layer.add_to(mapa)

    colors = [
        '#0066CC', '#009900', '#FFA95B', '#68D668', '#AB87CB', '#8b0000', '#ff6347',
        '#f5deb3', '#00008b', '#006400', '#5f9ea0', '#4b0082', '#ffffff',
        '#ffc0cb', '#87cefa', '#90ee90', '#808080', '#000000', '#d3d3d3',
    ]
    mesorregioes = df['Região'].unique()
    color_map = {meso: colors[i % len(colors)] for i, meso in enumerate(mesorregioes)}
    meso_layers = {meso: FeatureGroup(name=meso, show=False) for meso in mesorregioes}

    for feature in municipios_geojson['features']:
        municipio_nome = feature['properties']['name'].lower()
        municipio_uf = feature['properties'].get('uf')

        row = df[(df['Cidade'] == municipio_nome) & (df['UF'] == municipio_uf)]

        if not row.empty:
            mesorregiao = row['Região'].values[0]
            color = color_map[mesorregiao]

            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 0.5,
                    'fillOpacity': 0.6,
                },
                tooltip=GeoJsonTooltip(fields=['name', 'uf'], aliases=['Cidade:', 'UF:']),
            ).add_to(meso_layers[mesorregiao])

    for _, layer in meso_layers.items():
        layer.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)
    folium_static(mapa)

    if estados_detectados:
        st.caption(f"UFs identificadas automaticamente na planilha: {', '.join(estados_detectados)}")

    # Salvar o mapa como um arquivo HTML
    html_file = "mapa_interativo.html"
    mapa.save(html_file)

    # Botão para download do arquivo HTML
    with open(html_file, 'rb') as f:
        st.download_button("Baixar Mapa em HTML", f, file_name=html_file, mime="text/html")

    # Nota de rodapé no Streamlit
    st.markdown(
        """
        <hr style="margin-top: 50px;">
        <div style="text-align: center; font-size: 12px; color: gray;">
            Developed by André Matos
        </div>
        """,
        unsafe_allow_html=True,
    )
