import json
import os
import unicodedata

import folium
import pandas as pd
import streamlit as st
from folium import FeatureGroup, GeoJsonTooltip
from folium.plugins import Fullscreen
from streamlit_folium import folium_static

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def normalize_text(value):
    text = str(value).strip().lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in text if not unicodedata.combining(char))


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
                feature['properties']['name_normalized'] = normalize_text(feature['properties'].get('name', ''))
                combined_features.append(feature)

    return {
        'type': 'FeatureCollection',
        'features': combined_features,
    }, missing_states


# Configuração do Streamlit
st.set_page_config(page_title="Criar Mapas Interativos", page_icon="🌍")
st.title("Mapa de Cidades por Estado")

if "files_loaded" not in st.session_state:
    st.session_state["files_loaded"] = False

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
            df['Cidade'] = df['Cidade'].fillna('').astype(str).str.strip()
            df['UF'] = df['UF'].fillna('').astype(str).str.upper().str.strip()
            df['Região'] = df['Região'].fillna('').astype(str).str.strip()
            df['Cidade_normalizada'] = df['Cidade'].apply(normalize_text)

            invalid_ufs = sorted([uf for uf in df['UF'].unique().tolist() if uf and uf not in UF_VALIDAS])
            if invalid_ufs:
                st.warning(f"UF(s) inválida(s) ignorada(s): {', '.join(invalid_ufs)}")

            df = df[df['UF'].isin(UF_VALIDAS) & (df['Cidade_normalizada'] != '')]
            estados_detectados = sorted(df['UF'].unique().tolist())

            if not estados_detectados:
                st.error("Nenhuma UF válida encontrada na planilha.")
            else:
                municipios_geojson, missing_states = load_geojson_for_states(estados_detectados)

                if missing_states:
                    st.warning(f"Arquivo JSON não encontrado para: {', '.join(missing_states)}")

                if not municipios_geojson['features']:
                    st.error("Nenhum município foi carregado para as UFs da planilha.")
                else:
                    st.session_state['df'] = df
                    st.session_state['municipios_geojson'] = municipios_geojson
                    st.session_state['estados_detectados'] = estados_detectados
                    st.session_state["files_loaded"] = True
                    st.rerun()

    st.markdown(
        """
        <hr style="margin-top: 50px;">
        <div style="text-align: center; font-size: 12px; color: gray;">
            Developed by André Matos
        </div>
        """,
        unsafe_allow_html=True,
    )

if st.session_state["files_loaded"]:
    df = st.session_state['df']
    municipios_geojson = st.session_state['municipios_geojson']
    estados_detectados = st.session_state.get('estados_detectados', [])

    st.success(f"Arquivo carregado. UFs identificadas automaticamente: {', '.join(estados_detectados)}")

    if st.button("Carregar novo arquivo"):
        for key in ['files_loaded', 'df', 'municipios_geojson', 'estados_detectados']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    features = municipios_geojson['features']
    if not features:
        st.error("Sem feições geográficas para renderizar o mapa.")
        st.stop()

    municipio_coords = []
    for feature in features:
        coordinates = feature['geometry']['coordinates']
        mean_lat, mean_lon = calculate_mean_coordinates(coordinates)
        municipio_coords.append((mean_lat, mean_lon))

    mean_lat = sum(coord[0] for coord in municipio_coords) / len(municipio_coords)
    mean_lon = sum(coord[1] for coord in municipio_coords) / len(municipio_coords)

    mapa = folium.Map(location=[mean_lat, mean_lon], zoom_start=6)
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

    for feature in features:
        municipio_normalizado = feature['properties'].get('name_normalized', '')
        municipio_uf = feature['properties'].get('uf')
        row = df[(df['Cidade_normalizada'] == municipio_normalizado) & (df['UF'] == municipio_uf)]

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

    html_file = "mapa_interativo.html"
    mapa.save(html_file)

    with open(html_file, 'rb') as f:
        st.download_button("Baixar Mapa em HTML", f, file_name=html_file, mime="text/html")

    st.markdown(
        """
        <hr style="margin-top: 50px;">
        <div style="text-align: center; font-size: 12px; color: gray;">
            Developed by André Matos
        </div>
        """,
        unsafe_allow_html=True,
    )
