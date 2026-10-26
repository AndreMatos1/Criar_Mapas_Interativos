"""Validação da planilha e associação aos municípios, sem dependência de UI."""

import copy
import hashlib
import json
import math
from pathlib import Path
import unicodedata

import pandas as pd
from shapely.geometry import shape


UF_VALIDAS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
CORES = ('#1769aa', '#16865a', '#d67b13', '#8454c0', '#cc455c', '#008e9b',
         '#4357bc', '#a35725', '#638a20', '#b23a91', '#087ca7', '#b18a10')


def texto(value):
    return '' if pd.isna(value) else ' '.join(str(value).split())


def normalizar(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto(value).casefold())
                   if not unicodedata.combining(c))


def cor_regiao(regiao):
    """A mesma região mantém a cor ao reordenar ou filtrar a planilha."""
    digest = hashlib.sha256(normalizar(regiao).encode('utf-8')).digest()
    return CORES[int.from_bytes(digest[:4], 'big') % len(CORES)]


def carregar_municipios(pasta, ufs):
    features, ausentes = [], []
    for uf in sorted(set(ufs) & UF_VALIDAS):
        arquivo = Path(pasta) / f'limites_mun_{uf}.json'
        if not arquivo.exists():
            ausentes.append(uf)
            continue
        for feature in json.loads(arquivo.read_text(encoding='utf-8'))['features']:
            feature['properties']['uf'] = uf
            features.append(feature)
    return {'type': 'FeatureCollection', 'features': features}, ausentes


def preparar_dados(planilha, municipios):
    """Retorna feições únicas e uma conferência de todas as linhas do Excel.

    Repetições idênticas são consolidadas. Municípios com regiões ou quantidades
    conflitantes são excluídos até que a planilha seja corrigida.
    """
    df = planilha.copy()
    df.columns = [texto(c) for c in df.columns]
    if df.columns.duplicated().any():
        raise ValueError('A planilha contém nomes de colunas repetidos.')
    faltantes = {'Cidade', 'UF', 'Região'} - set(df.columns)
    if faltantes:
        raise ValueError('Colunas obrigatórias ausentes: ' + ', '.join(sorted(faltantes)))
    if df.empty:
        raise ValueError('A planilha não contém linhas para mapear.')

    pdv_col = next((c for c in ('PDVs', 'Qtde PDVs', 'Quantidade PDVs') if c in df), None)
    indice = {}
    for feature in municipios.get('features', []):
        p = feature['properties']
        indice.setdefault((normalizar(p.get('name', '')), p.get('uf')), []).append(feature)

    linhas, candidatos = [], {}
    for numero, (_, row) in enumerate(df.iterrows(), start=2):
        cidade, uf, regiao = texto(row['Cidade']), texto(row['UF']).upper(), texto(row['Região'])
        item = {'Linha Excel': numero, 'Cidade': cidade, 'UF': uf, 'Região': regiao,
                'Status': '', 'Detalhe': ''}
        linhas.append(item)
        if not cidade or not uf or not regiao:
            item.update(Status='Inválido', Detalhe='Preencha Cidade, UF e Região.')
            continue
        if uf not in UF_VALIDAS:
            item.update(Status='UF inválida', Detalhe='Use uma sigla de UF brasileira.')
            continue
        pdvs = None
        if pdv_col and texto(row[pdv_col]):
            try:
                n = float(texto(row[pdv_col]).replace(',', '.'))
                if not math.isfinite(n) or n < 0 or not n.is_integer():
                    raise ValueError
                pdvs = int(n)
            except (TypeError, ValueError, OverflowError):
                item.update(Status='PDVs inválidos', Detalhe='Informe um número inteiro maior ou igual a zero.')
                continue
        key = (normalizar(cidade), uf)
        encontrados = indice.get(key, [])
        if len(encontrados) != 1:
            item.update(Status='Não encontrado' if not encontrados else 'Nome ambíguo',
                        Detalhe='Confira o nome oficial e a malha da UF.' if not encontrados
                        else 'Mais de um município corresponde ao nome informado.')
            continue
        candidatos.setdefault(key, []).append((item, encontrados[0], pdvs))

    features = []
    for registros in candidatos.values():
        regioes = {normalizar(r[0]['Região']) for r in registros}
        quantidades = {r[2] for r in registros}
        if len(regioes) > 1 or len(quantidades) > 1:
            for item, _, _ in registros:
                item.update(Status='Conflito', Detalhe='Cidade/UF repetida com regiões ou PDVs diferentes; excluída do mapa.')
            continue
        item, original, pdvs = registros[0]
        # Escolha determinística inclusive quando só a capitalização varia.
        regiao = sorted((r[0]['Região'] for r in registros), key=lambda x: (normalizar(x), x))[0]
        feature = copy.deepcopy(original)
        props = feature['properties']
        props.update(regiao=regiao, pdvs=pdvs)
        props['id'] = str(props.get('id') or f"{props['uf']}:{normalizar(props['name'])}")
        center = shape(feature['geometry']).representative_point()
        props['centro'] = [center.y, center.x]
        features.append(feature)
        item.update(Status='Mapeado', Detalhe='Município associado à malha geográfica.')
        for repetido, _, _ in registros[1:]:
            repetido.update(Status='Duplicado consolidado', Detalhe='Repetição idêntica; contabilizada uma única vez.')

    # Unifica a grafia de regiões equivalentes em municípios diferentes.
    nomes = {}
    for f in features:
        r = f['properties']['regiao']
        key = normalizar(r)
        nomes[key] = min(nomes.get(key, r), r)
    cores = {}
    usadas = set()
    for key, nome in sorted(nomes.items()):
        primeira = CORES.index(cor_regiao(nome))
        disponiveis = [CORES[(primeira + i) % len(CORES)] for i in range(len(CORES))]
        cor = next((c for c in disponiveis if c not in usadas), None)
        if cor is None:
            # Depois da paleta, varia o matiz em vez de repetir exatamente a cor.
            cor = f'hsl({(len(cores) * 137.508) % 360:.2f}, 42%, 43%)'
        cores[key] = cor
        usadas.add(cor)
    for f in features:
        key = normalizar(f['properties']['regiao'])
        f['properties'].update(regiao=nomes[key], cor=cores[key])
    features.sort(key=lambda f: (f['properties']['uf'], normalizar(f['properties']['name'])))
    relatorio = pd.DataFrame(linhas)
    return {'type': 'FeatureCollection', 'features': features}, relatorio, bool(pdv_col)
