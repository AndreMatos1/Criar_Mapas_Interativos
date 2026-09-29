"""Gera a base estadual usando os municípios do repositório.

Executar apenas ao atualizar a base: pip install shapely && python scripts/gerar_estados.py
Shapely não é necessário para executar o aplicativo.
"""
import json
from pathlib import Path

from shapely import make_valid, union_all
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
features = []
for source in sorted((ROOT / 'Json_Polígonos_Geom_Cidades_Brasil').glob('limites_mun_*.json')):
    uf = source.stem.rsplit('_', 1)[1]
    municipalities = json.loads(source.read_text(encoding='utf-8'))['features']
    geometry = union_all([make_valid(shape(item['geometry'])) for item in municipalities])
    if geometry.geom_type not in ('Polygon', 'MultiPolygon') or not geometry.is_valid:
        raise ValueError(f'Geometria estadual inválida: {uf}')
    features.append({'type': 'Feature', 'properties': {'uf': uf}, 'geometry': mapping(geometry)})
    print(uf, flush=True)
if len(features) != 27:
    raise ValueError('A base deve conter as 27 UFs.')
target = ROOT / 'data' / 'estados_brasil.geojson'
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                             ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
