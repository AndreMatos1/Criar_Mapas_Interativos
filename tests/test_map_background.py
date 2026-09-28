import copy
import os
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

    def test_without_key_exports_polygons_without_tile_requests(self):
        html = self.render_map('')
        self.assertNotIn('cartocdn.com', html)
        self.assertNotIn('L.tileLayer(', html)

    def test_blank_key_uses_neutral_background(self):
        self.assertNotIn('L.tileLayer(', self.render_map('   '))

    def test_configured_key_is_encoded_and_layer_can_be_hidden(self):
        html = self.render_map('example&key=value')
        self.assertIn('?key=example%26key%3Dvalue', html)
        self.assertIn('Mapa base CARTO', html)
        self.assertIn('carto.com/attributions', html)
        self.assertEqual(html.count('L.tileLayer('), 1)


if __name__ == '__main__':
    unittest.main()
