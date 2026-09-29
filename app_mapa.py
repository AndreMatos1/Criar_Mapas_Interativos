import copy
import json
import os
import unicodedata
from pathlib import Path
from urllib.parse import quote

import folium
import pandas as pd
import streamlit as st
from branca.element import MacroElement, Template
from folium import FeatureGroup, GeoJsonTooltip
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

APP_DIR = Path(__file__).resolve().parent


@st.cache_data
def load_brazil_states():
    with (APP_DIR / 'data' / 'estados_brasil.geojson').open(encoding='utf-8') as source:
        return json.load(source)

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

FOOTER_HTML = """
<hr style="margin-top: 50px;">
<div style="text-align: center; font-size: 12px; color: gray;">
    Developed by André Matos
</div>
"""


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


def render_footer():
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def load_geojson_for_states(selected_states):
    combined_features = []
    missing_states = []

    for uf in selected_states:
        json_path = APP_DIR / 'Json_Polígonos_Geom_Cidades_Brasil' / f'limites_mun_{uf}.json'
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

    render_footer()

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

    estados_brasil = load_brazil_states()
    # Mapa geográfico completo, inclusive fora das UFs presentes na planilha.
    mapa = folium.Map(
        location=[-14.2, -51.9], zoom_start=4, tiles=None,
        background_color='#f8fafc',
    )
    osm_layer = folium.TileLayer(
        tiles='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name='OpenStreetMap.Mapnik', max_zoom=19,
        overlay=False, control=True, show=True,
        referrer_policy='strict-origin-when-cross-origin',
    ).add_to(mapa)
    esri_layer = folium.TileLayer(
        tiles='Esri.WorldTopoMap', name='Mapa geográfico Esri (alternativa)',
        overlay=False, control=True, show=False,
    ).add_to(mapa)
    # file:// não envia Referer HTTP. Iframes srcdoc podem herdar a origem da página.
    basemap_start = MacroElement()
    basemap_start._template = Template('''
        {% macro script(this, kwargs) %}
        var hasWebOrigin = /^https?:$/.test(window.location.protocol) ||
            (window.location.protocol === 'about:' && /^https?:\\/\\//.test(document.referrer));
        if (hasWebOrigin) {
            {{ this.osm }}.addTo({{ this.map_name }});
        } else {
            {{ this.esri }}.addTo({{ this.map_name }});
            {{ this.map_name }}.removeLayer({{ this.osm }});
        }
        {% endmacro %}
    ''')
    basemap_start.osm = osm_layer.get_name()
    basemap_start.esri = esri_layer.get_name()
    basemap_start.map_name = mapa.get_name()
    carto_api_key = os.environ.get('CARTO_API_KEY', '').strip()
    if carto_api_key:
        folium.TileLayer(
            tiles=(
                'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
                f'?key={quote(carto_api_key, safe="")}'
            ),
            attr=(
                '&copy; <a href="https://www.openstreetmap.org/copyright">'
                'OpenStreetMap</a> contributors &copy; '
                '<a href="https://carto.com/attributions">CARTO</a>'
            ),
            name='Mapa base CARTO',
            overlay=False,
            control=True,
            show=False,
        ).add_to(mapa)
    Fullscreen(position='topright').add_to(mapa)

    # Divisas acima das regiões, sem cobrir o mapa geográfico nem os tooltips.
    folium.map.CustomPane('divisas_estaduais', z_index=450, pointer_events=False).add_to(mapa)

    estado_layer = FeatureGroup(name='Limites municipais das UFs da planilha', show=True)
    folium.GeoJson(
        municipios_geojson,
        style_function=lambda x: {
            'fill': False,
            'color': '#1f2937',
            'weight': 0.35,
        },
    ).add_to(estado_layer)
    estado_layer.add_to(mapa)

    st.caption("Você pode expandir o mapa para melhor visualização ou baixar o arquivo em html.")

    # Evita cores muito claras (ex.: branco) que podem parecer "tarja" ao abrir o HTML fora do Streamlit.
    colors = [
        '#0066CC', '#009900', '#FFA95B', '#68D668', '#AB87CB', '#8B0000', '#FF6347',
        '#00008B', '#006400', '#5F9EA0', '#4B0082', '#C71585', '#20B2AA',
        '#CD5C5C', '#2E8B57', '#4169E1', '#708090', '#2F4F4F', '#8A2BE2',
    ]
    mesorregioes = df['Região'].unique()
    color_map = {meso: colors[i % len(colors)] for i, meso in enumerate(mesorregioes)}
    meso_layers = {meso: FeatureGroup(name=meso, show=True) for meso in mesorregioes}

    for feature in features:
        municipio_normalizado = feature['properties'].get('name_normalized', '')
        municipio_uf = feature['properties'].get('uf')
        row = df[(df['Cidade_normalizada'] == municipio_normalizado) & (df['UF'] == municipio_uf)]

        if not row.empty:
            mesorregiao = row['Região'].values[0]
            color = color_map[mesorregiao]
        
            # adiciona a região no geojson
            feature['properties']['regiao'] = mesorregiao
        
            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': '#6b7280',
                    'weight': 0.35,
                    'fillOpacity':0.6,
                },
                tooltip=GeoJsonTooltip(
                    fields=['name', 'uf', 'regiao'],
                    aliases=['Cidade:', 'UF:', 'Região:']
                ),
        ).add_to(meso_layers[mesorregiao])

    for _, layer in meso_layers.items():
        layer.add_to(mapa)

    divisas_layer = folium.GeoJson(
        estados_brasil, name='Divisas estaduais',
        pane='divisas_estaduais', interactive=False,
        style_function=lambda x: {
            'fill': False,
            'color': '#1d4ed8' if x['properties']['uf'] in estados_detectados else '#64748b',
            'weight': 3.5 if x['properties']['uf'] in estados_detectados else 1.2,
            'opacity': 1,
        },
    ).add_to(mapa)
    mapa.fit_bounds(divisas_layer.get_bounds(), padding=(15, 15))
    st.caption('Mapa completo ao fundo. UFs da planilha destacadas com borda azul espessa; '
               'municípios coloridos por região. As demais UFs permanecem no mapa, '
               'com divisas discretas. Use o controle de camadas para ocultar ou exibir regiões.')
    st.caption('OpenStreetMap.Mapnik é o fundo padrão em páginas web. No HTML aberto por '
               'duplo clique, o mapa Esri é usado automaticamente para evitar bloqueios de origem.')

    folium.LayerControl(collapsed=True).add_to(mapa)
    # A seleção por origem pertence somente ao HTML exportado. No aplicativo,
    # o componente st_folium é servido por HTTP e inicia explicitamente em Mapnik.
    export_map = copy.deepcopy(mapa)
    export_map._children[osm_layer.get_name()].show = False
    basemap_start.add_to(export_map)
    st_folium(mapa, height=500, use_container_width=True, returned_objects=[])

    html_file = "mapa_interativo.html"
    export_map.save(html_file)

    with open(html_file, 'rb') as f:
        st.download_button("Baixar Mapa em HTML", f, file_name=html_file, mime="text/html")

    render_footer()
