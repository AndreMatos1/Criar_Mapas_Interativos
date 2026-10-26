"""Importa uma base Excel e gera um explorador territorial compartilhável."""

from io import BytesIO
from pathlib import Path
import hashlib
import json
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from mapas.dados import carregar_municipios, preparar_dados, texto
from mapas.visualizacao import criar_mapa, exportar_html

APP_DIR = Path(__file__).resolve().parent
st.set_page_config(page_title='Mapas Interativos', page_icon='🌍', layout='wide')


@st.cache_data(show_spinner=False)
def analisar_planilha(df):
    ufs = [texto(x).upper() for x in df['UF']] if 'UF' in df else []
    municipios, ausentes = carregar_municipios(APP_DIR / 'Json_Polígonos_Geom_Cidades_Brasil', ufs)
    features, relatorio, tem_pdvs = preparar_dados(df, municipios)
    return features, relatorio, tem_pdvs, ausentes, municipios


@st.cache_data(show_spinner=False)
def carregar_estados():
    return json.loads((APP_DIR / 'data' / 'estados_brasil.geojson').read_text(encoding='utf-8'))


@st.cache_data(show_spinner=False)
def planilha_modelo():
    buffer = BytesIO()
    pd.DataFrame([
        {'Cidade': 'Bom Despacho', 'UF': 'MG', 'Região': 'Centro-Oeste MG', 'PDVs': 9},
        {'Cidade': 'Divinópolis', 'UF': 'MG', 'Região': 'Centro-Oeste MG', 'PDVs': 12},
        {'Cidade': 'Itaúna', 'UF': 'MG', 'Região': 'Centro-Oeste MG', 'PDVs': 4},
        {'Cidade': 'Piumhi', 'UF': 'MG', 'Região': 'Canastra', 'PDVs': 7},
        {'Cidade': 'São Roque de Minas', 'UF': 'MG', 'Região': 'Canastra', 'PDVs': 2},
        {'Cidade': 'Vargem Bonita', 'UF': 'MG', 'Região': 'Canastra', 'PDVs': 0},
    ]).to_excel(buffer, index=False)
    return buffer.getvalue()


st.markdown('''<style>
.block-container{padding-top:1.6rem;padding-bottom:1rem;max-width:1800px}
[data-testid="stSidebar"]{background:#f4f8f9}
[data-testid="stMetricValue"]{color:#176c72}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.header('Preparar mapa')
    st.caption('Carregue sua lista de cidades, estados e regiões comerciais.')
    arquivo = st.file_uploader('Planilha Excel', type=['xlsx'], key='arquivo_excel')
    st.download_button('Baixar planilha de exemplo', planilha_modelo(),
                       file_name='modelo_territorios.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.caption('Obrigatórias: Cidade, UF e Região. PDVs é uma coluna opcional.')
    if st.button('Explorar exemplo', width='stretch'):
        st.session_state['base_df'] = pd.read_excel(BytesIO(planilha_modelo()))
        st.session_state['base_nome'] = 'Exemplo · Minas Gerais'
        # Não reimporta um arquivo anterior enquanto o usuário explora o exemplo.
        st.session_state['arquivo_processado'] = hashlib.sha256(arquivo.getvalue()).hexdigest() if arquivo else None
    titulo = st.text_input('Título do mapa', value='Mapa de territórios', max_chars=100)
    apresentacao = st.toggle('Abrir em modo apresentação', value=False,
                             help='Oculta busca e configurações dentro do mapa. Resumo e legenda continuam visíveis.')
    st.divider()
    st.caption('O HTML baixado leva os dados e controles do mapa. Não exige que o Streamlit esteja aberto.')
    st.caption('Desenvolvido por André Matos')

if arquivo is not None:
    digest = hashlib.sha256(arquivo.getvalue()).hexdigest()
    if digest != st.session_state.get('arquivo_processado'):
        try:
            novo_df = pd.read_excel(BytesIO(arquivo.getvalue()))
            novo_df.columns = [texto(c) for c in novo_df.columns]
            # Valida antes de substituir uma base já carregada.
            analisar_planilha(novo_df)
        except (ValueError, OSError, KeyError, TypeError, ImportError, BadZipFile, ParseError) as exc:
            st.error(f'Não foi possível importar a planilha: {exc}')
            st.stop()
        st.session_state.update(base_df=novo_df, base_nome=arquivo.name, arquivo_processado=digest)

st.title('Mapas Interativos')
st.caption('Explore sua cobertura comercial por estado, região e município.')

if 'base_df' not in st.session_state:
    st.info('Carregue uma planilha pela lateral ou use “Explorar exemplo” para conhecer a visualização.')
    st.markdown('**Da planilha para a exploração:** importe sua base, confira as pendências e navegue pelo mapa. '
                'Você pode buscar cidades, destacar regiões, consultar detalhes e baixar o HTML interativo.')
    st.stop()

try:
    with st.spinner('Preparando os territórios…'):
        municipios, relatorio, tem_pdvs, ausentes, contexto = analisar_planilha(st.session_state['base_df'])
except (ValueError, OSError, KeyError, TypeError) as exc:
    st.error(f'Não foi possível preparar o mapa: {exc}')
    st.stop()

validos = len(municipios['features'])
pendencias = relatorio[~relatorio['Status'].isin(['Mapeado', 'Duplicado consolidado'])]
duplicados = int((relatorio['Status'] == 'Duplicado consolidado').sum())
colunas = st.columns(4)
for col, label, value in zip(colunas, ['Municípios mapeados', 'Regiões', 'Linhas com pendências', 'Repetições consolidadas'],
                            [validos, len({f['properties']['regiao'] for f in municipios['features']}), len(pendencias), duplicados]):
    col.metric(label, value)
if ausentes:
    st.warning('Malhas municipais não encontradas para: ' + ', '.join(ausentes))
if len(pendencias):
    st.warning(f'{len(pendencias)} linha(s) precisam de revisão e não entraram no mapa. Consulte a aba Conferência.')

aba_mapa, aba_conferencia = st.tabs(['Mapa', 'Conferência da planilha'])
with aba_mapa:
    if validos:
        with st.spinner('Montando o mapa interativo…'):
            mapa = criar_mapa(municipios, carregar_estados(), tem_pdvs, titulo.strip() or 'Mapa de territórios',
                              apresentacao, contexto_municipal=contexto)
            html = exportar_html(mapa)
        st.download_button('Baixar mapa interativo em HTML', data=html.encode('utf-8'),
                           file_name='mapa_interativo.html', mime='text/html', type='primary')
        if hasattr(st, 'iframe'):
            st.iframe(html, height=800, alt='Explorador de municípios e regiões comerciais')
        else:
            # Compatibilidade com instalações anteriores ao st.iframe.
            components.html(html, height=800, scrolling=False)
        st.caption('Use os polígonos, a busca ou a legenda para navegar. O HTML funciona offline na visão '
                   'territorial. A visão geográfica precisa de internet para carregar o mapa do provedor.')
    else:
        st.info('Nenhum município pôde ser mapeado. Corrija as pendências e carregue o arquivo novamente.')
with aba_conferencia:
    st.subheader('Conferência de todas as linhas')
    st.caption('Repetições idênticas são contabilizadas uma vez. Cidades com regiões ou PDVs conflitantes '
               'ficam fora do mapa até a correção. As quantidades de PDVs não são somadas entre duplicatas.')
    apenas_pendencias = st.checkbox('Mostrar somente pendências')
    st.dataframe(pendencias if apenas_pendencias else relatorio, hide_index=True, width='stretch')
    st.download_button('Baixar conferência em CSV', relatorio.to_csv(index=False).encode('utf-8-sig'),
                       file_name='conferencia_municipios.csv', mime='text/csv')
