import copy
import unittest

import pandas as pd
from shapely.geometry import Point, shape

from mapas.dados import preparar_dados


def feature(code, name, uf='MG', x=-45):
    return {'type': 'Feature', 'properties': {'id': code, 'name': name, 'uf': uf},
            'geometry': {'type': 'Polygon', 'coordinates': [[[x, -21], [x + .3, -21],
                         [x + .3, -20], [x, -20], [x, -21]]]}}


GEO = {'type': 'FeatureCollection', 'features': [
    feature('3100203', 'Abaeté'), feature('3107406', 'Bom Despacho', x=-44),
    feature('4201406', 'Araranguá', 'SC', x=-49),
]}


class DadosTest(unittest.TestCase):
    def preparar(self, rows):
        return preparar_dados(pd.DataFrame(rows, columns=['Cidade', 'UF', 'Região', 'PDVs']), copy.deepcopy(GEO))

    def test_matches_accents_case_and_whitespace_without_mutating_input(self):
        geo = copy.deepcopy(GEO)
        data, report, pdvs = preparar_dados(pd.DataFrame([
            {'Cidade': '  ABAETE ', 'UF': ' mg ', 'Região': ' Centro   Oeste ', 'PDVs': 0},
        ]), geo)
        self.assertEqual(len(data['features']), 1)
        p = data['features'][0]['properties']
        self.assertEqual((p['name'], p['uf'], p['regiao'], p['pdvs']), ('Abaeté', 'MG', 'Centro Oeste', 0))
        self.assertEqual(report.iloc[0]['Status'], 'Mapeado')
        self.assertEqual(report.iloc[0]['Linha Excel'], 2)
        self.assertEqual(geo, GEO)
        self.assertTrue(pdvs)
        self.assertTrue(shape(data['features'][0]['geometry']).contains(Point(p['centro'][1], p['centro'][0])))

    def test_same_name_in_different_states_does_not_cross_match(self):
        geo = copy.deepcopy(GEO)
        geo['features'].append(feature('9999999', 'Abaeté', 'SP'))
        df = pd.DataFrame([{'Cidade': 'Abaeté', 'UF': 'SP', 'Região': 'Interior'}])
        data, _, _ = preparar_dados(df, geo)
        self.assertEqual(data['features'][0]['properties']['id'], '9999999')

    def test_reports_invalid_missing_and_unknown_rows(self):
        data, report, _ = self.preparar([
            ['Cidade inexistente', 'MG', 'A', None], ['Abaeté', 'XX', 'A', None],
            ['Abaeté', 'MG', '', None], ['', 'MG', 'A', None],
            ['Bom Despacho', 'MG', 'B', 9],
        ])
        self.assertEqual(len(data['features']), 1)
        self.assertEqual(report['Status'].tolist(), ['Não encontrado', 'UF inválida', 'Inválido', 'Inválido', 'Mapeado'])
        self.assertEqual(report['Linha Excel'].tolist(), [2, 3, 4, 5, 6])

    def test_identical_duplicates_count_once_including_pdvs(self):
        data, report, _ = self.preparar([['Abaeté', 'MG', 'Oeste', 2], ['ABAETE', 'mg', 'Oeste', 2]])
        self.assertEqual(len(data['features']), 1)
        self.assertEqual(data['features'][0]['properties']['pdvs'], 2)
        self.assertEqual(report['Status'].tolist(), ['Mapeado', 'Duplicado consolidado'])

    def test_conflicting_regions_exclude_every_occurrence(self):
        data, report, _ = self.preparar([['Abaeté', 'MG', 'Norte', 2], ['Abaeté', 'MG', 'Sul', 2]])
        self.assertEqual(data['features'], [])
        self.assertEqual(report['Status'].tolist(), ['Conflito', 'Conflito'])

    def test_conflicting_pdvs_are_not_summed_or_silently_discarded(self):
        for right in (3, None):
            with self.subTest(right=right):
                data, report, _ = self.preparar([['Abaeté', 'MG', 'A', 2], ['Abaeté', 'MG', 'A', right]])
                self.assertEqual(data['features'], [])
                self.assertTrue((report['Status'] == 'Conflito').all())

    def test_invalid_pdvs_and_unknown_are_distinct_from_zero(self):
        for value in (-1, 1.5, 'dois', float('inf')):
            with self.subTest(value=value):
                data, report, _ = self.preparar([['Abaeté', 'MG', 'A', value]])
                self.assertEqual(data['features'], [])
                self.assertEqual(report.iloc[0]['Status'], 'PDVs inválidos')
        data, _, _ = self.preparar([['Abaeté', 'MG', 'A', None], ['Bom Despacho', 'MG', 'A', 0]])
        self.assertEqual([f['properties']['pdvs'] for f in data['features']], [None, 0])

    def test_base_without_optional_pdvs(self):
        df = pd.DataFrame([{'Cidade': 'Abaeté', 'UF': 'MG', 'Região': 'A'}])
        data, _, has_pdvs = preparar_dados(df, GEO)
        self.assertFalse(has_pdvs)
        self.assertIsNone(data['features'][0]['properties']['pdvs'])

    def test_colors_and_region_labels_are_stable_after_reordering(self):
        rows = [['Abaeté', 'MG', 'Oeste', 2], ['Bom Despacho', 'MG', 'Norte', 9], ['Araranguá', 'SC', 'Sul', 3]]
        a, _, _ = self.preparar(rows)
        b, _, _ = self.preparar(list(reversed(rows)))
        self.assertEqual(a, b)
        self.assertEqual(len({f['properties']['cor'] for f in a['features']}), 3)

    def test_equivalent_region_names_are_unified(self):
        data, _, _ = self.preparar([['Abaeté', 'MG', 'Região Oeste', 2], ['Bom Despacho', 'MG', 'regiao oeste', 9]])
        self.assertEqual(len({f['properties']['regiao'] for f in data['features']}), 1)

    def test_ambiguous_geographic_name_is_reported(self):
        geo = copy.deepcopy(GEO)
        geo['features'].append(feature('9999999', 'Abaete'))
        data, report, _ = preparar_dados(pd.DataFrame([{'Cidade': 'Abaeté', 'UF': 'MG', 'Região': 'A'}]), geo)
        self.assertEqual(data['features'], [])
        self.assertEqual(report.iloc[0]['Status'], 'Nome ambíguo')

    def test_missing_empty_and_duplicate_columns_fail_clearly(self):
        for df, expected in [
            (pd.DataFrame({'Cidade': ['A']}), 'Colunas obrigatórias'),
            (pd.DataFrame(columns=['Cidade', 'UF', 'Região']), 'não contém linhas'),
            (pd.DataFrame([['A', 'MG', 'B', 'C']], columns=['Cidade', 'UF', 'Região', 'Região']), 'repetidos'),
        ]:
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, expected):
                preparar_dados(df, GEO)


if __name__ == '__main__':
    unittest.main()
