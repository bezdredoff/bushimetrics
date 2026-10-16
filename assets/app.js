const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function safeJson(raw, fallback) {
  try { return JSON.parse(raw); } catch { return fallback; }
}
const state = {
  cards: [], byId: new Map(), printingFamilies: new Map(), sets: [], history: {}, sources: {}, jpMeta: {}, jpLoaded: false, jpLoading: null,
  game: 'weiss', marketLanguage: 'EN', tab: 'market', page: 1, pageSize: 60, filtered: [],
  viewerIndex: 0, viewerList: [], zoom: 1, cardView: localStorage.getItem('bm-card-view') || 'grid',
  watch: new Set(safeJson(localStorage.getItem('bm-watch') || '[]', [])),
  compare: safeJson(localStorage.getItem('bm-compare') || '[]', []).slice(0, 4),
  portfolio: safeJson(localStorage.getItem('bm-portfolio') || '{}', {})
};

const currencyMoney = (v,currency='USD') => v == null || v === '' ? '—' : new Intl.NumberFormat(currency==='EUR'?'de-DE':'en-US', {
  style:'currency', currency, maximumFractionDigits:Number(v)>=100?0:2
}).format(v);
const money = v => currencyMoney(v,'USD');
const euro = v => currencyMoney(v,'EUR');
const observed = c => c.marketEUR != null ? {value:Number(c.marketEUR),currency:'EUR',source:c.priceSourceEUR||'Cardmarket'} :
  (c.market != null ? {value:Number(c.market),currency:'USD',source:c.priceSource||'market'} : null);
const modelFair = c => c.marketEUR != null && c.fairEUR != null ? {value:Number(c.fairEUR),currency:'EUR'} :
  (c.market != null && c.fair != null ? {value:Number(c.fair),currency:'USD'} : null);
const observedLabel = c => { const p=observed(c); if(!p) return '—'; const label=currencyMoney(p.value,p.currency); return c.marketKind==='thin' ? '~'+label : label; };
const fairLabel = c => { const p=modelFair(c); return p ? currencyMoney(p.value,p.currency) : '—'; };
const pct = v => v == null || Number.isNaN(Number(v)) ? '—' : `${Number(v) > 0 ? '+' : ''}${Number(v).toFixed(1)}%`;
const esc = s => String(s ?? '').replace(/[&<>"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const gameLabel = g => g === 'palworld' ? 'Palworld OCG' : 'Weiss Schwarz';
const premium = new Set(['SP','SSP','SEC','SEC+','OFR','AGR','SIR','RRR+','SSS','TSP','TSR','OSR','SR']);

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 2200);
}

function enrichCard(c) {
  const primary = observed(c);
  const fairPrimary = modelFair(c);
  return {
    ...c,
    gap: primary && fairPrimary && primary.currency===fairPrimary.currency ? (fairPrimary.value / primary.value - 1) * 100 : null,
    investment: Number(c.investment ?? 0),
    momentum: Number(c.momentum ?? 50)
  };
}

async function load() {
  const [catalog, history, sources, jpMeta] = await Promise.all([
    fetch('data/catalog.json', {cache:'no-cache'}).then(r => {
      if (!r.ok) throw new Error('catalog.json ' + r.status);
      return r.json();
    }),
    fetch('data/history.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/sources.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/catalog-weiss-jp-meta.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({}))
  ]);
  state.cards = (catalog.cards || []).map(enrichCard);
  state.jpMeta = jpMeta || {};
  state.sets = [...(catalog.sets || []), ...((jpMeta && jpMeta.sets) || [])];
  state.history = history;
  state.sources = sources;
  rebuildCardIndexes();

  const counts = catalog.counts || {};
  const jpCounts = (jpMeta && jpMeta.counts) || {};
  const totalReleased = Number(counts.released || state.cards.length) + Number(jpCounts.released || 0);
  $('#globalStatus').textContent = `${totalReleased.toLocaleString()} released`;
  updateCatalogStatus(catalog.generatedAt);

  initFilters();
  renderAll();
  restoreDeepLink();
}

function rebuildCardIndexes() {
  state.byId = new Map(state.cards.map(c => [c.id, c]));
  state.printingFamilies = new Map();
  for (const c of state.cards) {
    const key = [c.game,c.language||'EN',c.set||'',String(c.name||'').trim().toLowerCase()].join('|');
    if (!state.printingFamilies.has(key)) state.printingFamilies.set(key,[]);
    state.printingFamilies.get(key).push(c);
  }
  for (const family of state.printingFamilies.values()) {
    family.sort((a,b)=>(Number(b.rarityRank)||0)-(Number(a.rarityRank)||0) || (a.code||'').localeCompare(b.code||''));
  }
}

function updateCatalogStatus(generatedAt=null) {
  const jpAvailable=Number(state.jpMeta?.counts?.total||0);
  const loaded=state.cards.length;
  const jpText=jpAvailable ? (state.jpLoaded ? ' · JP loaded' : ` · +${jpAvailable.toLocaleString()} JP on demand`) : '';
  $('#catalogStatus').textContent =
    `${loaded.toLocaleString()} loaded printings${jpText} · ${state.sets.length.toLocaleString()} set/language groups` +
    (generatedAt ? ` · updated ${new Date(generatedAt).toLocaleString()}` : '');
}

async function ensureJPCatalog() {
  if (state.jpLoaded) return true;
  if (state.jpLoading) return state.jpLoading;
  state.jpLoading=(async()=>{
    toast('Loading Japanese Weiss catalog…');
    const r=await fetch('data/catalog-weiss-jp.json',{cache:'no-cache'});
    if(!r.ok) throw new Error('JP catalog '+r.status);
    const jp=await r.json();
    const incoming=(jp.cards||[]).map(enrichCard);
    state.cards.push(...incoming);
    state.jpLoaded=true;
    rebuildCardIndexes();
    initRarityOptions();
    updateCatalogStatus();
    toast(`Loaded ${incoming.length.toLocaleString()} Japanese printings.`);
    return true;
  })().catch(e=>{console.error(e);toast('Japanese catalog is not published yet.');return false;}).finally(()=>{state.jpLoading=null;});
  return state.jpLoading;
}

function initFilters() {
  initRarityOptions();
  updateSetOptions();
  $('#gridViewBtn').classList.toggle('active', state.cardView === 'grid');
  $('#tableViewBtn').classList.toggle('active', state.cardView === 'table');
}
function initRarityOptions() {
  const current=$('#rarityFilter').value;
  const rarities = [...new Set(state.cards.map(c => c.rarity).filter(Boolean))].sort((a,b) => a.localeCompare(b));
  $('#rarityFilter').innerHTML = '<option value="all">All rarities</option>' +
    rarities.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  if(rarities.includes(current)) $('#rarityFilter').value=current;
}

function updateSetOptions() {
  const game = $('#gameFilter').value;
  const language = $('#languageFilter').value;
  const current = $('#setFilter').value;
  const sourceSets = state.sets
    .filter(s => (game === 'all' || s.game === game) && (language === 'all' || (s.language||'EN') === language))
    .map(s=>s.name).filter(Boolean);
  const sets = [...new Set(sourceSets)].sort((a,b) => a.localeCompare(b));
  $('#setFilter').innerHTML = '<option value="all">All sets</option>' +
    sets.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  if (sets.includes(current)) $('#setFilter').value = current;
}

function goto(tab) {
  state.tab = tab;
  $$('.view').forEach(v => v.classList.toggle('active', v.id === tab));
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  if (tab === 'portfolio') renderPortfolio();
  if (tab === 'compare') renderCompare();
  if (tab === 'sets') renderSets();
}
$$('#tabs button').forEach(b => b.onclick = () => goto(b.dataset.tab));
$$('[data-go]').forEach(b => b.onclick = () => goto(b.dataset.go));
$('#themeBtn').onclick = () => document.body.classList.toggle('light');

$('#gameSeg button').forEach(b => b.onclick = async () => {
  state.game = b.dataset.game;
  $('#gameSeg button').forEach(x => x.classList.toggle('active', x === b));
  const lang=$('#marketLanguage');
  if(state.game==='palworld'){ state.marketLanguage='EN'; lang.value='EN'; lang.disabled=true; }
  else { lang.disabled=false; state.marketLanguage=lang.value; if(state.marketLanguage==='JP') await ensureJPCatalog(); }
  renderMarket();
});
$('#marketLanguage').addEventListener('change', async e => {
  state.marketLanguage=e.target.value;
  if(state.marketLanguage==='JP') await ensureJPCatalog();
  renderMarket();
});

function opportunityTable(rows, compact=false) {
  if (!rows.length) return '<div class="empty-state">No priced cards match this view yet. Catalog data is still fully available in Card Explorer.</div>';
  return `<div class="table-scroll"><table><thead><tr>
    <th>Card</th><th>Rarity</th><th>Market</th>${compact ? '' : '<th>Model fair</th><th>Gap</th><th>30d</th>'}<th>IQ</th>
  </tr></thead><tbody>${rows.map(c => `<tr class="click-row" data-id="${esc(c.id)}">
    <td><div class="mini-card">${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}<div><b>${esc(c.name)}</b><br><small>${esc(c.set || '')}</small></div></div></td>
    <td><span class="badge">${esc(c.rarity || '—')}</span></td>
    <td class="price">${observedLabel(c)}</td>
    ${compact ? '' : `<td>${fairLabel(c)}</td><td class="${(c.gap || 0) >= 0 ? 'pos':'neg'}">${pct(c.gap)}</td><td class="${(c.change30d || 0) >= 0 ? 'pos':'neg'}">${pct(c.change30d)}</td>`}
    <td><b>${c.investment}</b></td>
  </tr>`).join('')}</tbody></table></div>`;
}

function bindRows(root) {
  $$(root + ' [data-id]').forEach(el => el.onclick = () => openViewer(el.dataset.id));
}

function renderMarket() {
  const cards = state.cards.filter(c => c.game === state.game && (c.language||'EN') === state.marketLanguage && c.availability === 'released');
  const priced = cards.filter(c => observed(c)); 
  const pricedEUR = cards.filter(c => c.marketEUR != null);
  const pricedUSD = cards.filter(c => c.market != null);
  const premiumCards = cards.filter(c => c.isPremium || premium.has(c.rarity));
  const imaged = cards.filter(c => c.image).length;
  const with30 = priced.filter(c => c.change30d != null);
  const avg30 = with30.length ? with30.reduce((a,c) => a + Number(c.change30d), 0) / with30.length : null;

  $('#marketCards').innerHTML = [
    ['Catalog', cards.length.toLocaleString(), 'released printings'],
    ['Premium', premiumCards.length.toLocaleString(), 'SR / SP / SSP / SEC / etc.'],
    ['Priced', priced.length.toLocaleString(), `${Math.round(priced.length / Math.max(1,cards.length) * 100)}% any-currency coverage · € ${pricedEUR.length.toLocaleString()} / $ ${pricedUSD.length.toLocaleString()}`],
    ['30d pulse', avg30 == null ? '—' : pct(avg30), with30.length ? `${with30.length} cards with 30d data` : 'price history pending']
  ].map(([l,v,d]) => `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${d}</div></div>`).join('');

  const opportunities = priced.filter(c => c.fair).sort((a,b) => (b.gap ?? -999) - (a.gap ?? -999)).slice(0,12);
  $('#opportunityTable').innerHTML = opportunityTable(opportunities);
  bindRows('#opportunityTable');

  const conviction = premiumCards.slice().sort((a,b) => b.investment - a.investment || (b.market||0)-(a.market||0)).slice(0,12);
  $('#convictionTable').innerHTML = opportunityTable(conviction, true);
  bindRows('#convictionTable');

  const pressure = cards.filter(c => c.demandPressure != null).sort((a,b)=>(b.marketHeatPercentile??-1)-(a.marketHeatPercentile??-1)).slice(0,15);
  $('#pressureTable').innerHTML = pressure.length ? `<div class="table-scroll"><table><thead><tr><th>Card</th><th>Rarity</th><th>Sales</th><th>Fresh asks</th><th>Pressure</th><th>Heat</th></tr></thead><tbody>${pressure.map(c=>`<tr class="click-row" data-id="${esc(c.id)}"><td><div class="mini-card">${c.image?`<img src="${esc(c.image)}" loading="lazy">`:''}<div><b>${esc(c.name)}</b><br><small>${esc(c.set||'')}</small></div></div></td><td><span class="badge">${esc(c.rarity||'—')}</span></td><td>${c.demandPressureSales??'—'}</td><td>${c.demandPressureAsks??'—'}</td><td><b>${c.demandPressure.toFixed(1)}%</b></td><td><span class="badge">${esc(c.marketHeatLabel||'—')} · P${c.marketHeatPercentile??'—'}</span></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty-state">No sales + asks pressure data for this game yet.</div>';
  bindRows('#pressureTable');

  const announced = state.cards.filter(c => c.game === state.game && (c.language||'EN') === state.marketLanguage && c.availability !== 'released').length;
  const marketFresh = priced.filter(c => c.marketAsOf || c.cardmarketAsOf).length;
  $('#dataHealth').innerHTML = [
    ['Image coverage', `${Math.round(imaged / Math.max(1,cards.length)*100)}%`, `${imaged.toLocaleString()} / ${cards.length.toLocaleString()}`],
    ['Price coverage', `${Math.round(priced.length / Math.max(1,cards.length)*100)}%`, `€ ${pricedEUR.length.toLocaleString()} · $ ${pricedUSD.length.toLocaleString()}`],
    ['Dated prices', marketFresh.toLocaleString(), 'marketAsOf supplied'],
    ['Pressure coverage', cards.filter(c=>c.demandPressure!=null).length.toLocaleString(), 'sales + fresh asks'],
    ['Announced', announced.toLocaleString(), 'kept separate from released']
  ].map(([a,b,c]) => `<div class="health-card"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
}

function matchesSignal(c, signal) {
  if (signal === 'all') return true;
  if (signal === 'undervalued') return c.gap != null && c.gap >= 15 && c.investment >= 65 && ['High','Medium'].includes(c.fairValueConfidence) && !['Low','NONE','None'].includes(c.confidence);
  if (signal === 'conviction') return c.investment >= 80 && (c.isPremium || premium.has(c.rarity));
  if (signal === 'hot') return Number(c.marketHeatPercentile) >= 80;
  if (signal === 'character') return Number(c.characterPremiumIndex) >= 150 && Number(c.characterPremiumObservations) >= 2;
  if (signal === 'thin') return c.marketKind === 'thin' || String(c.marketConfidence||'').toUpperCase() === 'LOW';
  return true;
}

function signalBadges(c) {
  const out=[];
  if (matchesSignal(c,'undervalued')) out.push('<span class="signal signal-value">VALUE</span>');
  if (matchesSignal(c,'conviction')) out.push('<span class="signal signal-iq">HIGH IQ</span>');
  if (matchesSignal(c,'hot')) out.push('<span class="signal signal-hot">HOT</span>');
  if (matchesSignal(c,'character')) out.push('<span class="signal signal-char">CHAR+</span>');
  if (matchesSignal(c,'thin')) out.push('<span class="signal signal-risk">THIN</span>');
  return out.join('');
}

function applyFilters() {
  const q = $('#search').value.trim().toLowerCase();
  const gf = $('#gameFilter').value;
  const lf = $('#languageFilter').value;
  const sf = $('#setFilter').value;
  const rf = $('#rarityFilter').value;
  const af = $('#availabilityFilter').value;
  const signal = $('#signalFilter').value;
  const prem = $('#premiumOnly').checked;
  const priced = $('#pricedOnly').checked;

  let a = state.cards.filter(c =>
    (gf === 'all' || c.game === gf) &&
    (lf === 'all' || (c.language||'EN') === lf) &&
    (sf === 'all' || c.set === sf) &&
    (rf === 'all' || c.rarity === rf) &&
    (af === 'all' || c.availability === af) &&
    matchesSignal(c, signal) &&
    (!prem || c.isPremium || premium.has(c.rarity)) &&
    (!priced || !!observed(c)) &&
    (!q || [c.name,c.set,c.code,c.rarity,c.cardType,c.color].join(' ').toLowerCase().includes(q))
  );

  const sort = $('#sort').value;
  if (sort === 'name') a.sort((x,y) => (x.name||'').localeCompare(y.name||''));
  else {
    const key = {market:'market',gap:'gap',investment:'investment',momentum:'momentum',heat:'marketHeatPercentile'}[sort.split('-')[0]];
    a.sort((x,y) => (Number(y[key]) || -Infinity) - (Number(x[key]) || -Infinity));
  }

  state.filtered = a;
  const pages = Math.max(1, Math.ceil(a.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  renderCards();
}

['setFilter','rarityFilter','availabilityFilter','signalFilter','sort','premiumOnly','pricedOnly'].forEach(id =>
  $('#'+id).addEventListener('change', () => { state.page = 1; applyFilters(); })
);
let searchTimer=null;
$('#search').addEventListener('input',()=>{ clearTimeout(searchTimer); searchTimer=setTimeout(()=>{state.page=1;applyFilters();},120); });
$('#languageFilter').addEventListener('change', async () => {
  const lang=$('#languageFilter').value;
  if(lang==='JP' || lang==='all') await ensureJPCatalog();
  updateSetOptions(); state.page=1; applyFilters();
});
$('#gameFilter').addEventListener('change', async () => {
  if($('#gameFilter').value==='palworld' && $('#languageFilter').value==='JP') $('#languageFilter').value='EN';
  if($('#languageFilter').value==='JP' || $('#languageFilter').value==='all') await ensureJPCatalog();
  updateSetOptions(); state.page = 1; applyFilters();
});
$('#resetFiltersBtn').onclick = () => {
  $('#search').value=''; $('#gameFilter').value='all'; $('#languageFilter').value='EN'; updateSetOptions(); $('#setFilter').value='all';
  $('#rarityFilter').value='all'; $('#availabilityFilter').value='released'; $('#signalFilter').value='all';
  $('#sort').value='investment-desc'; $('#premiumOnly').checked=false; $('#pricedOnly').checked=false;
  state.page=1; applyFilters();
};

function cardImage(c, cls='') {
  return c.image
    ? `<img class="${cls}" src="${esc(c.image)}" loading="lazy" alt="${esc(c.name)}">`
    : `<div class="placeholder">${esc(c.rarity || 'Card')}<br><small>preview pending</small></div>`;
}

function renderCards() {
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  const start = (state.page - 1) * state.pageSize;
  const rows = state.filtered.slice(start, start + state.pageSize);

  $('#cardGrid').innerHTML = rows.map(c => `<article class="card-tile" data-id="${esc(c.id)}">
    <div class="card-img">${cardImage(c)}</div>
    <div class="card-body">
      <div class="card-title">${esc(c.name)}</div>
      <div class="card-meta">${esc(c.set || '')} · ${esc(c.code || '')}</div>
      <div class="card-row"><span class="badge">${esc(c.rarity || '—')}</span><span class="price">${observedLabel(c)}</span></div>
      <div class="card-row"><span class="${c.gap == null ? '' : c.gap >= 0 ? 'pos':'neg'}">gap ${pct(c.gap)}</span><span>IQ ${c.investment}</span></div>
      <div class="signal-row">${signalBadges(c)}</div>
      ${c.availability !== 'released' ? '<div class="announced-ribbon">ANNOUNCED</div>' : ''}
    </div>
  </article>`).join('');

  $('#cardTable').innerHTML = `<div class="table-scroll"><table><thead><tr><th>Card</th><th>Set</th><th>No.</th><th>Rarity</th><th>Market</th><th>Gap</th><th>Signals</th><th>Momentum</th><th>IQ</th></tr></thead>
  <tbody>${rows.map(c => `<tr class="click-row" data-id="${esc(c.id)}">
    <td><div class="mini-card">${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}<b>${esc(c.name)}</b></div></td>
    <td>${esc(c.set || '')}</td><td><code>${esc(c.code || '')}</code></td><td><span class="badge">${esc(c.rarity || '—')}</span></td>
    <td>${observedLabel(c)}</td><td>${pct(c.gap)}</td><td><div class="signal-row">${signalBadges(c)}</div></td><td>${c.momentum}</td><td><b>${c.investment}</b></td>
  </tr>`).join('')}</tbody></table></div>`;

  const isGrid = state.cardView === 'grid';
  $('#cardGrid').classList.toggle('hidden', !isGrid);
  $('#cardTable').classList.toggle('hidden', isGrid);
  $$('#cardGrid [data-id], #cardTable [data-id]').forEach(el => el.onclick = () => openViewer(el.dataset.id));

  $('#pageInfo').textContent = `${state.page} / ${pages} · ${state.filtered.length.toLocaleString()} cards`;
  renderWatch();
}

$('#gridViewBtn').onclick = () => setCardView('grid');
$('#tableViewBtn').onclick = () => setCardView('table');
function setCardView(view) {
  state.cardView = view; localStorage.setItem('bm-card-view',view);
  $('#gridViewBtn').classList.toggle('active', view === 'grid');
  $('#tableViewBtn').classList.toggle('active', view === 'table');
  renderCards();
}
$('#prevPage').onclick = () => { if (state.page > 1) { state.page--; renderCards(); window.scrollTo({top:100,behavior:'smooth'}); } };
$('#nextPage').onclick = () => { if (state.page < Math.ceil(state.filtered.length/state.pageSize)) { state.page++; renderCards(); window.scrollTo({top:100,behavior:'smooth'}); } };

function renderSets() {
  const q = $('#setSearch').value.trim().toLowerCase();
  const game = $('#setGameFilter').value;
  const language = $('#setLanguageFilter').value;
  let a = state.sets.filter(s =>
    (game === 'all' || s.game === game) &&
    (language === 'all' || (s.language||'EN') === language) &&
    (!q || s.name.toLowerCase().includes(q))
  );
  const sort = $('#setSort').value;
  if (sort === 'name') a.sort((x,y) => x.name.localeCompare(y.name));
  else {
    const key = {premium:'premium',total:'total',investment:'avgInvestment',coverage:'priceCoverage'}[sort.split('-')[0]];
    a.sort((x,y) => (Number(y[key])||0)-(Number(x[key])||0));
  }
  $('#setGrid').innerHTML = a.map(s => `<article class="set-card" data-set="${esc(s.name)}" data-game="${esc(s.game)}" data-language="${esc(s.language||'EN')}">
    <div class="set-card-top"><span class="eyebrow">${esc(gameLabel(s.game))} · ${esc(s.language||'EN')}</span><span class="badge">${s.released} released${s.announced ? ` + ${s.announced} announced` : ''}</span></div>
    <h3>${esc(s.name)}</h3>
    <div class="set-stats">
      <div><b>${s.premium}</b><span>premium</span></div>
      <div><b>${s.priceCoverage}%</b><span>priced</span></div>
      <div><b>${s.imageCoverage}%</b><span>images</span></div>
      <div><b>${s.avgInvestment ?? '—'}</b><span>avg IQ</span></div>
    </div>
    <div class="progress"><i style="width:${Math.min(100,s.priceCoverage)}%"></i></div>
  </article>`).join('') || '<div class="empty-state">No sets match.</div>';

  $$('#setGrid [data-set]').forEach(el => el.onclick = async () => {
    const lang=el.dataset.language||'EN';
    if(lang==='JP') await ensureJPCatalog();
    $('#gameFilter').value = el.dataset.game;
    $('#languageFilter').value = lang;
    updateSetOptions();
    $('#setFilter').value = el.dataset.set;
    $('#availabilityFilter').value = 'released';
    state.page = 1; applyFilters(); goto('cards');
  });
}
['setSearch','setGameFilter','setLanguageFilter','setSort'].forEach(id =>
  $('#'+id).addEventListener(id === 'setSearch' ? 'input' : 'change', renderSets)
);

function openViewer(id) {
  const c = state.byId.get(id);
  if (!c) return;
  state.viewerList = state.filtered.length && state.filtered.some(x => x.id === id) ? state.filtered : state.cards;
  state.viewerIndex = Math.max(0, state.viewerList.findIndex(x => x.id === id));
  renderViewer();
  $('#viewer').classList.add('open');
  $('#viewer').setAttribute('aria-hidden','false');
  document.body.style.overflow = 'hidden';
  history.replaceState(null,'',`#card=${encodeURIComponent(id)}`);
}

function renderViewer() {
  const c = state.viewerList[state.viewerIndex];
  if (!c) return;
  state.zoom = 1;
  $('#viewerImageWrap').style.setProperty('--zoom','1');
  $('#zoomLabel').textContent = '100%';

  $('#viewerImage').style.display = c.image ? 'block' : 'none';
  $('#viewerPlaceholder').classList.toggle('hidden', !!c.image);
  if (c.image) $('#viewerImage').src = c.image;

  $('#viewerGame').textContent = gameLabel(c.game);
  $('#viewerName').textContent = c.name;
  $('#viewerMeta').textContent = [c.set,c.code,c.rarity,c.edition,c.treatment].filter(Boolean).join(' · ');
  $('#viewerBadges').innerHTML = [
    c.availability !== 'released' ? '<span class="badge badge-warn">Announced</span>' : '<span class="badge">Released</span>',
    c.isPremium ? '<span class="badge badge-accent">Premium</span>' : '',
    !c.market ? '<span class="badge">Market pending</span>' : ''
  ].join('');

  const familyKey=[c.game,c.language||'EN',c.set||'',String(c.name||'').trim().toLowerCase()].join('|');
  const family=state.printingFamilies.get(familyKey)||[c];
  $('#printingFamilyCount').textContent=family.length + (family.length===1?' printing':' printings');
  $('#printingFamily').innerHTML=family.map(x => `<button class="printing-chip ${x.id===c.id?'active':''}" data-family-id="${esc(x.id)}" title="${esc(x.code||'')}">
    ${x.image?`<img src="${esc(x.image)}" loading="lazy" alt="">`:''}
    <span><b>${esc(x.rarity||'—')}</b><small>${esc(x.code||'')}</small><em>${observedLabel(x)}</em></span>
  </button>`).join('');
  $('#printingFamily [data-family-id]').forEach(btn=>btn.onclick=()=>{
    const target=state.byId.get(btn.dataset.familyId); if(!target)return;
    const idx=state.viewerList.findIndex(x=>x.id===target.id);
    if(idx>=0) state.viewerIndex=idx;
    else { state.viewerList=family; state.viewerIndex=family.findIndex(x=>x.id===target.id); }
    renderViewer(); updateViewerHash();
  });

  $('#viewerStats').innerHTML = [
    ['Cardmarket trend (EUR)',euro(c.marketEUR)],['Cardmarket low (EUR)',euro(c.marketEURLow)],
    ['Cardmarket 7d avg',euro(c.marketEURAvg7)],['Cardmarket 30d avg',euro(c.marketEURAvg30)],
    ['Observed sold market (USD)',c.marketKind==='thin' ? '~'+money(c.market) : money(c.market)],['TCGPlayer low (USD)',money(c.marketLow)],['TCGPlayer median (USD)',money(c.marketMedian)],
    ['Completed-sale sample',c.salesInBasis!=null ? `${c.salesInBasis} sales · ${c.marketBasisWindow||'basis'}` : '—'],['Fresh asks',c.marketAskCount!=null ? `${c.marketAskCount} · low ${money(c.marketAskLow)}${c.marketAskMedian!=null ? ` · median ${money(c.marketAskMedian)}`:''}` : '—'],
    ['Peer fair value',fairLabel(c)],['Fair-value gap',pct(c.gap)],['Fair confidence',c.fairValueConfidence||'None'],['Fair method',c.fairValueMethod||'Insufficient peers'],['7d',pct(c.change7d)],['30d',pct(c.change30d)],
    ['Momentum',`${c.momentum}/100`],['Demand pressure',c.demandPressure!=null?`${c.demandPressure.toFixed(1)}% · ${c.marketHeatLabel||''} P${c.marketHeatPercentile??'—'}`:'N/A'],['Investment quality',`${c.investment}/100`],
    ['Character premium',c.characterPremiumIndex!=null ? `${c.characterPremiumIndex} index · ${c.characterPremiumObservations||0} obs · ${c.characterPremiumConfidence||'Low'}` : 'Not enough peer pricing'],['Fair peers',c.fairValuePeerCount!=null ? `${c.fairValuePeerCount} rarity peers · ${c.fairValueSubjectObservations||0} subject obs` : '—'],
    ['Confidence',c.confidence || 'Low'],
    ['EUR source',c.priceSourceEUR || 'Pending'],['USD source',c.priceSource || 'Pending'],['Price qualifier',c.marketQualifier || (c.marketKind==='bare' ? 'Completed-sale estimate' : '—')]
  ].map(([a,b]) => `<div class="stat"><span>${a}</span><b>${b}</b></div>`).join('');

  const factors = c.modelFactors || {};
  const labels = {
    scarcity:'Structural scarcity',ipStrength:'IP strength',characterPremium:'Character premium',reprintDurability:'Reprint durability',
    historicalSignificance:'Historical significance',treatment:'Treatment premium',
    liquidity:'Liquidity',editionDurability:'Edition durability'
  };
  $('#factorBars').innerHTML = Object.entries(labels).map(([k,label]) => {
    const v = Number(factors[k] ?? 0);
    return `<div class="factor"><div><span>${label}</span><b>${v}</b></div><div class="factor-track"><i style="width:${Math.max(0,Math.min(100,v))}%"></i></div></div>`;
  }).join('') + (c.scarcityEvidence ? `<div class="evidence-note"><b>Scarcity evidence:</b> ~1 in ${c.scarcityEvidence.packsPerHit} packs · n=${Number(c.scarcityEvidence.samplePacks||0).toLocaleString()} · ${esc(c.scarcityEvidence.confidence||'')} confidence ${c.scarcityEvidence.source ? `· <a href="${esc(c.scarcityEvidence.source)}" target="_blank" rel="noreferrer">source</a>` : ''}</div>` : '');

  const p = state.portfolio[c.id] || {qty:0,cost:0,currency:(c.marketEUR!=null?'EUR':'USD')};
  $('#portfolioQty').value = p.qty || 0;
  $('#portfolioCost').value = p.cost || 0;
  $('#portfolioCurrency').value = p.currency || (c.marketEUR!=null?'EUR':'USD');

  const src = c.identitySource || c.source;
  $('#sourceBtn').style.display = src ? 'inline-flex' : 'none';
  if (src) $('#sourceBtn').href = src;
  $('#imageBtn').style.display = c.image ? 'inline-flex' : 'none';
  if (c.image) $('#imageBtn').href = c.image;
  $('#marketSourceBtn').style.display = c.marketSourceUrl ? 'inline-flex' : 'none';
  if (c.marketSourceUrl) $('#marketSourceBtn').href = c.marketSourceUrl;

  $('#watchBtn').textContent = state.watch.has(c.id) ? 'Watching' : 'Watch';
  $('#compareBtn').textContent = state.compare.includes(c.id) ? 'In compare' : 'Compare';

  const lo = Math.max(0,state.viewerIndex-6), hi = Math.min(state.viewerList.length,state.viewerIndex+7);
  $('#thumbStrip').innerHTML = state.viewerList.slice(lo,hi).map((x,i) =>
    x.image ? `<img src="${esc(x.image)}" data-i="${lo+i}" class="${lo+i===state.viewerIndex?'active':''}" title="${esc(x.name)}">` : ''
  ).join('');
  $$('#thumbStrip img').forEach(i => i.onclick = () => { state.viewerIndex = Number(i.dataset.i); renderViewer(); updateViewerHash(); });
}

function updateViewerHash() {
  const c = state.viewerList[state.viewerIndex];
  if (c) history.replaceState(null,'',`#card=${encodeURIComponent(c.id)}`);
}
function closeViewer() {
  $('#viewer').classList.remove('open');
  $('#viewer').setAttribute('aria-hidden','true');
  document.body.style.overflow = '';
  if (location.hash.startsWith('#card=')) history.replaceState(null,'',location.pathname + location.search);
}
$$('[data-close]').forEach(x => x.onclick = closeViewer);

function navViewer(delta) {
  if (!state.viewerList.length) return;
  state.viewerIndex = (state.viewerIndex + delta + state.viewerList.length) % state.viewerList.length;
  renderViewer(); updateViewerHash();
}
$('#viewerPrev').onclick = () => navViewer(-1);
$('#viewerNext').onclick = () => navViewer(1);

function setZoom(z) {
  state.zoom = Math.max(.55,Math.min(3.2,z));
  $('#viewerImageWrap').style.setProperty('--zoom',state.zoom);
  $('#zoomLabel').textContent = `${Math.round(state.zoom*100)}%`;
}
$('#zoomIn').onclick = () => setZoom(state.zoom+.2);
$('#zoomOut').onclick = () => setZoom(state.zoom-.2);
$('#viewerImageWrap').addEventListener('wheel', e => {
  e.preventDefault(); setZoom(state.zoom + (e.deltaY < 0 ? .12 : -.12));
},{passive:false});

document.addEventListener('keydown', e => {
  if (!$('#viewer').classList.contains('open')) return;
  if (e.key === 'Escape') closeViewer();
  if (e.key === 'ArrowLeft') navViewer(-1);
  if (e.key === 'ArrowRight') navViewer(1);
  if (e.key === '+' || e.key === '=') setZoom(state.zoom+.2);
  if (e.key === '-') setZoom(state.zoom-.2);
});

document.addEventListener('error', e => {
  if (e.target && e.target.tagName === 'IMG') {
    e.target.classList.add('broken-image');
    e.target.title = 'Preview unavailable from source';
  }
}, true);

$('#watchBtn').onclick = () => {
  const c = state.viewerList[state.viewerIndex]; if (!c) return;
  state.watch.has(c.id) ? state.watch.delete(c.id) : state.watch.add(c.id);
  localStorage.setItem('bm-watch',JSON.stringify([...state.watch]));
  renderViewer(); renderWatch();
};

$('#compareBtn').onclick = () => {
  const c = state.viewerList[state.viewerIndex]; if (!c) return;
  if (state.compare.includes(c.id)) state.compare = state.compare.filter(x => x !== c.id);
  else if (state.compare.length < 4) state.compare.push(c.id);
  else { state.compare = [...state.compare.slice(1),c.id]; toast('Compare holds four cards; oldest card was replaced.'); }
  persistCompare(); renderViewer(); renderCompare();
};

function persistCompare() {
  localStorage.setItem('bm-compare',JSON.stringify(state.compare));
  $('#compareCount').textContent = state.compare.length;
}

$('#copyLinkBtn').onclick = async () => {
  try { await navigator.clipboard.writeText(location.href); toast('Card link copied.'); }
  catch { toast('Copy unavailable in this browser.'); }
};

$('#savePortfolioBtn').onclick = () => {
  const c = state.viewerList[state.viewerIndex]; if (!c) return;
  const qty = Math.max(0,Math.floor(Number($('#portfolioQty').value)||0));
  const cost = Math.max(0,Number($('#portfolioCost').value)||0);
  const currency = $('#portfolioCurrency').value === 'USD' ? 'USD' : 'EUR';
  if (!qty) delete state.portfolio[c.id];
  else state.portfolio[c.id] = {qty,cost,currency};
  localStorage.setItem('bm-portfolio',JSON.stringify(state.portfolio));
  renderPortfolio(); updatePortfolioCount();
  toast(qty ? 'Portfolio position saved.' : 'Removed from portfolio.');
};

function renderWatch() {
  const a = [...state.watch].map(id => state.byId.get(id)).filter(Boolean);
  $('#watchList').innerHTML = a.length ? a.map(c => `<div class="watch-item" data-id="${esc(c.id)}">
    ${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}
    <div><b>${esc(c.name)}</b><br><small>${observedLabel(c)} · ${esc(c.rarity||'')}</small></div>
  </div>`).join('') : '<p class="muted">No cards watched yet.</p>';
  $$('#watchList [data-id]').forEach(x => x.onclick = () => openViewer(x.dataset.id));
}

function updatePortfolioCount() {
  const count = Object.values(state.portfolio).reduce((a,p) => a + (Number(p.qty)||0),0);
  $('#portfolioCount').textContent = count;
}

function renderPortfolio() {
  const positions = Object.entries(state.portfolio)
    .map(([id,p]) => ({card:state.byId.get(id),qty:Number(p.qty)||0,cost:Number(p.cost)||0,currency:p.currency==='USD'?'USD':'EUR'}))
    .filter(x => x.card && x.qty > 0);
  const qty = positions.reduce((a,x) => a+x.qty,0);
  const totals = {};
  for (const currency of ['EUR','USD']) {
    const group=positions.filter(x=>x.currency===currency);
    const basis=group.reduce((a,x)=>a+x.qty*x.cost,0);
    const priced=group.filter(x=>currency==='EUR' ? x.card.marketEUR!=null : x.card.market!=null);
    const value=priced.reduce((a,x)=>a+x.qty*Number(currency==='EUR'?x.card.marketEUR:x.card.market),0);
    const pricedBasis=priced.reduce((a,x)=>a+x.qty*x.cost,0);
    totals[currency]={basis,value,pnl:value-pricedBasis,priced:priced.length,count:group.length};
  }

  $('#portfolioMetrics').innerHTML = [
    ['Cards owned',qty.toLocaleString(),`${positions.length} positions`],
    ['EUR portfolio',euro(totals.EUR.value),`basis ${euro(totals.EUR.basis)} · P/L ${euro(totals.EUR.pnl)} · ${totals.EUR.priced}/${totals.EUR.count} priced`],
    ['USD portfolio',money(totals.USD.value),`basis ${money(totals.USD.basis)} · P/L ${money(totals.USD.pnl)} · ${totals.USD.priced}/${totals.USD.count} priced`],
    ['Price coverage',positions.length ? `${Math.round((totals.EUR.priced+totals.USD.priced)/positions.length*100)}%` : '—','position-matched in chosen currency']
  ].map(([l,v,d]) => `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${d}</div></div>`).join('');

  $('#portfolioTable').innerHTML = positions.length ? `<div class="table-scroll"><table><thead><tr>
    <th>Card</th><th>Qty</th><th>Avg cost</th><th>Basis</th><th>Market</th><th>Value</th><th>P/L</th><th></th>
  </tr></thead><tbody>${positions.map(x => {
    const m=Number(x.currency==='EUR'?x.card.marketEUR:x.card.market)||0,b=x.qty*x.cost,v=m?x.qty*m:0,p=m?v-b:null;
    const fmt=x.currency==='EUR'?euro:money;
    return `<tr>
      <td class="click-row" data-id="${esc(x.card.id)}"><div class="mini-card">${x.card.image?`<img src="${esc(x.card.image)}" loading="lazy">`:''}<div><b>${esc(x.card.name)}</b><br><small>${esc(x.card.set||'')}</small></div></div></td>
      <td>${x.qty}</td><td>${fmt(x.cost)} <small>${x.currency}</small></td><td>${fmt(b)}</td><td>${fmt(m||null)}</td><td>${m?fmt(v):'—'}</td>
      <td class="${p==null?'':p>=0?'pos':'neg'}">${p==null?'—':fmt(p)}</td>
      <td><button class="ghost remove-position" data-remove="${esc(x.card.id)}">Remove</button></td>
    </tr>`;
  }).join('')}</tbody></table></div>` : '<div class="empty-state">Add a quantity and cost basis from any card preview to start a portfolio.</div>';

  $$('#portfolioTable [data-id]').forEach(x => x.onclick = e => { if (!e.target.closest('button')) openViewer(x.dataset.id); });
  $$('.remove-position').forEach(b => b.onclick = () => {
    delete state.portfolio[b.dataset.remove];
    localStorage.setItem('bm-portfolio',JSON.stringify(state.portfolio));
    renderPortfolio(); updatePortfolioCount();
  });
}

function renderCompare() {
  const a = state.compare.map(id => state.byId.get(id)).filter(Boolean);
  $('#compareCount').textContent = a.length;
  $('#compareGrid').innerHTML = a.length ? a.map(c => `<article class="compare-card">
    ${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}
    <h2>${esc(c.name)}</h2>
    <p>${esc(c.set||'')} · ${esc(c.code||'')} · ${esc(c.rarity||'')}</p>
    <div class="stat-list">
      ${[['Primary market',observedLabel(c)],['Model fair',fairLabel(c)],['Gap',pct(c.gap)],['30d',pct(c.change30d)],['Momentum',c.momentum],['Investment',c.investment],['Confidence',c.confidence||'Low']].map(x=>`<div class="stat"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('')}
    </div>
    <div class="factor-mini">${Object.entries(c.modelFactors||{}).map(([k,v])=>`<span title="${esc(k)}">${Math.round(v)}</span>`).join('')}</div>
    <div class="button-row"><button class="ghost compare-open" data-id="${esc(c.id)}">Preview</button><button class="ghost removeCompare" data-id="${esc(c.id)}">Remove</button></div>
  </article>`).join('') : '<div class="panel"><p>Add up to four cards from Card Explorer or the full-screen preview.</p></div>';

  $$('.compare-open').forEach(b => b.onclick = () => openViewer(b.dataset.id));
  $$('.removeCompare').forEach(b => b.onclick = () => {
    state.compare = state.compare.filter(x => x !== b.dataset.id); persistCompare(); renderCompare();
  });
}

function exportJson(filename,obj) {
  const blob = new Blob([JSON.stringify(obj,null,2)],{type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href),1000);
}

function exportLocal() {
  exportJson('bushimetrics-local-data.json',{
    version:1, exportedAt:new Date().toISOString(),
    watch:[...state.watch], compare:state.compare, portfolio:state.portfolio
  });
}
$('#exportLocalBtn').onclick = exportLocal;
$('#portfolioExportBtn').onclick = () => exportJson('bushimetrics-portfolio.json',{version:1,exportedAt:new Date().toISOString(),portfolio:state.portfolio});
$('#importLocalBtn').onclick = () => $('#importLocalFile').click();
$('#importLocalFile').onchange = async e => {
  const file=e.target.files?.[0]; if(!file)return;
  try {
    const d=JSON.parse(await file.text());
    if (Array.isArray(d.watch)) state.watch=new Set(d.watch);
    if (Array.isArray(d.compare)) state.compare=d.compare.slice(0,4);
    if (d.portfolio && typeof d.portfolio==='object') state.portfolio=d.portfolio;
    localStorage.setItem('bm-watch',JSON.stringify([...state.watch]));
    persistCompare();
    localStorage.setItem('bm-portfolio',JSON.stringify(state.portfolio));
    renderWatch();renderPortfolio();updatePortfolioCount();toast('Local data imported.');
  } catch { toast('Could not import that JSON file.'); }
  e.target.value='';
};

function renderBacktest() {
  const sets=state.history.sets||[];
  $('#backtestContent').innerHTML = `<div class="backtest-grid">${sets.map(s=>`<div class="source-card">
    <p class="eyebrow">${esc(s.game||'Weiss')}</p><h3>${esc(s.name)}</h3>
    <div class="stat-list"><div class="stat"><span>Since first prices</span><b class="${s.sinceFirst>=0?'pos':'neg'}">${pct(s.sinceFirst)}</b></div><div class="stat"><span>30d</span><b>${pct(s.change30d)}</b></div><div class="stat"><span>Current index</span><b>${s.index??'—'}</b></div></div>
  </div>`).join('')}</div>
  <div class="panel"><h3>Walk-forward status</h3><p>${esc(state.history.note || 'Compact daily market snapshots are accumulating. 30/90/180-day model accuracy appears only after the horizon can be evaluated without future leakage.')}</p></div>`;
}

function renderSources() {
  const a=state.sources.sources||[];
  const m=state.sources.methodology||{};
  $('#sourcesContent').innerHTML = `<div class="source-grid">${a.map(s=>`<div class="source-card">
    <p class="eyebrow">${esc(s.role||'source')}</p><h3>${esc(s.name)}</h3><p>${esc(s.description||'')}</p>
    ${s.url?`<a class="ghost" target="_blank" rel="noreferrer" href="${esc(s.url)}">Open source</a>`:''}
  </div>`).join('')}</div>
  <div class="panel methodology-panel">
    <p class="eyebrow">Methodology</p><h2>${esc(m.title||'Investment Quality')}</h2><p>${esc(m.description||'')}</p>
    <div class="method-grid">${(m.factors||[]).map(f=>`<div class="method-card"><div><b>${esc(f.name)}</b><strong>${Number(f.weight)||0}%</strong></div><p>${esc(f.description||'')}</p></div>`).join('')}</div>
    <div class="method-notes"><p><b>Fair Value:</b> ${esc(m.fairValue||'')}</p><p><b>Backtest:</b> ${esc(m.backtest||'')}</p></div>
  </div>
  <div class="panel"><h3>Model boundaries</h3><p>Observed market prices, retailer asks, catalog identity and model outputs remain separate. A missing price stays missing. Fair Value and Investment Quality are research estimates, not guaranteed returns.</p></div>`;
}

function restoreDeepLink() {
  if (!location.hash.startsWith('#card=')) return;
  const id=decodeURIComponent(location.hash.slice(6));
  if (state.byId.has(id)) openViewer(id);
}

function renderAll() {
  renderMarket(); applyFilters(); renderSets(); renderWatch(); renderPortfolio(); renderCompare(); renderBacktest(); renderSources(); updatePortfolioCount(); persistCompare();
}

load().catch(e => {
  $('#catalogStatus').textContent='Failed to load catalog: '+e.message;
  $('#globalStatus').textContent='load failed';
  console.error(e);
});
