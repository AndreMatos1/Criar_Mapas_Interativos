# Cria-o_Mapas_Interativos
Este script cria mapas interativos a partir de parâmetros de arquivos Json e Excel.

Execute com `streamlit run app_mapa.py` após instalar `pip install -r requirements.txt`.

### Fundo do mapa e mensagem “API KEY REQUIRED”

O provedor CARTO passou a exigir uma chave para seus mapas base. O antigo
`CartoDB positron` era solicitado sem chave, por isso o próprio serviço devolvia
imagens com essa mensagem. Não é um erro da planilha ou dos polígonos.

Por padrão, o aplicativo agora usa um fundo neutro, sem solicitações à CARTO.
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
variável e reinicie o aplicativo, ou desative “Mapa base CARTO” no controle de camadas.

Gere e baixe novamente os mapas antigos para incorporar a correção. O HTML ainda
precisa de internet para carregar as bibliotecas JavaScript e CSS do Folium;
o fundo neutro elimina apenas a dependência de imagens do mapa base.
