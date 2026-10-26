"""Regressões de interação no navegador. Opcional: requirements-dev.txt + Chromium."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import pandas as pd
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from mapas.dados import carregar_municipios, preparar_dados
from mapas.visualizacao import criar_mapa, exportar_html

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sync_playwright, 'Instale requirements-dev.txt para executar os testes de navegador.')
class InteracaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('MAPAS_BROWSER_EXECUTABLE')
        try:
            cls.browser = cls.playwright.chromium.launch(
                executable_path=executable, headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--no-zygote'],
            )
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest('Chromium indisponível; execute python -m playwright install chromium.') from exc
        geo, _ = carregar_municipios(ROOT / 'Json_Polígonos_Geom_Cidades_Brasil', ['MG', 'SC'])
        rows = [
            ('Bom Despacho', 'MG', 'Centro-Oeste', 9), ('Divinópolis', 'MG', 'Centro-Oeste', 12),
            ('Itaúna', 'MG', 'Centro-Oeste', 4), ('Piumhi', 'MG', 'Canastra', 7),
            ('São Roque de Minas', 'MG', 'Canastra', 2), ('Vargem Bonita', 'MG', 'Canastra', 0),
            ('Araranguá', 'SC', 'Litoral Sul', None),
        ]
        features, _, pdvs = preparar_dados(pd.DataFrame(rows, columns=['Cidade', 'UF', 'Região', 'PDVs']), geo)
        states = json.loads((ROOT / 'data' / 'estados_brasil.geojson').read_text())
        cls.folder = tempfile.TemporaryDirectory()
        cls.path = Path(cls.folder.name) / 'mapa.html'
        cls.path.write_text(exportar_html(criar_mapa(features, states, pdvs, contexto_municipal=geo)), encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.folder.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 950}, offline=True)
        self.page = self.context.new_page()
        self.errors, self.requests = [], []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.on('request', lambda request: self.requests.append(request.url))
        self.page.goto(self.path.as_uri())
        self.page.locator('.map-stat').first.wait_for()

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.context.close()

    def counts(self):
        return self.page.locator('.map-stat strong').all_text_contents()

    def test_initial_map_offline_filters_and_clear(self):
        self.assertEqual(self.counts(), ['7', '3', '2', '34'])
        self.assertIn('soma parcial', self.page.locator('#stats').inner_text())
        self.assertFalse(any(url.startswith('http') for url in self.requests))
        self.page.locator('#state-filter').select_option('MG')
        self.assertEqual(self.counts(), ['6', '2', '1', '34'])
        self.page.locator('.region-item').filter(has_text='Canastra').click()
        self.assertEqual(self.counts(), ['3', '1', '1', '9'])
        self.page.locator('#clear-filters').click()
        self.assertEqual(self.counts(), ['7', '3', '2', '34'])

    def test_accent_insensitive_search_details_zero_and_breadcrumb(self):
        self.page.locator('#city-search').fill('vargem')
        self.page.locator('#search-results button').click()
        self.assertEqual(self.page.locator('#detail-title').inner_text(), 'Vargem Bonita')
        self.assertEqual(self.page.locator('#detail-fields dd').all_text_contents(), ['MG', 'Canastra', '3170602', '0'])
        self.assertIn('Vargem Bonita', self.page.locator('#map-breadcrumb').inner_text())
        self.page.locator('#map-breadcrumb button').filter(has_text='Brasil').click()
        self.assertTrue(self.page.locator('#detail-panel').is_hidden())
        self.page.locator('#city-search').fill('ararangua')
        self.page.locator('#city-search').press('Enter')
        self.assertEqual(self.page.locator('#detail-title').inner_text(), 'Araranguá')
        self.assertIn('Não informado', self.page.locator('#detail-fields').inner_text())
        self.assertEqual(self.page.locator('#state-filter').input_value(), 'SC')

    def test_marker_click_and_zoom_size(self):
        self.page.locator('#state-filter').select_option('MG')
        # Clica no marcador real, sem chamar diretamente o código do aplicativo.
        self.page.locator('.pdv-bubble').filter(has_text='12').click()
        self.assertEqual(self.page.locator('#detail-title').inner_text(), 'Divinópolis')
        size_near = self.page.locator('.pdv-bubble').first.bounding_box()['width']
        self.page.locator('#show-brazil').click()
        self.page.wait_for_timeout(150)  # requestAnimationFrame das anotações
        size_far = self.page.locator('.pdv-bubble').first.bounding_box()['width']
        self.assertLess(size_far, size_near)
        self.assertLessEqual(size_near, 24)
        self.page.locator('summary').click()
        self.page.locator('#show-boundaries').check()
        self.page.locator('#show-pdvs').uncheck()
        self.assertEqual(self.page.locator('.pdv-bubble').count(), 0)

    def test_hover_relief_clears_without_changing_filters_or_counts(self):
        self.page.locator('#state-filter').select_option('MG')
        self.page.locator('#region-filter').select_option('Centro-Oeste')
        before = self.counts()
        marker = self.page.locator('.pdv-bubble').filter(has_text='12')
        marker.hover()
        face = self.page.locator('.territory-face.is-hovered')
        self.assertEqual(face.get_attribute('data-territory-id'), '3122306')
        self.assertNotEqual(face.evaluate('el => getComputedStyle(el).filter'), 'none')
        # Sai do marcador para o interior do polígono: testa o hover do mapa.
        box = marker.bounding_box()
        self.page.mouse.move(box['x'] + box['width'] + 20, box['y'] + box['height']/2)
        self.assertEqual(face.get_attribute('data-territory-id'), '3122306')
        self.assertEqual(self.counts(), before)
        self.page.locator('#presentation').hover()
        self.assertEqual(self.page.locator('.territory-face').count(), 0)
        marker.click()
        self.page.locator('#presentation').hover()
        self.assertEqual(self.page.locator('.territory-face').count(), 1)
        self.page.locator('#clear-filters').click()
        self.assertEqual(self.counts(), ['7', '3', '2', '34'])
        self.assertEqual(self.page.locator('.territory-face').count(), 0)

    def test_hover_label_is_compact_and_below_right_of_cursor(self):
        self.page.locator('#region-filter').select_option('Centro-Oeste')
        marker = self.page.locator('.pdv-bubble').filter(has_text='12')
        marker.hover()
        position = marker.bounding_box()
        tooltip = self.page.locator('.territory-hover-tooltip:visible').last
        bounds = tooltip.bounding_box()
        self.assertGreaterEqual(bounds['x'], position['x'] + position['width']/2 + 18)
        self.assertGreaterEqual(bounds['y'], position['y'] + position['height']/2 + 18)
        self.assertLessEqual(bounds['width'], 220)
        self.assertLessEqual(bounds['height'], 60)
        self.assertEqual(self.page.locator('.territory-face.is-hovered').count(), 1)
        # Perto da borda inferior direita, o rótulo deve inverter e continuar visível.
        center = {'x': position['x'] + position['width']/2, 'y': position['y'] + position['height']/2}
        map_id = self.page.locator('.folium-map').get_attribute('id')
        self.page.evaluate('''({id, x, y}) => {
            const map = window[id], size = map.getSize();
            map.panBy([x - (size.x - 100), y - (size.y - 40)], {animate: false});
            return new Promise(requestAnimationFrame);
        }''', {'id': map_id, **center})
        marker.hover()
        position = marker.bounding_box()
        bounds = self.page.locator('.territory-hover-tooltip:visible').last.bounding_box()
        self.assertLessEqual(bounds['x'] + bounds['width'], position['x'] + position['width']/2 - 18)
        self.assertLessEqual(bounds['y'] + bounds['height'], position['y'] + position['height']/2 - 18)
        self.assertGreaterEqual(bounds['x'], 0)
        self.assertGreaterEqual(bounds['y'], 0)

    def test_presentation_and_mobile_controls(self):
        self.page.locator('#presentation').click()
        self.assertTrue(self.page.locator('#city-search').is_hidden())
        self.assertTrue(self.page.locator('#stats').is_visible())
        self.assertTrue(self.page.locator('#region-legend').is_visible())
        self.page.locator('#presentation').click()
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('#panel-toggle').click()
        self.assertTrue(self.page.locator('#city-search').is_hidden())
        self.page.locator('#panel-toggle').click()
        self.page.locator('#city-search').fill('itauna')
        self.page.locator('#search-results button').click()
        self.assertEqual(self.page.locator('#detail-title').inner_text(), 'Itaúna')
        self.assertTrue(self.page.locator('#detail-panel').is_visible())
        self.assertTrue(self.page.locator('#city-search').is_hidden())
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)

    def test_geographic_fallback_and_return_to_territorial(self):
        self.page.locator('summary').click()
        self.page.locator('#view-mode').select_option('geographic')
        self.page.wait_for_timeout(150)
        # O arquivo local escolhe Esri; não solicita tiles OSM sem origem web.
        tile_urls = [url for url in self.requests if url.startswith('http')]
        self.assertTrue(any('World_Topo_Map' in url for url in tile_urls))
        self.assertFalse(any('tile.openstreetmap.org' in url for url in tile_urls))
        self.page.locator('#view-mode').select_option('territorial')
        self.assertEqual(self.page.locator('.leaflet-tile-container').count(), 0)
        self.assertEqual(self.counts(), ['7', '3', '2', '34'])


if __name__ == '__main__':
    unittest.main()
