# Cria-o_Mapas_Interativos
Este script cria mapas interativos a partir de parâmetros de arquivos Json e Excel.

Execute com `streamlit run app_mapa.py` após instalar `pip install -r requirements.txt`.

### Fundo do mapa e mensagem “API KEY REQUIRED”

O provedor CARTO passou a exigir uma chave para seus mapas base. O antigo
`CartoDB positron` era solicitado sem chave, por isso o próprio serviço devolvia
imagens com essa mensagem. Não é um erro da planilha ou dos polígonos.

Por padrão, o aplicativo usa o mapa topográfico Esri WorldTopoMap, com cidades,
estradas, rios, relevo e países vizinhos, sem solicitações à CARTO e sem chave.
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
variável e reinicie o aplicativo, ou selecione “Mapa geográfico” no controle de camadas.
O fundo CARTO é uma alternativa opcional, inicialmente desativada.

Gere e baixe novamente os mapas antigos para incorporar a correção. O HTML ainda
precisa de internet para carregar as imagens do mapa e as bibliotecas JavaScript
e CSS do Folium. A disponibilidade do fundo depende do serviço externo da Esri;
a atribuição do provedor é mantida no mapa.

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
locais; as imagens de fundo são carregadas da Esri. Para regenerar a base após atualizar
os municípios, instale `shapely` e execute `python scripts/gerar_estados.py`.
Shapely é necessário apenas nessa regeneração, não na hospedagem do aplicativo.

Testes: `python -m unittest discover -s tests -v`.
