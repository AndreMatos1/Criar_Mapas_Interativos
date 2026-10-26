"""Um único explorador, usado na prévia Streamlit e no HTML exportado."""

import json
import os
from pathlib import Path
from urllib.parse import quote

import folium
from branca.element import Element, MacroElement, Template


ASSETS = Path(__file__).parent / 'assets'


def json_seguro(value):
    # Dados da planilha nunca podem encerrar a tag script ou inserir HTML.
    return (json.dumps(value, ensure_ascii=False, allow_nan=False)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))


def criar_mapa(municipios, estados, tem_pdvs=False, titulo='Mapa de territórios', apresentacao=False,
               contexto_municipal=None):
    mapa = folium.Map(location=[-14.2, -51.9], zoom_start=4, tiles=None,
                       zoom_control=False, prefer_canvas=True, control_scale=True,
                       background_color='#f3f6f7')
    # Leaflet acompanha o HTML; o modo territorial não depende de CDNs.
    # Bootstrap, jQuery e AwesomeMarkers não são usados por este explorador.
    mapa.default_js = []
    mapa.default_css = []
    vendor = ASSETS / 'vendor' / 'leaflet'
    mapa.get_root().header.add_child(Element('<!-- Leaflet 1.9.4\n' + (vendor / 'LICENSE').read_text() + '\n-->'))
    mapa.get_root().header.add_child(Element('<style>' + (vendor / 'leaflet.css').read_text() + '</style>'))
    mapa.get_root().header.add_child(Element('<script>' + (vendor / 'leaflet.js').read_text() + '</script>'))
    # As camadas só são carregadas se o usuário escolher a visão geográfica.
    osm = folium.TileLayer(
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png', name='OpenStreetMap.Mapnik',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        max_zoom=19, show=False, control=False,
        referrer_policy='strict-origin-when-cross-origin',
    ).add_to(mapa)
    esri = folium.TileLayer('Esri.WorldTopoMap', name='Mapa geográfico Esri (alternativa)',
                            show=False, control=False).add_to(mapa)
    carto = None
    key = os.environ.get('CARTO_API_KEY', '').strip()
    if key:
        carto = folium.TileLayer(
            'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png?key=' + quote(key, safe=''),
            name='Mapa base CARTO', show=False, control=False,
            attr='&copy; OpenStreetMap contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        ).add_to(mapa)

    ui = MacroElement()
    # O template é estático; textos fornecidos pelo usuário só entram como JSON.
    ui._template = Template('''
      {% macro header(this, kwargs) %}<style>{{ this.css }}</style>{% endmacro %}
      {% macro html(this, kwargs) %}{{ this.html }}{% endmacro %}
      {% macro script(this, kwargs) %}
        (function() {
          const map = {{ this.map_name }};
          const basemaps = {osm: {{ this.osm }}, esri: {{ this.esri }}, carto: {{ this.carto }}};
          const features = {{ this.features }};
          const states = {{ this.states }};
          const municipalContext = {{ this.contexto }};
          const config = {{ this.config }};
          {{ this.js }}
        })();
      {% endmacro %}
    ''')
    ui.css = (ASSETS / 'explorador.css').read_text(encoding='utf-8')
    ui.html = (ASSETS / 'explorador.html').read_text(encoding='utf-8')
    ui.js = (ASSETS / 'explorador.js').read_text(encoding='utf-8')
    ui.map_name = mapa.get_name()
    ui.osm, ui.esri = osm.get_name(), esri.get_name()
    ui.carto = carto.get_name() if carto else 'null'
    ui.features, ui.states = json_seguro(municipios), json_seguro(estados)
    ids = {str(f['properties']['id']) for f in municipios['features']}
    # As cidades já coloridas não precisam ser incorporadas duas vezes.
    contexto = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {}, 'geometry': f['geometry']}
        for f in (contexto_municipal or {}).get('features', [])
        if str(f['properties'].get('id')) not in ids
    ]}
    ui.contexto = json_seguro(contexto)
    ui.config = json_seguro({'temPdvs': tem_pdvs, 'titulo': titulo, 'apresentacao': apresentacao})
    ui.add_to(mapa)
    return mapa


def exportar_html(mapa):
    """Sem arquivo compartilhado no disco entre sessões do Streamlit."""
    return mapa.get_root().render()
