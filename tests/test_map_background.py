import copy
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / 'app_mapa.py'
FEATURE = {
    'type': 'Feature',
    'properties': {'name': 'Teste', 'name_normalized': 'teste', 'uf': 'SP'},
    'geometry': {
        'type': 'Polygon',
        'coordinates': [[[-47, -23], [-46, -23], [-46, -22], [-47, -23]]],
    },
}


class MapBackgroundTest(unittest.TestCase):
    def render_map(self, key):
        app = AppTest.from_file(str(APP))
        app.session_state['files_loaded'] = True
        app.session_state['estados_detectados'] = ['SP']
        app.session_state['df'] = pd.DataFrame([{
            'Cidade': 'Teste', 'Cidade_normalizada': 'teste',
            'UF': 'SP', 'Região': 'Regiao teste',
        }])
        app.session_state['municipios_geojson'] = {
            'type': 'FeatureCollection', 'features': [copy.deepcopy(FEATURE)],
        }
        with tempfile.TemporaryDirectory() as folder:
            previous = os.getcwd()
            try:
                os.chdir(folder)
                with patch.dict(os.environ, {'CARTO_API_KEY': key}):
                    app.run(timeout=30)
                self.assertEqual(len(app.exception), 0, str(app.exception))
                html = Path('mapa_interativo.html').read_text(encoding='utf-8')
            finally:
                os.chdir(previous)
        self.assertIn('Regiao teste', html)
        self.assertIn('L.geoJson', html)
        self.assertIn('Cidade:', html)
        self.assertEqual(len(app.get('download_button')), 1)
        return html

    def test_without_key_exports_geographic_basemap_without_carto(self):
        html = self.render_map('')
        self.assertNotIn('cartocdn.com', html)
        self.assertIn('World_Topo_Map/MapServer/tile/', html)
        self.assertEqual(html.count('L.tileLayer('), 1)
        self.assertNotIn('brasil_fundo', html)
        self.assertNotIn('#e2e8f0', html)

    def test_blank_key_uses_geographic_basemap(self):
        html = self.render_map('   ')
        self.assertIn('World_Topo_Map/MapServer/tile/', html)
        self.assertNotIn('cartocdn.com', html)

    def test_configured_key_is_encoded_and_layer_can_be_hidden(self):
        html = self.render_map('example&key=value')
        self.assertIn('?key=example%26key%3Dvalue', html)
        self.assertIn('Mapa base CARTO', html)
        self.assertIn('carto.com/attributions', html)
        self.assertEqual(html.count('L.tileLayer('), 2)
        self.assertIn('Mapa geogr', html)

    def test_single_state_input_keeps_all_brazil_and_visible_borders(self):
        html = self.render_map('')
        data = json.loads((APP.parent / 'data' / 'estados_brasil.geojson').read_text(encoding='utf-8'))
        expected = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
        self.assertEqual({f['properties']['uf'] for f in data['features']}, expected)
        self.assertEqual(len(data['features']), 27)
        for uf in expected:
            self.assertIn(f'"uf": "{uf}"', html)
        self.assertIn('.fitBounds(', html)
        self.assertIn('"weight": 3.5', html)
        self.assertIn('"weight": 1.2', html)
        self.assertIn('"fill": false', html)
        self.assertIn('divisas_estaduais', html)
        self.assertTrue("pointerEvents = 'none'" in html)

    def test_regions_visible_on_load_and_only_input_state_highlighted(self):
        html = self.render_map('')
        group = re.search(r'"Regiao teste"\s*:\s*(feature_group_\w+)', html)
        self.assertIsNotNone(group)
        self.assertTrue(re.search(re.escape(group.group(1)) + r'\.addTo\(map_', html) is not None)
        style = re.search(r'switch\(feature.properties.uf\)\s*\{(.*?)\n\s*\}', html, re.S)
        self.assertIsNotNone(style)
        cases = re.findall(r'case "([A-Z]{2})":', style.group(1))
        self.assertEqual(len(cases), 26)
        self.assertNotIn('SP', cases)
        default = re.search(r'default:\s*return (\{[^}]+\});', style.group(1))
        self.assertEqual(json.loads(default.group(1))['color'], '#1d4ed8')
        self.assertEqual(json.loads(default.group(1))['weight'], 3.5)


if __name__ == '__main__':
    unittest.main()
