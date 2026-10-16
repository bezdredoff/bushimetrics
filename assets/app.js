const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function safeJson(raw, fallback) {
  try { return JSON.parse(raw); } catch { return fallback; }
}
const state = {
  cards: [], byId: new Map(), sets: [], history: {}, sources: {},
  game: 'weiss', tab: 'market', page: 1, pageSize: 60, filtered: [],
  viewerIndex: 0, viewerList: [], zoom: 1, cardView: localStorage.getItem('bm-card-view') || 'grid',
  watch: new Set(safeJson(localStorage.getItem('bm-watch') || '[]', [])),
  compare: safeJson(localStorage.getItem('bm-compare') || '[]', []).slice(0, 4),
  portfolio: safeJson(localStorage.getItem('bm-portfolio') || '{}', {})
};

const money = v => v == null || v === '' ? '—' : new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', maximumFractionDigits: Number(v) >= 100 ? 0 : 2
}).format(v);
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
  const market = Number(c.market) || 0;
  const fair = Number(c.fair) || 0;
  return {
    ...c,
    gap: market && fair ? (fair / market - 1) * 100 : null,
    investment: Number(c.investment ?? 0),
    momentum: Number(c.momentum ?? 50)
  };
}

async function load() {
  const [catalog, history, sources] = await Promise.all([
    fetch('data/catalog.json', {cache:'no-cache'}).then(r => {
      if (!r.ok) throw new Error('catalog.json ' + r.status);
      return r.json();
    }),
    fetch('data/history.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/sources.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({}))
  ]);
  state.cards = (catalog.cards || []).map(enrichCard);
  state.byId = new Map(state.cards.map(c => [c.id, c]));
  state.sets = catalog.sets || [];
  state.history = history;
  state.sources = sources;

  const counts = catalog.counts || {};
  $('#globalStatus').textContent = `${(counts.released || state.cards.length).toLocaleString()} released`;
  $('#catalogStatus').textContent =
    `${state.cards.length.toLocaleString()} printings · ${(counts.sets || state.sets.length).toLocaleString()} sets · ` +
    `${(counts.premium || state.cards.filter(c => c.isPremium).length).toLocaleString()} premium · updated ` +
    (catalog.generatedAt ? new Date(catalog.generatedAt).toLocaleString() : 'unknown');

  initFilters();
  renderAll();
  restoreDeepLink();
}

function initFilters() {
  const rarities = [...new Set(state.cards.map(c => c.rarity).filter(Boolean))].sort((a,b) => a.localeCompare(b));
  $('#rarityFilter').innerHTML = '<option value="all">All rarities</option>' +
    rarities.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  updateSetOptions();

  $('#gridViewBtn').classList.toggle('active', state.cardView === 'grid');
  $('#tableViewBtn').classList.toggle('active', state.cardView === 'table');
}

function updateSetOptions() {
  const game = $('#gameFilter').value;
  const current = $('#setFilter').value;
  const sets = [...new Set(state.cards
    .filter(c => game === 'all' || c.game === game)
    .map(c => c.set).filter(Boolean))]
    .sort((a,b) => a.localeCompare(b));
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

$$('#gameSeg button').forEach(b => b.onclick = () => {
  state.game = b.dataset.game;
  $$('#gameSeg button').forEach(x => x.classList.toggle('active', x === b));
  renderMarket();
});

function opportunityTable(rows, compact=false) {
  if (!rows.length) return '<div class="empty-state">No priced cards match this view yet. Catalog data is still fully available in Card Explorer.</div>';
  return `<div class="table-scroll"><table><thead><tr>
    <th>Card</th><th>Rarity</th><th>Market</th>${compact ? '' : '<th>Model fair</th><th>Gap</th><th>30d</th>'}<th>IQ</th>
  </tr></thead><tbody>${rows.map(c => `<tr class="click-row" data-id="${esc(c.id)}">
    <td><div class="mini-card">${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}<div><b>${esc(c.name)}</b><br><small>${esc(c.set || '')}</small></div></div></td>
    <td><span class="badge">${esc(c.rarity || '—')}</span></td>
    <td class="price">${money(c.market)}</td>
    ${compact ? '' : `<td>${money(c.fair)}</td><td class="${(c.gap || 0) >= 0 ? 'pos':'neg'}">${pct(c.gap)}</td><td class="${(c.change30d || 0) >= 0 ? 'pos':'neg'}">${pct(c.change30d)}</td>`}
    <td><b>${c.investment}</b></td>
  </tr>`).join('')}</tbody></table></div>`;
}

function bindRows(root) {
  $$(root + ' [data-id]').forEach(el => el.onclick = () => openViewer(el.dataset.id));
}

function renderMarket() {
  const cards = state.cards.filter(c => c.game === state.game && c.availability === 'released');
  const priced = cards.filter(c => Number(c.market) > 0);
  const premiumCards = cards.filter(c => c.isPremium || premium.has(c.rarity));
  const imaged = cards.filter(c => c.image).length;
  const with30 = priced.filter(c => c.change30d != null);
  const avg30 = with30.length ? with30.reduce((a,c) => a + Number(c.change30d), 0) / with30.length : null;

  $('#marketCards').innerHTML = [
    ['Catalog', cards.length.toLocaleString(), 'released printings'],
    ['Premium', premiumCards.length.toLocaleString(), 'SR / SP / SSP / SEC / etc.'],
    ['Priced', priced.length.toLocaleString(), `${Math.round(priced.length / Math.max(1,cards.length) * 100)}% market coverage`],
    ['30d pulse', avg30 == null ? '—' : pct(avg30), with30.length ? `${with30.length} cards with 30d data` : 'price history pending']
  ].map(([l,v,d]) => `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${d}</div></div>`).join('');

  const opportunities = priced.filter(c => c.fair).sort((a,b) => (b.gap ?? -999) - (a.gap ?? -999)).slice(0,12);
  $('#opportunityTable').innerHTML = opportunityTable(opportunities);
  bindRows('#opportunityTable');

  const conviction = premiumCards.slice().sort((a,b) => b.investment - a.investment || (b.market||0)-(a.market||0)).slice(0,12);
  $('#convictionTable').innerHTML = opportunityTable(conviction, true);
  bindRows('#convictionTable');

  const announced = state.cards.filter(c => c.game === state.game && c.availability !== 'released').length;
  const marketFresh = priced.filter(c => c.marketAsOf).length;
  $('#dataHealth').innerHTML = [
    ['Image coverage', `${Math.round(imaged / Math.max(1,cards.length)*100)}%`, `${imaged.toLocaleString()} / ${cards.length.toLocaleString()}`],
    ['Price coverage', `${Math.round(priced.length / Math.max(1,cards.length)*100)}%`, 'observed market only'],
    ['Dated prices', marketFresh.toLocaleString(), 'marketAsOf supplied'],
    ['Announced', announced.toLocaleString(), 'kept separate from released']
  ].map(([a,b,c]) => `<div class="health-card"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
}

function applyFilters() {
  const q = $('#search').value.trim().toLowerCase();
  const gf = $('#gameFilter').value;
  const sf = $('#setFilter').value;
  const rf = $('#rarityFilter').value;
  const af = $('#availabilityFilter').value;
  const prem = $('#premiumOnly').checked;
  const priced = $('#pricedOnly').checked;

  let a = state.cards.filter(c =>
    (gf === 'all' || c.game === gf) &&
    (sf === 'all' || c.set === sf) &&
    (rf === 'all' || c.rarity === rf) &&
    (af === 'all' || c.availability === af) &&
    (!prem || c.isPremium || premium.has(c.rarity)) &&
    (!priced || Number(c.market) > 0) &&
    (!q || [c.name,c.set,c.code,c.rarity,c.cardType,c.color].join(' ').toLowerCase().includes(q))
  );

  const sort = $('#sort').value;
  if (sort === 'name') a.sort((x,y) => (x.name||'').localeCompare(y.name||''));
  else {
    const key = {market:'market',gap:'gap',investment:'investment',momentum:'momentum'}[sort.split('-')[0]];
    a.sort((x,y) => (Number(y[key]) || -Infinity) - (Number(x[key]) || -Infinity));
  }

  state.filtered = a;
  const pages = Math.max(1, Math.ceil(a.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  renderCards();
}

['search','setFilter','rarityFilter','availabilityFilter','sort','premiumOnly','pricedOnly'].forEach(id =>
  $('#'+id).addEventListener(id === 'search' ? 'input' : 'change', () => { state.page = 1; applyFilters(); })
);
$('#gameFilter').addEventListener('change', () => {
  updateSetOptions(); state.page = 1; applyFilters();
});

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
      <div class="card-row"><span class="badge">${esc(c.rarity || '—')}</span><span class="price">${money(c.market)}</span></div>
      <div class="card-row"><span class="${c.gap == null ? '' : c.gap >= 0 ? 'pos':'neg'}">gap ${pct(c.gap)}</span><span>IQ ${c.investment}</span></div>
      ${c.availability !== 'released' ? '<div class="announced-ribbon">ANNOUNCED</div>' : ''}
    </div>
  </article>`).join('');

  $('#cardTable').innerHTML = `<div class="table-scroll"><table><thead><tr><th>Card</th><th>Set</th><th>No.</th><th>Rarity</th><th>Market</th><th>Gap</th><th>Momentum</th><th>IQ</th></tr></thead>
  <tbody>${rows.map(c => `<tr class="click-row" data-id="${esc(c.id)}">
    <td><div class="mini-card">${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}<b>${esc(c.name)}</b></div></td>
    <td>${esc(c.set || '')}</td><td><code>${esc(c.code || '')}</code></td><td><span class="badge">${esc(c.rarity || '—')}</span></td>
    <td>${money(c.market)}</td><td>${pct(c.gap)}</td><td>${c.momentum}</td><td><b>${c.investment}</b></td>
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
  let a = state.sets.filter(s => (game === 'all' || s.game === game) && (!q || s.name.toLowerCase().includes(q)));
  const sort = $('#setSort').value;
  if (sort === 'name') a.sort((x,y) => x.name.localeCompare(y.name));
  else {
    const key = {premium:'premium',total:'total',investment:'avgInvestment',coverage:'priceCoverage'}[sort.split('-')[0]];
    a.sort((x,y) => (Number(y[key])||0)-(Number(x[key])||0));
  }
  $('#setGrid').innerHTML = a.map(s => `<article class="set-card" data-set="${esc(s.name)}" data-game="${esc(s.game)}">
    <div class="set-card-top"><span class="eyebrow">${esc(gameLabel(s.game))}</span><span class="badge">${s.released} released${s.announced ? ` + ${s.announced} announced` : ''}</span></div>
    <h3>${esc(s.name)}</h3>
    <div class="set-stats">
      <div><b>${s.premium}</b><span>premium</span></div>
      <div><b>${s.priceCoverage}%</b><span>priced</span></div>
      <div><b>${s.imageCoverage}%</b><span>images</span></div>
      <div><b>${s.avgInvestment ?? '—'}</b><span>avg IQ</span></div>
    </div>
    <div class="progress"><i style="width:${Math.min(100,s.priceCoverage)}%"></i></div>
  </article>`).join('') || '<div class="empty-state">No sets match.</div>';

  $$('#setGrid [data-set]').forEach(el => el.onclick = () => {
    $('#gameFilter').value = el.dataset.game;
    updateSetOptions();
    $('#setFilter').value = el.dataset.set;
    $('#availabilityFilter').value = 'released';
    state.page = 1; applyFilters(); goto('cards');
  });
}
['setSearch','setGameFilter','setSort'].forEach(id =>
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

  $('#viewerStats').innerHTML = [
    ['Observed market',money(c.market)],['Market low',money(c.marketLow)],['Market median',money(c.marketMedian)],
    ['Model fair',money(c.fair)],['Fair-value gap',pct(c.gap)],['7d',pct(c.change7d)],['30d',pct(c.change30d)],
    ['Momentum',`${c.momentum}/100`],['Investment quality',`${c.investment}/100`],
    ['Confidence',c.confidence || 'Low'],['Price source',c.priceSource || 'Pending']
  ].map(([a,b]) => `<div class="stat"><span>${a}</span><b>${b}</b></div>`).join('');

  const factors = c.modelFactors || {};
  const labels = {
    scarcity:'Structural scarcity',ipStrength:'IP / character prior',reprintDurability:'Reprint durability',
    historicalSignificance:'Historical significance',treatment:'Treatment premium',
    liquidity:'Liquidity',editionDurability:'Edition durability'
  };
  $('#factorBars').innerHTML = Object.entries(labels).map(([k,label]) => {
    const v = Number(factors[k] ?? 0);
    return `<div class="factor"><div><span>${label}</span><b>${v}</b></div><div class="factor-track"><i style="width:${Math.max(0,Math.min(100,v))}%"></i></div></div>`;
  }).join('');

  const p = state.portfolio[c.id] || {qty:0,cost:0};
  $('#portfolioQty').value = p.qty || 0;
  $('#portfolioCost').value = p.cost || 0;

  const src = c.identitySource || c.source;
  $('#sourceBtn').style.display = src ? 'inline-flex' : 'none';
  if (src) $('#sourceBtn').href = src;
  $('#imageBtn').style.display = c.image ? 'inline-flex' : 'none';
  if (c.image) $('#imageBtn').href = c.image;

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
  if (!qty) delete state.portfolio[c.id];
  else state.portfolio[c.id] = {qty,cost};
  localStorage.setItem('bm-portfolio',JSON.stringify(state.portfolio));
  renderPortfolio(); updatePortfolioCount();
  toast(qty ? 'Portfolio position saved.' : 'Removed from portfolio.');
};

function renderWatch() {
  const a = [...state.watch].map(id => state.byId.get(id)).filter(Boolean);
  $('#watchList').innerHTML = a.length ? a.map(c => `<div class="watch-item" data-id="${esc(c.id)}">
    ${c.image ? `<img src="${esc(c.image)}" loading="lazy">` : ''}
    <div><b>${esc(c.name)}</b><br><small>${money(c.market)} · ${esc(c.rarity||'')}</small></div>
  </div>`).join('') : '<p class="muted">No cards watched yet.</p>';
  $$('#watchList [data-id]').forEach(x => x.onclick = () => openViewer(x.dataset.id));
}

function updatePortfolioCount() {
  const count = Object.values(state.portfolio).reduce((a,p) => a + (Number(p.qty)||0),0);
  $('#portfolioCount').textContent = count;
}

function renderPortfolio() {
  const positions = Object.entries(state.portfolio)
    .map(([id,p]) => ({card:state.byId.get(id),qty:Number(p.qty)||0,cost:Number(p.cost)||0}))
    .filter(x => x.card && x.qty > 0);
  const qty = positions.reduce((a,x) => a+x.qty,0);
  const basis = positions.reduce((a,x) => a+x.qty*x.cost,0);
  const priced = positions.filter(x => Number(x.card.market)>0);
  const value = priced.reduce((a,x) => a+x.qty*Number(x.card.market),0);
  const pricedBasis = priced.reduce((a,x) => a+x.qty*x.cost,0);
  const pnl = value - pricedBasis;

  $('#portfolioMetrics').innerHTML = [
    ['Cards owned',qty.toLocaleString(),`${positions.length} positions`],
    ['Cost basis',money(basis),'your entered cost'],
    ['Known market value',money(value),`${priced.length}/${positions.length} priced positions`],
    ['Unrealized P/L',money(pnl),priced.length ? pct(pricedBasis ? pnl/pricedBasis*100 : null) : 'market data pending']
  ].map(([l,v,d]) => `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${d}</div></div>`).join('');

  $('#portfolioTable').innerHTML = positions.length ? `<div class="table-scroll"><table><thead><tr>
    <th>Card</th><th>Qty</th><th>Avg cost</th><th>Basis</th><th>Market</th><th>Value</th><th>P/L</th><th></th>
  </tr></thead><tbody>${positions.map(x => {
    const m=Number(x.card.market)||0,b=x.qty*x.cost,v=m?x.qty*m:0,p=m?v-b:null;
    return `<tr>
      <td class="click-row" data-id="${esc(x.card.id)}"><div class="mini-card">${x.card.image?`<img src="${esc(x.card.image)}" loading="lazy">`:''}<div><b>${esc(x.card.name)}</b><br><small>${esc(x.card.set||'')}</small></div></div></td>
      <td>${x.qty}</td><td>${money(x.cost)}</td><td>${money(b)}</td><td>${money(m||null)}</td><td>${m?money(v):'—'}</td>
      <td class="${p==null?'':p>=0?'pos':'neg'}">${p==null?'—':money(p)}</td>
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
      ${[['Market',money(c.market)],['Model fair',money(c.fair)],['Gap',pct(c.gap)],['30d',pct(c.change30d)],['Momentum',c.momentum],['Investment',c.investment],['Confidence',c.confidence||'Low']].map(x=>`<div class="stat"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('')}
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
  $('#sourcesContent').innerHTML = `<div class="source-grid">${a.map(s=>`<div class="source-card">
    <p class="eyebrow">${esc(s.role||'source')}</p><h3>${esc(s.name)}</h3><p>${esc(s.description||'')}</p>
    ${s.url?`<a class="ghost" target="_blank" rel="noreferrer" href="${esc(s.url)}">Open source</a>`:''}
  </div>`).join('')}</div>
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
