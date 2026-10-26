"""Contrato do HTML exportado, fundos e estado inicial do aplicativo."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from mapas.dados import preparar_dados
from mapas.visualizacao import criar_mapa, exportar_html
from test_dados import GEO

ROOT = Path(__file__).resolve().parents[1]


class MapBackgroundTest(unittest.TestCase):
    def render_map(self, key=''):
        data, _, pdvs = preparar_dados(pd.DataFrame([
            {'Cidade': 'Abaeté', 'UF': 'MG', 'Região': 'Oeste', 'PDVs': 2},
        ]), GEO)
        states = json.loads((ROOT / 'data' / 'estados_brasil.geojson').read_text())
        with patch.dict(os.environ, {'CARTO_API_KEY': key}):
            return exportar_html(criar_mapa(data, states, pdvs))

    def test_territorial_view_does_not_activate_tile_layers_on_load(self):
        html = self.render_map()
        self.assertNotIn('cartocdn.com', html)
        self.assertEqual(html.count('L.tileLayer('), 2)
        self.assertIn('value="territorial"', html)
        self.assertNotIn('updateBasemap();', html)
        self.assertIn('geographic = false', html)

    def test_geographic_options_keep_attribution_and_file_origin_fallback(self):
        html = self.render_map()
        for required in ['OpenStreetMap.Mapnik', 'www.openstreetmap.org/copyright',
                         'World_Topo_Map/MapServer/tile/', 'window.location.protocol',
                         'document.referrer', 'strict-origin-when-cross-origin']:
            self.assertIn(required, html)
        self.assertIn("hasWebOrigin ? 'osm' : 'esri'", html)

    def test_optional_carto_key_is_encoded(self):
        html = self.render_map('example&key=value')
        self.assertIn('?key=example%26key%3Dvalue', html)
        self.assertIn('carto.com/attributions', html)
        self.assertEqual(html.count('L.tileLayer('), 3)

    def test_all_states_are_preserved_even_for_single_state_input(self):
        html = self.render_map()
        states = json.loads((ROOT / 'data' / 'estados_brasil.geojson').read_text())
        self.assertEqual(len(states['features']), 27)
        for f in states['features']:
            self.assertIn('"uf": "' + f['properties']['uf'] + '"', html)

    def test_spreadsheet_text_cannot_close_script_tag(self):
        dangerous = '</script><script>window.injected=1</script>'
        df = pd.DataFrame([{'Cidade': 'Abaeté', 'UF': 'MG', 'Região': dangerous}])
        data, _, _ = preparar_dados(df, GEO)
        html = exportar_html(criar_mapa(data, {'type': 'FeatureCollection', 'features': []}, titulo=dangerous))
        self.assertNotIn(dangerous, html)
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertIn('el.textContent = text', html)


class StreamlitAppTest(unittest.TestCase):
    def test_initial_screen_only_requests_users_file(self):
        app = AppTest.from_file(str(ROOT / 'app_mapa.py')).run(timeout=30)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertFalse(any(b.label == 'Explorar exemplo' for b in app.button))
        self.assertEqual(len(app.metric), 0)
        self.assertEqual(len(app.get('download_button')), 1)

    def test_loaded_file_starts_with_all_regions(self):
        app = AppTest.from_file(str(ROOT / 'app_mapa.py'))
        app.session_state['base_df'] = pd.DataFrame([
            {'Cidade': 'Bom Despacho', 'UF': 'MG', 'Região': 'Oeste'},
            {'Cidade': 'Piumhi', 'UF': 'MG', 'Região': 'Canastra'},
        ])
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual([m.value for m in app.metric], ['2', '2', '0', '0'])
        self.assertEqual(len(app.get('download_button')), 3)
        self.assertEqual(len(app.get('iframe')), 1)

    def test_old_demo_session_returns_to_upload_screen_without_file(self):
        app = AppTest.from_file(str(ROOT / 'app_mapa.py'))
        app.session_state['base_nome'] = 'Exemplo · Minas Gerais'
        app.session_state['base_df'] = pd.DataFrame([
            {'Cidade': 'Bom Despacho', 'UF': 'MG', 'Região': 'Oeste'},
        ])
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(len(app.metric), 0)

    def test_pending_rows_are_visible_and_do_not_enter_map(self):
        app = AppTest.from_file(str(ROOT / 'app_mapa.py'))
        app.session_state['base_df'] = pd.DataFrame([
            {'Cidade': 'Abaeté', 'UF': 'MG', 'Região': 'Oeste'},
            {'Cidade': 'Abaeté', 'UF': 'MG', 'Região': 'Leste'},
            {'Cidade': 'Divinópolis', 'UF': 'MG', 'Região': 'Oeste'},
            {'Cidade': 'Inventada', 'UF': 'MG', 'Região': 'Oeste'},
        ])
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual([m.value for m in app.metric], ['1', '1', '3', '0'])
        self.assertTrue(app.warning)
        self.assertEqual(len(app.dataframe[0].value), 4)


if __name__ == '__main__':
    unittest.main()
