// Interações locais: o mesmo código funciona na prévia e no HTML baixado.
const $ = id => document.getElementById(id);
const fmt = n => n.toLocaleString('pt-BR');
const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const all = features.features;
const byId = new Map(all.map(f => [String(f.properties.id), f]));
const regionColors = new Map(all.map(f => [f.properties.regiao, f.properties.cor]));
const baseStates = new Set(all.map(f => f.properties.uf));
const stateLayers = new Map(), cityLayers = new Map();
let selectedState = '', selectedRegion = '', selectedCity = null, currentTiles = null;
let geographic = false, presentation = config.apresentacao;
let pendingResize = null;
let municipalBoundaries = null;
let hoveredFeature = null;
map.createPane('territory-emphasis');
map.getPane('territory-emphasis').style.zIndex = 460;
map.getPane('territory-emphasis').style.pointerEvents = 'none';
const emphasisRenderer = L.svg({pane: 'territory-emphasis', padding: .5});
const emphasis = L.layerGroup().addTo(map);

function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function button(text, action, className) {
  const b = node('button', text, className); b.type = 'button'; b.onclick = action; return b;
}
function matches(p) {
  return (!selectedState || p.uf === selectedState) && (!selectedRegion || p.regiao === selectedRegion);
}
function activeFeatures() { return all.filter(f => matches(f.properties)); }
function message(text) { $('map-message').textContent = text; $('map-message').hidden = !text; }
function fitBounds(bounds) {
  if (!bounds || !bounds.isValid()) return;
  const mobile = map.getSize().x <= 720;
  map.fitBounds(bounds, {paddingTopLeft: mobile ? [30, 120] : [map.getSize().x <= 1000 ? 282 : 322, 135],
                        paddingBottomRight: [35, 45], maxZoom: 12, animate: false});
}
function fitBase() {
  const bounds = L.latLngBounds([]);
  activeFeatures().forEach(f => bounds.extend(cityLayers.get(String(f.properties.id)).getBounds()));
  if (bounds.isValid()) fitBounds(bounds);
  else if (selectedState && stateLayers.has(selectedState)) fitBounds(stateLayers.get(selectedState).getBounds());
  else fitBounds(stateContext.getBounds());
}
function styleCity(f) {
  const active = matches(f.properties), selected = String(f.properties.id) === selectedCity;
  return {color: selected ? '#122c39' : active ? '#ffffff' : '#c4ced2',
          weight: selected ? 2.8 : active ? 1.15 : .6,
          fillColor: active ? f.properties.cor : '#cbd5d9',
          fillOpacity: active ? (geographic ? .72 : .98) : .20};
}
function styleState(f) {
  const uf = f.properties.uf;
  const inBase = baseStates.has(uf);
  return {color: uf === selectedState ? '#174f62' : '#a5b4c4',
          weight: uf === selectedState ? 2.5 : inBase ? 1.4 : .8,
          fillColor: '#e9eff5', fillOpacity: geographic ? 0 : .86};
}
function renderEmphasis() {
  emphasis.clearLayers();
  const feature = hoveredFeature || (selectedCity ? byId.get(selectedCity) : null);
  if (!feature) return;
  const isCity = Boolean(feature.properties.regiao);
  const addSurface = (className, style) => {
    const surface = L.geoJSON(feature, {interactive: false, renderer: emphasisRenderer,
      pane: 'territory-emphasis', style}).addTo(emphasis);
    surface.eachLayer(layer => {
      const path = layer.getElement();
      path.classList.add(className);
      path.classList.toggle('is-hovered', Boolean(hoveredFeature));
      path.setAttribute('data-territory-id', String(feature.properties.id || feature.properties.uf));
      path.setAttribute('aria-hidden', 'true');
    });
  };
  addSurface('territory-wall', {fill: isCity, fillColor: '#273e59', fillOpacity: .85,
    color: '#273e59', weight: isCity ? 1.6 : 3.2});
  addSurface('territory-face', {fill: isCity, fillColor: feature.properties.cor || '#bccbdd',
    fillOpacity: 1, color: isCity ? '#ffffff' : '#284d70', weight: isCity ? 1.8 : 2.1});
}
function hoverTerritory(feature) { hoveredFeature = feature; renderEmphasis(); }
function leaveTerritory(feature) {
  if (hoveredFeature === feature) { hoveredFeature = null; renderEmphasis(); }
}
function closeDetail() {
  selectedCity = null; $('detail-panel').hidden = true;
}
function updateRegions() {
  const regions = [...new Set(all.filter(f => !selectedState || f.properties.uf === selectedState)
    .map(f => f.properties.regiao))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  if (selectedRegion && !regions.includes(selectedRegion)) selectedRegion = '';
  $('region-filter').replaceChildren(node('option', 'Todas as regiões'));
  $('region-filter').firstChild.value = '';
  regions.forEach(r => { const o = node('option', r); o.value = r; $('region-filter').append(o); });
  $('region-filter').value = selectedRegion;
}
function setFilters(uf, region, zoom = true) {
  selectedState = uf; selectedRegion = region; closeDetail();
  $('state-filter').value = uf; updateRegions(); refresh();
  if (zoom) fitBase();
}
function renderStats(active) {
  const municipalities = active.length, regions = new Set(active.map(f => f.properties.regiao)).size;
  const ufs = new Set(active.map(f => f.properties.uf)).size;
  const stats = [[municipalities, municipalities === 1 ? 'município' : 'municípios'],
    [regions, regions === 1 ? 'região' : 'regiões'], [ufs, ufs === 1 ? 'estado' : 'estados']];
  if (config.temPdvs) {
    const known = active.filter(f => f.properties.pdvs !== null);
    const total = known.reduce((sum, f) => sum + f.properties.pdvs, 0);
    stats.push([total, known.length === municipalities ? 'PDVs informados' : 'PDVs · soma parcial']);
  }
  $('stats').replaceChildren(...stats.map(([value, label]) => {
    const stat = node('div', undefined, 'map-stat'); stat.append(node('strong', fmt(value)), node('span', label)); return stat;
  }));
  $('filter-badge').textContent = selectedRegion ? 'Região selecionada' : selectedState ? selectedState : 'Base completa';
}
function renderLegend() {
  const counts = new Map();
  all.filter(f => !selectedState || f.properties.uf === selectedState).forEach(f => {
    const r = f.properties.regiao; counts.set(r, (counts.get(r) || 0) + 1);
  });
  $('region-legend').replaceChildren(...[...counts].sort(([a], [b]) => a.localeCompare(b, 'pt-BR')).map(([r, count]) => {
    const el = button('', () => setFilters(selectedState, selectedRegion === r ? '' : r),
      'region-item' + (selectedRegion && selectedRegion !== r ? ' dimmed' : ''));
    el.setAttribute('aria-pressed', String(selectedRegion === r));
    const swatch = node('span', undefined, 'swatch'); swatch.style.background = regionColors.get(r);
    el.append(swatch, node('span', r), node('b', fmt(count))); return el;
  }));
  if (!counts.size) $('region-legend').append(node('p', 'Nenhum município da base neste estado.', 'small'));
}
function renderBreadcrumb() {
  const nav = $('map-breadcrumb'); nav.replaceChildren();
  const crumb = (label, action) => {
    if (nav.children.length) nav.append(node('span', '›'));
    nav.append(button(label, action));
  };
  crumb('Brasil', () => { setFilters('', '', false); fitBounds(stateContext.getBounds()); });
  if (selectedState) crumb(selectedState, () => setFilters(selectedState, ''));
  if (selectedRegion) crumb(selectedRegion, () => setFilters(selectedState, selectedRegion));
  if (selectedCity) {
    const f = byId.get(selectedCity); const current = node('span', f.properties.name, 'crumb-current');
    nav.append(node('span', '›'), current);
  }
}
function showCity(id) {
  const f = byId.get(String(id)); if (!f) return;
  const p = f.properties;
  // Uma busca pode navegar para fora do filtro atual, mantendo a UI coerente.
  selectedState = p.uf; selectedRegion = p.regiao; selectedCity = String(id);
  $('state-filter').value = selectedState; updateRegions(); refresh();
  $('detail-title').textContent = p.name;
  const fields = [['UF', p.uf], ['Região', p.regiao], ['Código IBGE', /^\d{7}$/.test(p.id) ? p.id : 'Não informado']];
  if (config.temPdvs) fields.push(['PDVs identificados', p.pdvs === null ? 'Não informado' : fmt(p.pdvs)]);
  $('detail-fields').replaceChildren(...fields.flatMap(([label, value]) => [node('dt', label), node('dd', value)]));
  $('detail-panel').hidden = false;
  fitBounds(cityLayers.get(String(id)).getBounds());
  if (map.getSize().x <= 720) {
    $('map-panel').classList.add('collapsed'); $('panel-toggle').textContent = 'Abrir painel';
    $('panel-toggle').setAttribute('aria-expanded', 'false');
  }
}

// Uma coleção por camada, em vez de milhares de objetos Folium individuais.
const stateContext = L.geoJSON(states, {style: styleState, onEachFeature: (f, layer) => {
  const uf = f.properties.uf; stateLayers.set(uf, layer);
  layer.bindTooltip(node('span', uf), {sticky: true});
  layer.on('click', () => setFilters(uf, ''));
  layer.on('mouseover', () => hoverTerritory(f));
  layer.on('mouseout', () => leaveTerritory(f));
}}).addTo(map);
const municipalities = L.geoJSON(features, {style: styleCity, onEachFeature: (f, layer) => {
  const p = f.properties; cityLayers.set(String(p.id), layer);
  const tooltip = node('div', undefined, 'map-tooltip');
  tooltip.append(node('strong', p.name + ' · ' + p.uf), node('span', 'Região: ' + p.regiao));
  if (config.temPdvs) tooltip.append(node('div', p.pdvs === null ? 'PDVs não informados' : fmt(p.pdvs) + ' PDVs'));
  layer.bindTooltip(tooltip, {sticky: true});
  layer.on('click', () => showCity(p.id));
  layer.on('mouseover', () => hoverTerritory(f));
  layer.on('mouseout', () => leaveTerritory(f));
}}).addTo(map);
const labels = L.layerGroup().addTo(map), pdvMarkers = L.layerGroup().addTo(map);
const centers = new Map();
all.forEach(f => {
  // Ponto representativo interior pré-calculado; não é endereço de PDV.
  const p = f.properties; centers.set(String(p.id), p.centro || cityLayers.get(String(p.id)).getBounds().getCenter());
});
function markerSize(zoom) { return Math.round(Math.max(14, Math.min(24, 14 + 3 * (zoom - 7)))); }
function renderMapAnnotations() {
  labels.clearLayers(); pdvMarkers.clearLayers();
  const zoom = map.getZoom(), bounds = map.getBounds(), size = markerSize(zoom);
  const active = activeFeatures();
  active.forEach(f => {
    const p = f.properties, point = centers.get(String(p.id));
    if (!bounds.pad(.15).contains(point)) return;
    if (config.temPdvs && $('show-pdvs').checked && p.pdvs > 0) {
      const bubble = node('div', fmt(p.pdvs), 'pdv-bubble'); bubble.style.fontSize = (size < 18 ? 8 : 10) + 'px';
      const marker = L.marker(point, {icon: L.divIcon({className: 'pdv-icon', html: bubble,
        iconSize: [size, size], iconAnchor: [size/2, size/2]})}).addTo(pdvMarkers);
      marker.bindTooltip(node('span', p.name + ': ' + fmt(p.pdvs) + ' PDVs'));
      marker.on('click', () => showCity(p.id));
      marker.on('mouseover', () => hoverTerritory(f));
      marker.on('mouseout', () => leaveTerritory(f));
    }
    if ($('show-names').checked && zoom >= 8) {
      L.circleMarker(point, {radius: 0, stroke: false, fill: false, interactive: false})
        .bindTooltip(node('span', p.name), {permanent: true, direction: 'bottom', className: 'territorio-nome',
          offset: [0, config.temPdvs && $('show-pdvs').checked && p.pdvs > 0 ? size/2 : 0]}).addTo(labels);
    }
  });
}
function refresh() {
  hoveredFeature = null;
  municipalities.setStyle(styleCity); stateContext.setStyle(styleState);
  renderEmphasis();
  renderStats(activeFeatures()); renderLegend(); renderBreadcrumb(); renderMapAnnotations();
  renderSearch();
}
function renderSearch() {
  const query = normalize($('city-search').value.trim());
  const el = $('search-results'), status = $('search-status'); el.replaceChildren();
  el.hidden = !query; status.hidden = !query;
  if (!query) return;
  const found = all.filter(f => normalize(f.properties.name + ' ' + f.properties.uf).includes(query));
  found.slice(0, 25).forEach(f => {
    const p = f.properties, li = node('li');
    li.append(button(p.name + ' · ' + p.uf, () => {
      $('city-search').value = ''; renderSearch(); showCity(p.id);
    })); el.append(li);
  });
  status.textContent = found.length ? fmt(found.length) + ' resultado(s)' +
    (found.length > 25 ? ' · exibindo os primeiros 25; refine a busca.' : '') : 'Nenhum município encontrado na base.';
}
function updateBasemap() {
  if (currentTiles) { map.removeLayer(currentTiles); currentTiles = null; }
  geographic = $('view-mode').value === 'geographic'; $('basemap-settings').hidden = !geographic;
  message('');
  if (geographic) {
    const hasWebOrigin = /^https?:$/.test(window.location.protocol) ||
      (window.location.protocol === 'about:' && /^https?:\/\//.test(document.referrer));
    const choice = $('basemap').value;
    currentTiles = basemaps[choice === 'auto' ? (hasWebOrigin ? 'osm' : 'esri') : choice];
    currentTiles.addTo(map);
  }
  municipalities.setStyle(styleCity); stateContext.setStyle(styleState);
  renderEmphasis();
}
Object.values(basemaps).filter(Boolean).forEach(layer => layer.on('tileerror', () => {
  if (currentTiles === layer) message('O mapa geográfico não carregou. A visão territorial e seus dados continuam disponíveis.');
}));

$('map-title').textContent = config.titulo; document.title = config.titulo;
const ufs = states.features.map(f => f.properties.uf).sort();
ufs.forEach(uf => { const o = node('option', uf); o.value = uf; $('state-filter').append(o); });
if (basemaps.carto) { const o = node('option', 'CARTO · chave configurada'); o.value = 'carto'; $('basemap').append(o); }
$('state-filter').onchange = e => setFilters(e.target.value, '');
$('region-filter').onchange = e => setFilters(selectedState, e.target.value);
$('city-search').oninput = renderSearch;
$('city-search').onkeydown = e => {
  if (e.key === 'Escape') { e.target.value = ''; renderSearch(); }
  if (e.key === 'Enter') $('search-results').querySelector('button')?.click();
};
$('show-base').onclick = fitBase;
$('show-brazil').onclick = () => { setFilters('', '', false); fitBounds(stateContext.getBounds()); };
$('clear-filters').onclick = () => setFilters('', '');
$('close-detail').onclick = () => { closeDetail(); refresh(); };
$('focus-city').onclick = () => { if (selectedCity) fitBounds(cityLayers.get(selectedCity).getBounds()); };
$('zoom-in').onclick = () => map.zoomIn(); $('zoom-out').onclick = () => map.zoomOut();
$('recenter').onclick = fitBase; $('show-names').onchange = renderMapAnnotations;
$('show-pdvs').onchange = renderMapAnnotations; $('pdvs-setting').hidden = !config.temPdvs;
$('pdvs-note').hidden = !config.temPdvs;
$('boundaries-setting').hidden = !municipalContext.features.length;
$('show-boundaries').onchange = e => {
  if (e.target.checked) {
    if (!municipalBoundaries) municipalBoundaries = L.geoJSON(municipalContext,
      {interactive: false, style: {fill: false, color: '#7e929c', weight: .4}});
    municipalBoundaries.addTo(map); municipalities.bringToFront();
  } else if (municipalBoundaries) map.removeLayer(municipalBoundaries);
};
$('view-mode').onchange = updateBasemap; $('basemap').onchange = updateBasemap;
function updatePresentation() {
  $('territorios-ui').classList.toggle('presentation', presentation);
  $('presentation').setAttribute('aria-pressed', String(presentation));
  $('presentation').textContent = presentation ? 'Sair da apresentação' : 'Apresentação';
}
$('presentation').onclick = () => { presentation = !presentation; updatePresentation(); };
$('panel-toggle').onclick = () => {
  const collapsed = $('map-panel').classList.toggle('collapsed');
  $('panel-toggle').textContent = collapsed ? 'Abrir painel' : 'Recolher painel';
  $('panel-toggle').setAttribute('aria-expanded', String(!collapsed));
};
$('fullscreen').onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch (error) { message('Tela cheia indisponível nesta prévia. Abra o HTML baixado para apresentar.'); }
};
document.addEventListener('fullscreenchange', () => { map.invalidateSize(); });
map.on('zoomend moveend', () => {
  if (pendingResize) cancelAnimationFrame(pendingResize);
  pendingResize = requestAnimationFrame(renderMapAnnotations);
});
map.on('resize', renderMapAnnotations);
map.on('movestart zoomstart', () => { hoveredFeature = null; renderEmphasis(); });
// Move os controles para dentro do mapa: continuam visíveis em tela cheia.
map.getContainer().append($('territorios-ui'));
L.DomEvent.disableClickPropagation($('territorios-ui'));
L.DomEvent.disableScrollPropagation($('map-panel'));
L.DomEvent.disableScrollPropagation($('detail-panel'));
L.DomEvent.disableScrollPropagation($('map-header'));
updateRegions(); refresh(); updatePresentation();
map.whenReady(() => { map.invalidateSize(); fitBase(); });
