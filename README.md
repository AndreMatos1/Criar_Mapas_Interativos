# Cria-o_Mapas_Interativos
Este script cria mapas interativos a partir de parâmetros de arquivos Json e Excel.

Execute com `streamlit run app_mapa.py` após instalar `pip install -r requirements.txt`.

### Fundo do mapa e mensagem “API KEY REQUIRED”

O provedor CARTO passou a exigir uma chave para seus mapas base. O antigo
`CartoDB positron` era solicitado sem chave, por isso o próprio serviço devolvia
imagens com essa mensagem. Não é um erro da planilha ou dos polígonos.

Por padrão, em páginas HTTP/HTTPS o aplicativo usa **OpenStreetMap.Mapnik**, com
cidades, estradas, rios e países vizinhos, sem solicitações à CARTO e sem chave.
O controle de camadas também oferece Esri WorldTopoMap como alternativa.
No Streamlit, o componente `st_folium` inicia explicitamente com Mapnik ativo.
A escolha automática pela origem da página é aplicada somente à cópia exportada;
ela não pode substituir Mapnik por Esri dentro do aplicativo.
Os contornos dos municípios, as cores das regiões, os tooltips e os controles
continuam disponíveis, tanto no aplicativo quanto no HTML baixado.

Para incluir o fundo de ruas e nomes da CARTO, obtenha uma chave em
https://carto.com/basemaps/apikey e configure a variável de ambiente
`CARTO_API_KEY` antes de iniciar o Streamlit. Exemplo no PowerShell:

```powershell
$env:CARTO_API_KEY = 'sua-chave'
streamlit run app_mapa.py
```

A chave é incluída nas URLs públicas do mapa e no HTML exportado; use uma chave
destinada a mapas no navegador, com as restrições e limites adequados no provedor.
Uma chave inválida pode voltar a exibir a marca da CARTO. Nesse caso, remova a
variável e reinicie o aplicativo, ou selecione “OpenStreetMap.Mapnik” no controle de camadas.
O fundo CARTO é uma alternativa opcional, inicialmente desativada.

Gere e baixe novamente os mapas antigos para incorporar a correção. O HTML ainda
precisa de internet para carregar as imagens do mapa e as bibliotecas JavaScript
e CSS do Folium. A disponibilidade do fundo depende dos serviços externos;
a atribuição de cada provedor é mantida no mapa.

### OpenStreetMap no HTML baixado

O servidor `tile.openstreetmap.org` exige um Referer HTTP válido nas páginas web.
Um HTML aberto por duplo clique (`file://`) não fornece essa origem, então o
aplicativo seleciona automaticamente Esri nesse contexto, antes de pedir tiles
ao OpenStreetMap. OSM continua disponível para páginas servidas por HTTP/HTTPS,
inclusive o HTML exportado quando hospedado em um servidor web.
Iframes sem origem web identificável também usam a alternativa Esri.

Para visualizar um HTML local com Mapnik, na pasta que contém apenas os arquivos
que deseja servir, execute `python -m http.server 8000 --bind 127.0.0.1` e abra
`http://localhost:8000/mapa_interativo.html` no navegador. Encerre com Ctrl+C.
Não há download antecipado de tiles nem suporte a mapas offline.
Política do provedor: https://operations.osmfoundation.org/policies/tiles/.

### Brasil completo e divisas estaduais

O mapa abre enquadrando as 27 UFs, inclusive as que não aparecem na planilha.
O mapa geográfico fica visível, sem uma camada cinza cobrindo o território.
Os municípios das UFs carregadas
mantêm linhas finas (0,35 px). As UFs identificadas na planilha recebem bordas
azuis espessas (3,5 px); as demais mantêm divisas discretas (1,2 px).
As regiões coloridas aparecem automaticamente ao carregar a planilha e podem
ser ocultadas individualmente pelo controle de camadas. O mapa geográfico
permanece visível em todo o território, com as divisas acima das cores.
Essa camada não intercepta o mouse, preservando os tooltips dos municípios.
É possível alternar as divisas no controle de camadas; o contexto nacional
permanece disponível. O mesmo desenho acompanha o HTML exportado.

A base `data/estados_brasil.geojson` é derivada da união dos municípios já
incluídos neste repositório, sem simplificação das coordenadas. As divisas são
locais; as imagens de fundo são carregadas do provedor escolhido. Para regenerar a base após atualizar
os municípios, instale `shapely` e execute `python scripts/gerar_estados.py`.
Shapely é necessário apenas nessa regeneração, não na hospedagem do aplicativo.

Testes: `python -m unittest discover -s tests -v`.
