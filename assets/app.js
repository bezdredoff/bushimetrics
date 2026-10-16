const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function safeJson(raw, fallback) {
  try { return JSON.parse(raw); } catch { return fallback; }
}
const state = {
  cards: [], byId: new Map(), printingFamilies: new Map(), sets: [], historyCache: new Map(), historyCurrency: 'EUR', history: {}, sources: {}, marketAudit: {}, research: {records: []}, researchById: new Map(), jpMeta: {}, jpIdentityAudit: null, enIdentityAudit: null, jpLoaded: false, jpLoading: null,
  game: 'weiss', marketLanguage: 'EN', tab: 'market', page: 1, pageSize: 60, filtered: [],
  viewerIndex: 0, viewerList: [], zoom: 1, cardView: localStorage.getItem('bm-card-view') || 'grid',
  watch: new Set(safeJson(localStorage.getItem('bm-watch') || '[]', [])),
  compare: safeJson(localStorage.getItem('bm-compare') || '[]', []).slice(0, 4),
  portfolio: safeJson(localStorage.getItem('bm-portfolio') || '{}', {}),
  setCache: new Map(), loadedSetKeys: new Set(), setManifest: new Map(), fullCatalogLoaded: false, catalogGeneratedAt: null
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

function expandBrowserCard(x) {
  return enrichCard({
    id:x.i, game:x.g, language:x.l||'EN', availability:x.a||'released', _setKey:x.k,
    name:x.n, set:x.s, code:x.c, rarity:x.r, image:x.im,
    marketEUR:x.me, market:x.mu, fairEUR:x.fe, fair:x.fu,
    investment:x.iq, momentum:x.mo, isPremium:!!x.p, rarityRank:x.rr,
    marketHeatPercentile:x.hp, marketHeatLabel:x.hl,
    characterPremiumIndex:x.cp, characterPremiumObservations:x.co,
    marketKind:x.mk, marketConfidence:x.mc, confidence:x.cf,
    marketEvidenceStatus:x.es, marketObservationAgeDays:x.ea,
    marketStale:x.st, unverifiedMarketIndicationUSD:x.ui,
    fairValueConfidence:x.fc, change7d:x.d7, change30d:x.d30,
    demandPressure:x.dp, demandPressureSales:x.ds, demandPressureAsks:x.da,
    priceSource:x.ps, priceSourceEUR:x.pe, marketAsOf:x.ma, cardmarketAsOf:x.ca,
    cardType:x.ct, color:x.cl
  });
}

async function load() {
  const [bootstrap, history, sources, jpMeta, research, marketAudit, jpIdentityAudit, enIdentityAudit] = await Promise.all([
    fetch('data/web/bootstrap.json', {cache:'no-cache'}).then(r => {
      if (!r.ok) throw new Error('web/bootstrap.json ' + r.status);
      return r.json();
    }),
    fetch('data/history.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/sources.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/catalog-weiss-jp-meta.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/research_status.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {records:[]}).catch(() => ({records:[]})),
    fetch('data/market-source-audit.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('data/jp-identity-audit.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch('data/en-identity-audit.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : null).catch(() => null)
  ]);

  state.cards = (bootstrap.cards || []).map(expandBrowserCard);
  state.jpMeta = jpMeta || {};
  state.sets = bootstrap.sets || [];
  state.setManifest = new Map((bootstrap.sets||[]).map(x=>[x.key,x]));
  state.history = history;
  state.sources = sources;
  state.marketAudit = marketAudit || {};
  state.jpIdentityAudit = jpIdentityAudit;
  state.enIdentityAudit = enIdentityAudit;
  state.research = research || {records:[]};
  state.researchById = new Map((state.research.records||[]).map(x=>[x.id,x]));
  state.catalogGeneratedAt = bootstrap.generatedAt || null;
  rebuildCardIndexes();

  const counts = bootstrap.counts || {};
  const jpCounts = (jpMeta && jpMeta.counts) || {};
  const totalReleased = Number(counts.released || 0) + Number(jpCounts.released || 0);
  $('#globalStatus').textContent = `${totalReleased.toLocaleString()} released`;
  updateCatalogStatus(bootstrap.generatedAt);

  initFilters();
  renderAll();
  restoreDeepLink();

  // Full EN catalog loads after first paint. Bootstrap cards remain usable if
  // the larger index is slow or temporarily unavailable.
  loadFullBrowserCatalog();
}

async function loadFullBrowserCatalog() {
  try {
    $('#catalogStatus').textContent += ' · loading full EN catalog…';
    const r=await fetch('data/web/search-en.json',{cache:'no-cache'});
    if(!r.ok) throw new Error('web/search-en.json '+r.status);
    const full=await r.json();
    const previous=new Map(state.cards.map(c=>[c.id,c]));
    const jp=state.jpLoaded ? state.cards.filter(c=>(c.language||'EN')==='JP') : [];
    const en=(full.cards||[]).map(expandBrowserCard).map(c=>{
      const old=previous.get(c.id);
      return old && (old.image || old._detailLoaded) ? enrichCard({...c,...old}) : c;
    });
    state.cards=[...en,...jp];
    state.fullCatalogLoaded=true;
    state.catalogGeneratedAt=full.generatedAt||state.catalogGeneratedAt;
    // Set metadata already comes from bootstrap manifest; only card index changes here.
    rebuildCardIndexes();
    initFilters();
    renderAll();
    updateCatalogStatus(state.catalogGeneratedAt);
    toast(`Full catalog loaded: ${state.cards.length.toLocaleString()} cards in browser.`);
  } catch(e) {
    console.error(e);
    $('#catalogStatus').textContent += ' · full catalog unavailable; showing bootstrap cards';
    toast('Full catalog is temporarily unavailable; bootstrap cards remain usable.');
  }
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
  const stage=state.fullCatalogLoaded ? '' : ' · bootstrap visible';
  $('#catalogStatus').textContent =
    `${loaded.toLocaleString()} loaded printings${stage}${jpText} · ${state.sets.length.toLocaleString()} set/language groups` +
    (generatedAt ? ` · updated ${new Date(generatedAt).toLocaleString()}` : '');
}

function expandJPCompact(x) {
  const rr=Number(x.rr||30);
  const treatment=rr>=86?82:(rr>=62?55:30);
  return enrichCard({
    id:x.id||x.i,game:'weiss',language:'JP',availability:'released',_setKey:x.k,
    name:x.n,set:x.s,setId:x.si,code:x.c,rarity:x.r,cardType:x.t||x.ct,color:x.co||x.cl,image:x.im,
    rarityRank:Number(x.rr||rr),isPremium:!!x.p,investment:Number(x.iq||0),momentum:Number(x.mo||50),confidence:x.cf||'Low',
    identitySource:x.sf ? 'https://github.com/Akenaide/wsoffdata/blob/master/'+x.sf : null,
    catalogSource:'Akenaide/wsoffdata / official ws-tcg.com artwork',
    modelStatus:'jp-generic-v0.8',
    modelFactors:{
      scarcity:rr,ipStrength:55,characterPremium:50,reprintDurability:55,
      historicalSignificance:50,treatment,liquidity:25,editionDurability:50
    }
  });
}

async function ensureJPCatalog() {
  if (state.jpLoaded) return true;
  if (state.jpLoading) return state.jpLoading;
  state.jpLoading=(async()=>{
    toast('Loading Japanese Weiss catalog…');
    const r=await fetch('data/web/search-jp.json',{cache:'no-cache'});
    if(!r.ok) throw new Error('JP search index '+r.status);
    const jp=await r.json();
    const incoming=(jp.cards||[]).map(expandJPCompact);
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
  if (tab === 'coverage') renderCoverage();
}
$$('#tabs button').forEach(b => b.onclick = () => goto(b.dataset.tab));
$$('[data-go]').forEach(b => b.onclick = () => goto(b.dataset.go));
$('#themeBtn').onclick = () => document.body.classList.toggle('light');

$$('#gameSeg button').forEach(b => b.onclick = async () => {
  state.game = b.dataset.game;
  $$('#gameSeg button').forEach(x => x.classList.toggle('active', x === b));
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
  const layerSets=state.sets.filter(x=>x.game===state.game && (x.language||'EN')===state.marketLanguage);
  const imaged = layerSets.reduce((a,x)=>a+Number(x.imaged||0),0) || cards.filter(c => c.image).length;
  const with30 = priced.filter(c => c.change30d != null);
  const avg30 = with30.length ? with30.reduce((a,c) => a + Number(c.change30d), 0) / with30.length : null;

  $('#marketCards').innerHTML = [
    ['Catalog', cards.length.toLocaleString(), 'released printings'],
    ['Premium', premiumCards.length.toLocaleString(), 'SR / SP / SSP / SEC / etc.'],
    ['Priced', priced.length.toLocaleString(), `${Math.round(priced.length / Math.max(1,cards.length) * 100)}% observed · ${Math.max(0,cards.length-priced.length).toLocaleString()} without public price data · € ${pricedEUR.length.toLocaleString()} / $ ${pricedUSD.length.toLocaleString()}`],
    ['30d pulse', avg30 == null ? '—' : pct(avg30), with30.length ? `${with30.length} cards with 30d data` : 'price history pending']
  ].map(([l,v,d]) => `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${d}</div></div>`).join('');

  const opportunities = priced.filter(c => c.fair).sort((a,b) => (b.gap ?? -999) - (a.gap ?? -999)).slice(0,12);
  $('#opportunityTable').innerHTML = opportunityTable(opportunities);
  bindRows('#opportunityTable');

  const conviction = premiumCards.slice().sort((a,b) => b.investment - a.investment || (b.market||0)-(a.market||0)).slice(0,12);
  $('#convictionTable').innerHTML = opportunityTable(conviction, true);
  bindRows('#convictionTable');

  hydrateSetKeys([...opportunities,...conviction].map(c=>c._setKey)).then(changed=>{if(changed) renderMarket();});

  const pressure = cards.filter(c => c.demandPressure != null).sort((a,b)=>(b.marketHeatPercentile??-1)-(a.marketHeatPercentile??-1)).slice(0,15);
  $('#pressureTable').innerHTML = pressure.length ? `<div class="table-scroll"><table><thead><tr><th>Card</th><th>Rarity</th><th>Sales</th><th>Fresh asks</th><th>Pressure</th><th>Heat</th></tr></thead><tbody>${pressure.map(c=>`<tr class="click-row" data-id="${esc(c.id)}"><td><div class="mini-card">${c.image?`<img src="${esc(c.image)}" loading="lazy">`:''}<div><b>${esc(c.name)}</b><br><small>${esc(c.set||'')}</small></div></div></td><td><span class="badge">${esc(c.rarity||'—')}</span></td><td>${c.demandPressureSales??'—'}</td><td>${c.demandPressureAsks??'—'}</td><td><b>${c.demandPressure.toFixed(1)}%</b></td><td><span class="badge">${esc(c.marketHeatLabel||'—')} · P${c.marketHeatPercentile??'—'}</span></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty-state">No sales + asks pressure data for this game yet.</div>';
  bindRows('#pressureTable');

  const announced = state.cards.filter(c => c.game === state.game && (c.language||'EN') === state.marketLanguage && c.availability !== 'released').length;
  const marketFresh = priced.filter(c => c.marketAsOf || c.cardmarketAsOf).length;
  $('#dataHealth').innerHTML = [
    ['Artwork URL coverage (not verified)', `${Math.round(imaged / Math.max(1,cards.length)*100)}%`, `${imaged.toLocaleString()} URLs / ${cards.length.toLocaleString()} cards`],
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

['rarityFilter','availabilityFilter','signalFilter','sort','premiumOnly','pricedOnly'].forEach(id =>
  $('#'+id).addEventListener('change', () => { state.page = 1; applyFilters(); })
);
$('#setFilter').addEventListener('change', async () => {
  const name=$('#setFilter').value;
  if(name!=='all'){
    const game=$('#gameFilter').value,lang=$('#languageFilter').value;
    const meta=state.sets.find(x=>x.name===name&&(game==='all'||x.game===game)&&(lang==='all'||(x.language||'EN')===lang));
    if(meta){
      const payload=await fetchSetPayload(meta.key);
      if(payload){applySetPayload(payload);rebuildCardIndexes();}
    }
  }
  state.page=1;applyFilters();
});
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
  $('#search').value=''; $('#gameFilter').value='all'; $('#languageFilter').value='EN'; updateSetOptions(); $('#setFilter').value='all'; $$('#quickPresets .preset').forEach(b=>b.classList.remove('active'));
  $('#rarityFilter').value='all'; $('#availabilityFilter').value='released'; $('#signalFilter').value='all';
  $('#sort').value='investment-desc'; $('#premiumOnly').checked=false; $('#pricedOnly').checked=false;
  state.page=1; applyFilters();
};

// Bushiroad's newer official artwork URLs include /images/cardlist/.
// Retry that path for legacy JP links, then try the image relay once.
document.addEventListener('error', event => {
  const img = event.target;
  if (!(img instanceof HTMLImageElement)) return;
  const url = img.currentSrc || img.src;
  let parsed;
  try { parsed = new URL(url); } catch { parsed = null; }
  const official = parsed && ['ws-tcg.com', 'www.ws-tcg.com'].includes(parsed.hostname);
  if (official && !img.dataset.artFallback && parsed.pathname.includes('/wordpress/wp-content/images/') && !parsed.pathname.includes('/wordpress/wp-content/images/cardlist/')) {
    img.dataset.artFallback = 'cardlist';
    img.src = url.replace('/wordpress/wp-content/images/', '/wordpress/wp-content/images/cardlist/');
    return;
  }
  if (official && img.dataset.artFallback !== 'relay') {
    img.dataset.artFallback = 'relay';
    img.src = 'https://images.weserv.nl/?url=' + encodeURIComponent(url);
    return;
  }
  const replacement = document.createElement('div');
  replacement.className = 'placeholder';
  replacement.textContent = 'Artwork unavailable';
  replacement.title = 'The image host rejected this image or it is no longer available';
  img.replaceWith(replacement);
}, true);

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

  $('#pageInfo').textContent = `${state.page} / ${pages} · ${state.filtered.length.toLocaleString()} cards`; $('#pageJump').max=String(pages); $('#pageJump').value=String(state.page);
  renderWatch();

  const missing=rows.filter(c=>c._setKey && !c.image).map(c=>c._setKey);
  if(missing.length){
    hydrateSetKeys(missing).then(changed=>{if(changed) renderCards();});
  }
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
      <div><b>${s.imageCoverage}%</b><span>image URLs*</span></div>
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
    const meta=state.sets.find(x=>x.name===el.dataset.set&&x.game===el.dataset.game&&(x.language||'EN')===lang);
    if(meta){
      const payload=await fetchSetPayload(meta.key);
      if(payload){applySetPayload(payload);rebuildCardIndexes();}
    }
    state.page = 1; applyFilters(); goto('cards');
  });
}
['setSearch','setGameFilter','setLanguageFilter','setSort'].forEach(id =>
  $('#'+id).addEventListener(id === 'setSearch' ? 'input' : 'change', renderSets)
);


async function fetchSetPayload(setKey) {
  if (!setKey) return null;
  if (state.setCache.has(setKey)) return state.setCache.get(setKey);
  const meta=state.setManifest.get(setKey);
  if(!meta || !meta.path) return null;
  const promise=fetch(meta.path,{cache:'no-cache'})
    .then(r=>{if(!r.ok) throw new Error(meta.path+' '+r.status);return r.json();})
    .catch(e=>{console.error('set load failed',setKey,e);return null;});
  state.setCache.set(setKey,promise);
  return promise;
}

function applySetPayload(payload) {
  if(!payload || !Array.isArray(payload.cards)) return [];
  const rows=payload.compactJP ? payload.cards.map(expandJPCompact) : payload.cards.map(c=>enrichCard({...c,_setKey:payload.key}));
  const pos=new Map(state.cards.map((c,i)=>[c.id,i]));
  const filteredPos=new Map(state.filtered.map((c,i)=>[c.id,i]));
  const viewerPos=new Map(state.viewerList.map((c,i)=>[c.id,i]));
  for(const c of rows){
    const i=pos.get(c.id);
    if(i==null){ state.cards.push(c); pos.set(c.id,state.cards.length-1); }
    else state.cards[i]=c;
    const fi=filteredPos.get(c.id); if(fi!=null) state.filtered[fi]=c;
    const vi=viewerPos.get(c.id); if(vi!=null) state.viewerList[vi]=c;
    state.byId.set(c.id,c);
  }
  if(payload.key) state.loadedSetKeys.add(payload.key);
  return rows;
}

async function hydrateSetKeys(keys) {
  const wanted=[...new Set(keys.filter(Boolean))].filter(k=>!state.loadedSetKeys.has(k));
  if(!wanted.length) return false;
  const payloads=await Promise.all(wanted.map(fetchSetPayload));
  let changed=false;
  for(const p of payloads){ if(p){applySetPayload(p);changed=true;} }
  if(changed) rebuildCardIndexes();
  return changed;
}

async function ensureCardDetail(id) {
  const current=state.byId.get(id);
  if (!current) return null;
  if (current._detailLoaded) return current;
  const payload=await fetchSetPayload(current._setKey);
  if(payload){
    const rows=applySetPayload(payload);
    for(const row of rows) row._detailLoaded=true;
    rebuildCardIndexes();
  }
  const hydrated=state.byId.get(id)||current;
  hydrated._detailLoaded=true;
  return hydrated;
}

function openViewer(id) {
  const c = state.byId.get(id);
  if (!c) return;
  state.viewerList = state.filtered.length && state.filtered.some(x => x.id === id) ? state.filtered : state.cards;
  state.viewerIndex = Math.max(0, state.viewerList.findIndex(x => x.id === id));
  renderViewer();
  ensureCardDetail(id).then(full=>{
    const active=state.viewerList[state.viewerIndex];
    if (!full || !active || active.id!==id) return;
    const pos=state.viewerList.findIndex(x=>x.id===id);
    if (pos>=0) state.viewerList[pos]=full;
    renderViewer();
  });
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
  $('#viewerMeta').textContent = [c.language||'EN',c.set,c.code,c.rarity,c.edition,c.treatment].filter(Boolean).join(' · ');
  $('#viewerBadges').innerHTML = [
    c.availability !== 'released' ? '<span class="badge badge-warn">Announced</span>' : '<span class="badge">Released</span>',
    c.isPremium ? '<span class="badge badge-accent">Premium</span>' : '',
    !observed(c) ? '<span class="badge">Public market price unavailable</span>' : '',
    observed(c) ? `<span class="badge">Price source: ${esc(observed(c).source)}</span>` : '',
    !modelFair(c) ? '<span class="badge">Model fair value unavailable</span>' : '',
    c.market != null && c.marketStale ? '<span class="badge badge-warn">USD price observation outdated or undated</span>' : '',
    c.unverifiedMarketIndicationUSD != null ? '<span class="badge badge-warn">Unverified quote excluded from market data</span>' : ''
  ].join('');

  const familyKey=[c.game,c.language||'EN',c.set||'',String(c.name||'').trim().toLowerCase()].join('|');
  const family=state.printingFamilies.get(familyKey)||[c];
  $('#printingFamilyCount').textContent=family.length + (family.length===1?' printing':' printings');
  $('#printingFamily').innerHTML=family.map(x => `<button class="printing-chip ${x.id===c.id?'active':''}" data-family-id="${esc(x.id)}" title="${esc(x.code||'')}">
    ${x.image?`<img src="${esc(x.image)}" loading="lazy" alt="">`:''}
    <span><b>${esc(x.rarity||'—')}</b><small>${esc(x.code||'')}</small><em>${observedLabel(x)}</em></span>
  </button>`).join('');
  $$('#printingFamily [data-family-id]').forEach(btn=>btn.onclick=()=>{
    const target=state.byId.get(btn.dataset.familyId); if(!target)return;
    const idx=state.viewerList.findIndex(x=>x.id===target.id);
    if(idx>=0) state.viewerIndex=idx;
    else { state.viewerList=family; state.viewerIndex=family.findIndex(x=>x.id===target.id); }
    renderViewer(); updateViewerHash();
  });

  renderCardHistory(c);
  const evidence = state.researchById.get(c.id);
  const metricNames = [['cec','Carton Equivalent Cost'],['demandPressure','Verified demand pressure'],
    ['historicalHype','Historical HYPE'],['ripEV','Raw Rip EV'],
    ['gradingEV','Grading EV'],['franchiseHealth','Franchise Health']];
  const evidenceRows = metricNames.map(([key,label]) => {
    const entry=evidence?.metrics?.[key];
    const value=entry?.value;
    const formatted=value==null ? 'Unavailable — '+(entry?.reason||'No verified observation for this printing')
      : (entry.currency ? currencyMoney(value,entry.currency) : Number(value).toLocaleString());
    return [esc(label),esc(formatted)];
  });
  $('#viewerStats').innerHTML = [
    ['Cardmarket trend (EUR)',euro(c.marketEUR)],['Cardmarket low (EUR)',euro(c.marketEURLow)],
    ['Cardmarket 7d avg',euro(c.marketEURAvg7)],['Cardmarket 30d avg',euro(c.marketEURAvg30)],
    ['USD market price / estimate',c.marketKind==='thin' ? '~'+money(c.market) : money(c.market)],['TCGPlayer low (USD)',money(c.marketLow)],['TCGPlayer median (USD)',money(c.marketMedian)],
    ['USD evidence class',esc(c.marketEvidenceStatus||'Not available in this catalog view')],['USD observation age',c.marketObservationAgeDays!=null ? `${c.marketObservationAgeDays} days${c.marketStale ? ' · stale':''}` : 'Date unknown'],['Unverified research quote (not market)',c.unverifiedMarketIndicationUSD!=null ? `${money(c.unverifiedMarketIndicationUSD)} · not used in calculations` : '—'],['Completed-sale sample',c.salesInBasis!=null ? `${c.salesInBasis} sales · ${c.marketBasisWindow||'basis'}` : '—'],['Fresh asks',c.marketAskCount!=null ? `${c.marketAskCount} · low ${money(c.marketAskLow)}${c.marketAskMedian!=null ? ` · median ${money(c.marketAskMedian)}`:''}` : '—'],
    ['Peer fair value',fairLabel(c)],['Fair-value gap',pct(c.gap)],['Fair confidence',c.fairValueConfidence||'None'],['Fair method',c.fairValueMethod||'Insufficient peers'],['7d',pct(c.change7d)],['30d',pct(c.change30d)],
    ['Price-change momentum (heuristic)', c.change7d!=null || c.change30d!=null ? `${c.momentum}/100` : 'Unavailable — no measured price change'],['Observed demand / inventory proxy',c.demandPressure!=null?`${c.demandPressure.toFixed(1)}% · cross-sectional P${c.marketHeatPercentile??'—'} (not historical HYPE)`:'Unavailable — no verified sales and inventory observations'],['Investment quality',`${c.investment}/100`],
    ['Character premium',c.characterPremiumIndex!=null ? `${c.characterPremiumIndex} index · ${c.characterPremiumObservations||0} obs · ${c.characterPremiumConfidence||'Low'}` : 'Not enough peer pricing'],['Fair peers',c.fairValuePeerCount!=null ? `${c.fairValuePeerCount} rarity peers · ${c.fairValueSubjectObservations||0} subject obs` : '—'],
    ['Confidence',c.confidence || 'Low'],
    ['EUR source',c.priceSourceEUR || 'Pending'],['USD source',c.priceSource || 'Pending'],['Price qualifier',c.marketQualifier || (c.marketKind==='bare' ? 'Completed-sale estimate' : '—')],
    ...evidenceRows
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


async function historyForCard(cardId) {
  const shard=String(cardId||'0')[0].toLowerCase();
  if (!state.historyCache.has(shard)) {
    state.historyCache.set(shard, fetch(`data/history-shards/${shard}.json`,{cache:'no-cache'})
      .then(r=>r.ok?r.json():({cards:{}})).catch(()=>({cards:{}})));
  }
  const data=await state.historyCache.get(shard);
  return (data.cards||{})[cardId]||[];
}

function chartPath(points,key,min,max,w,h,pad) {
  const rows=points.filter(p=>p[key]!=null);
  if(!rows.length)return '';
  const n=Math.max(1,points.length-1),span=Math.max(.0001,max-min);
  return rows.map(p=>{
    const i=points.indexOf(p);
    const x=pad+(w-pad*2)*(i/n);
    const y=pad+(h-pad*2)*(1-(Number(p[key])-min)/span);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

async function renderCardHistory(c) {
  const targetId=c.id;
  $('#historySummary').textContent='Loading history…';
  $('#historyChart').innerHTML='';
  const points=await historyForCard(targetId);
  const active=state.viewerList[state.viewerIndex];
  if(!active||active.id!==targetId)return;
  const useEUR=state.historyCurrency==='EUR';
  const marketKey=useEUR?'e':'u', fairKey=useEUR?'fe':'fu';
  const marketRows=points.filter(p=>p[marketKey]!=null);
  const fairRows=points.filter(p=>p[fairKey]!=null);
  $('#historyEURBtn').classList.toggle('active',useEUR);
  $('#historyUSDBtn').classList.toggle('active',!useEUR);
  if(!marketRows.length){
    $('#historySummary').textContent=`No publicly verified ${state.historyCurrency} price history available for this printing.`;
    $('#historyChart').innerHTML='<div class="empty-state compact-empty">Not publicly available in the current dataset. History begins only after verified price observations are recorded.</div>';
    return;
  }
  const vals=[...marketRows.map(p=>Number(p[marketKey])),...fairRows.map(p=>Number(p[fairKey]))].filter(Number.isFinite);
  let min=Math.min(...vals),max=Math.max(...vals);
  if(max===min){min*=.95;max*=1.05;if(max===min){min-=1;max+=1}}
  const first=marketRows[0],last=marketRows[marketRows.length-1];
  const change=Number(first[marketKey]) ? (Number(last[marketKey])/Number(first[marketKey])-1)*100 : null;
  const fmt=useEUR?euro:money;
  $('#historySummary').innerHTML=`<b>${fmt(last[marketKey])}</b><span class="${(change||0)>=0?'pos':'neg'}">${marketRows.length>1?pct(change):'first snapshot'}</span><small>${marketRows.length} daily point${marketRows.length===1?'':'s'} · ${esc(first.d)} → ${esc(last.d)}</small>`;
  const w=720,h=220,pad=28;
  const marketLine=chartPath(points,marketKey,min,max,w,h,pad);
  const fairLine=chartPath(points,fairKey,min,max,w,h,pad);
  const yTop=fmt(max),yBottom=fmt(min);
  const lastIndex=points.findIndex(p=>p===last);
  const n=Math.max(1,points.length-1);
  const lx=pad+(w-pad*2)*(lastIndex/n);
  const ly=pad+(h-pad*2)*(1-(Number(last[marketKey])-min)/(max-min));
  $('#historyChart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Price history">
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h-pad}" class="chart-axis"/>
    <line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" class="chart-axis"/>
    <text x="4" y="${pad+4}" class="chart-label">${esc(yTop)}</text>
    <text x="4" y="${h-pad}" class="chart-label">${esc(yBottom)}</text>
    ${fairLine?`<polyline points="${fairLine}" class="chart-line chart-fair"/>`:''}
    <polyline points="${marketLine}" class="chart-line chart-market"/>
    <circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="4" class="chart-dot"/>
  </svg>
  <div class="chart-legend"><span><i class="legend-market"></i>Observed market</span><span><i class="legend-fair"></i>Model fair value</span></div>`;
}
$('#historyEURBtn').onclick=()=>{state.historyCurrency='EUR';const c=state.viewerList[state.viewerIndex];if(c)renderCardHistory(c);};
$('#historyUSDBtn').onclick=()=>{state.historyCurrency='USD';const c=state.viewerList[state.viewerIndex];if(c)renderCardHistory(c);};


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


function setExplorerPreset(name) {
  $$('#quickPresets .preset').forEach(b => b.classList.toggle('active', b.dataset.preset === name));
  $('#search').value=''; $('#setFilter').value='all'; $('#rarityFilter').value='all'; $('#availabilityFilter').value='released'; $('#signalFilter').value='all';
  $('#premiumOnly').checked=false; $('#pricedOnly').checked=false;
  if (name === 'en-weiss') { $('#gameFilter').value='weiss'; $('#languageFilter').value='EN'; }
  if (name === 'jp-weiss') { $('#gameFilter').value='weiss'; $('#languageFilter').value='JP'; }
  if (name === 'palworld') { $('#gameFilter').value='palworld'; $('#languageFilter').value='EN'; }
  if (name === 'premium') { $('#gameFilter').value='all'; $('#languageFilter').value='EN'; $('#premiumOnly').checked=true; }
  if (name === 'priced') { $('#gameFilter').value='all'; $('#languageFilter').value='EN'; $('#pricedOnly').checked=true; $('#sort').value='market-desc'; }
  if (name === 'all') { $('#gameFilter').value='all'; $('#languageFilter').value='all'; }
}
$$('#quickPresets .preset').forEach(btn => btn.onclick = async () => {
  const name=btn.dataset.preset;
  if (name === 'jp-weiss' || name === 'all') await ensureJPCatalog();
  setExplorerPreset(name); updateSetOptions(); state.page=1; applyFilters(); goto('cards');
});

$('#pageSizeSelect').value=String(state.pageSize);
$('#pageSizeSelect').addEventListener('change',e=>{state.pageSize=Number(e.target.value)||60;state.page=1;renderCards();});
$('#pageJump').addEventListener('change',e=>{
  const pages=Math.max(1,Math.ceil(state.filtered.length/state.pageSize));
  state.page=Math.max(1,Math.min(pages,Number(e.target.value)||1)); renderCards();
});

function csvCell(v){const x=String(v??'');return /[",\n]/.test(x)?'"'+x.replaceAll('"','""')+'"':x;}
function exportFilteredCsv(){
  const rows=[['game','language','set','name','code','rarity','availability','marketEUR','marketUSD','fairEUR','fairUSD','gapPct','investment','momentum','image']];
  for(const c of state.filtered) rows.push([c.game,c.language||'EN',c.set,c.name,c.code,c.rarity,c.availability,c.marketEUR,c.market,c.fairEUR,c.fair,c.gap,c.investment,c.momentum,c.image]);
  const blob=new Blob([rows.map(r=>r.map(csvCell).join(',')).join('\n')],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='bushimetrics-filtered-cards.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
$('#exportFilteredBtn').onclick=exportFilteredCsv;

function renderCoverage(){
  const en=state.cards.filter(c=>c.game==='weiss'&&(c.language||'EN')==='EN'&&c.availability==='released');
  const jpLoaded=state.cards.filter(c=>c.game==='weiss'&&(c.language||'EN')==='JP'&&c.availability==='released');
  const jpCount=Number(state.jpMeta?.counts?.released||jpLoaded.length||0);
  const pal=state.cards.filter(c=>c.game==='palworld'&&c.availability==='released');
  const announced=state.cards.filter(c=>c.game==='palworld'&&c.availability!=='released');
  const releasedTotal=en.length+jpCount+pal.length;
  const enSets=new Set(en.map(c=>c.set).filter(Boolean)).size;
  const jpSets=Number(state.jpMeta?.counts?.sets||new Set(jpLoaded.map(c=>c.set).filter(Boolean)).size||0);
  const palSets=new Set(pal.map(c=>c.set).filter(Boolean)).size;
  const enPrice=en.filter(c=>observed(c)).length, palPrice=pal.filter(c=>observed(c)).length;
  const enLayer=state.sets.filter(x=>x.game==='weiss'&&(x.language||'EN')==='EN');
  const jpLayer=state.sets.filter(x=>x.game==='weiss'&&(x.language||'EN')==='JP');
  const palLayer=state.sets.filter(x=>x.game==='palworld'&&(x.language||'EN')==='EN');
  const enImg=enLayer.reduce((a,x)=>a+Number(x.imaged||0),0);
  const palImg=palLayer.reduce((a,x)=>a+Number(x.imaged||0),0);
  $('#coverageMetrics').innerHTML=[
    ['Released printings',releasedTotal.toLocaleString(),'EN Weiss + JP Weiss + Palworld'],
    ['English Weiss',en.length.toLocaleString(),enSets.toLocaleString()+' sets'],
    ['Japanese Weiss',jpCount.toLocaleString(),jpSets.toLocaleString()+' sets · '+(state.jpLoaded?'loaded':'lazy')],
    ['Palworld',pal.length.toLocaleString(),announced.length.toLocaleString()+' announced separate']
  ].map(([l,v,d])=>`<div class="metric"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${d}</div></div>`).join('');

  const layers=[
    ['Weiss Schwarz · EN',en.length,enSets,enImg,enPrice,'Loaded immediately'],
    ['Weiss Schwarz · JP',jpCount,jpSets,jpLayer.reduce((a,x)=>a+Number(x.imaged||0),0),0,state.jpLoaded?'Search index loaded':'Search index on demand'],
    ['Palworld OCG · EN',pal.length,palSets,palImg,palPrice,'Loaded immediately'],
    ['Palworld announced',announced.length,new Set(announced.map(c=>c.set).filter(Boolean)).size,announced.filter(c=>c.image).length,0,'Excluded from released inventory']
  ];
  $('#coverageLayers').innerHTML=`<div class="table-scroll"><table><thead><tr><th>Layer</th><th>Printings</th><th>Sets</th><th>Artwork URLs</th><th>Priced</th><th>Status</th></tr></thead><tbody>${layers.map(x=>`<tr><td><b>${x[0]}</b></td><td>${Number(x[1]).toLocaleString()}</td><td>${Number(x[2]).toLocaleString()}</td><td>${Number(x[3]||0).toLocaleString()}</td><td>${Number(x[4]||0).toLocaleString()}</td><td><span class="badge">${x[5]}</span></td></tr>`).join('')}</tbody></table></div>`;

  const totalImmediate=en.length+pal.length;
  const immediateImages=enImg+palImg;
  const immediatePriced=enPrice+palPrice;
  $('#coverageQuality').innerHTML=[
    ['Immediate artwork URL coverage',Math.round(immediateImages/Math.max(1,totalImmediate)*100)+'%',immediateImages.toLocaleString()+' URLs; reachability not checked'],
    ['Immediate price coverage',Math.round(immediatePriced/Math.max(1,totalImmediate)*100)+'%',immediatePriced.toLocaleString()+' observed'],
    ['Premium EN+Pal',state.cards.filter(c=>(c.language||'EN')==='EN'&&(c.isPremium||premium.has(c.rarity))&&c.availability==='released').length.toLocaleString(),'distinct premium printings'],
    ['Total set groups',(enSets+jpSets+palSets).toLocaleString(),'language-specific set groups']
  ].map(([a,b,c])=>`<div class="health-card"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');

  const top=[...state.sets].sort((a,b)=>(Number(b.total)||0)-(Number(a.total)||0)).slice(0,20);
  $('#coverageSets').innerHTML=`<div class="table-scroll"><table><thead><tr><th>Set</th><th>Game</th><th>Lang</th><th>Total</th><th>Premium</th><th>Images</th><th>Priced</th></tr></thead><tbody>${top.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(gameLabel(x.game))}</td><td>${esc(x.language||'EN')}</td><td>${Number(x.total||0).toLocaleString()}</td><td>${Number(x.premium||0).toLocaleString()}</td><td>${x.imageCoverage??0}%</td><td>${x.priceCoverage??0}%</td></tr>`).join('')}</tbody></table></div>`;
  const ea=state.enIdentityAudit;
  $('#enIdentityAudit').innerHTML=ea && typeof ea.sourceFiles==='number' ? `<div class="stat-list">
    <div class="stat"><span>English-source set files examined</span><b>${Number(ea.sourceFiles).toLocaleString()}</b></div>
    <div class="stat"><span>Printings retained by collector code</span><b>${Number(ea.uniquePrintingsByCode).toLocaleString()}</b></div>
    <div class="stat"><span>Source rows with duplicate code</span><b>${Number(ea.duplicateCodeRows).toLocaleString()}</b></div>
    <div class="stat"><span>Code groups with conflicting metadata</span><b>${Number(ea.conflictingCodeGroups).toLocaleString()} · verify manually</b></div>
    <div class="stat"><span>Invalid set files / missing card codes</span><b>${Number(ea.invalidSetFiles).toLocaleString()} / ${Number(ea.missingCodeRows).toLocaleString()}</b></div>
  </div><p>Repeated collector numbers are not automatically assumed to be distinct physical cards. <a href="data/en-identity-audit.json" target="_blank" rel="noreferrer">View detailed audit</a>.</p>` :
    '<p>English upstream identity audit is pending the next full data refresh. Unique numbering does not by itself prove physical-variant completeness.</p>';
  const qa=state.jpIdentityAudit;
  $('#jpIdentityAudit').innerHTML=qa && typeof qa.sourceFiles==='number' ? `<div class="stat-list">
    <div class="stat"><span>Upstream card JSON files examined</span><b>${Number(qa.sourceFiles).toLocaleString()}</b></div>
    <div class="stat"><span>Unique collector codes</span><b>${Number(qa.uniqueCollectorCodes??qa.uniquePrintingsByCode).toLocaleString()}</b></div>
    <div class="stat"><span>Distinct printings, including verified parallels</span><b>${Number(qa.uniquePrintingsByCode).toLocaleString()}</b></div>
    <div class="stat"><span>Files with repeated collector code</span><b>${Number(qa.duplicateCodeFiles).toLocaleString()}</b></div>
    <div class="stat"><span>Code groups with conflicting metadata</span><b>${Number(qa.conflictingCodeGroups).toLocaleString()}</b></div>
    <div class="stat"><span>Verified parallel printings restored</span><b>${Number(qa.verifiedVariantRows||0).toLocaleString()}</b></div>
    <div class="stat"><span>Unresolved conflict groups</span><b>${Number(qa.unresolvedConflictingCodeGroups??qa.conflictingCodeGroups).toLocaleString()} · manual review</b></div>
    <div class="stat"><span>Invalid JSON / missing card code</span><b>${Number(qa.invalidFiles).toLocaleString()} / ${Number(qa.missingCardCodeFiles).toLocaleString()}</b></div>
  </div><p>Distinct printings are not invented from repeated IDs. This audit checks upstream duplicates, not completeness against Bushiroad's live official website. <a href="data/jp-identity-audit.json" target="_blank" rel="noreferrer">View full audit</a>.</p>` :
    '<p>Japanese upstream identity audit is pending the next full data refresh. Current card counts do not prove that every distinct physical printing has been verified.</p>';
  $('#loadJPCoverageBtn').textContent=state.jpLoaded?'JP catalog loaded':'Load full JP catalog';
  $('#loadJPCoverageBtn').disabled=state.jpLoaded;
}
$('#loadJPCoverageBtn').onclick=async()=>{await ensureJPCatalog();renderCoverage();renderSets();};

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
  <div class="panel"><h3>Research model availability</h3><p>Metrics are displayed only with sufficient observed inputs. The codebase supports evidence-gated research calculations; having a formula is not the same as having market evidence.</p>
    <div class="stat-list">
      <div class="stat"><span>Carton Equivalent Cost (CEC)</span><b>Awaiting verified carton prices and card-specific case observations</b></div>
      <div class="stat"><span>Historical HYPE</span><b>Awaiting comparable historical sales / listing observations</b></div>
      <div class="stat"><span>Rip EV / graded EV</span><b>Awaiting complete pull distributions, sold prices and grade outcomes</b></div>
      <div class="stat"><span>Franchise Health Index</span><b>Awaiting validated retention and activity series</b></div>
      <div class="stat"><span>Signatures / reprint editions</span><b>Only verified physical variants may be distinguished</b></div>
      <div class="stat"><span>Investment model</span><b>Heuristic — not calibrated to validated long-term returns</b></div>
    </div>
  </div>
  <div class="panel"><h3>Market source audit</h3><p>Unlinked manual and legacy seed prices are research indications, not verified market transactions or inputs to peer Fair Value.</p>
    <div class="stat-list">
      <div class="stat"><span>Manually entered prices reviewed</span><b>${Number(state.marketAudit.manualPriced||0).toLocaleString()}</b></div>
      <div class="stat"><span>Missing independent source or card-level date</span><b>${Number(state.marketAudit.indicationOnly||0).toLocaleString()}</b></div>
      <div class="stat"><span>Linked and dated records</span><b>${Number(state.marketAudit.linkedDated||0).toLocaleString()}</b></div>
    </div>
  </div>
  <div class="panel"><h3>Artwork data limitations</h3><p>Coverage means a catalog record contains an artwork URL — not that the remote image exists or loads successfully. Broken sources may fall back to alternative paths or an unavailable placeholder. Japanese image links are not verified in bulk.</p></div>
  <div class="panel"><h3>Model boundaries</h3><p>Observed market prices, retailer asks, catalog identity and model outputs remain separate. A missing price stays missing. Fair Value and Investment Quality are research estimates, not guaranteed returns.</p></div>`;
}

function restoreDeepLink() {
  if (!location.hash.startsWith('#card=')) return;
  const id=decodeURIComponent(location.hash.slice(6));
  if (state.byId.has(id)) openViewer(id);
}

function renderAll() {
  renderMarket(); applyFilters(); renderCoverage(); renderSets(); renderWatch(); renderPortfolio(); renderCompare(); renderBacktest(); renderSources(); updatePortfolioCount(); persistCompare();
}

load().catch(e => {
  $('#catalogStatus').textContent='Failed to load compact browser catalog: '+e.message;
  $('#globalStatus').textContent='load failed';
  const grid=$('#cardGrid'); if(grid) grid.innerHTML='<div class="empty-state">Card data failed to load. Refresh the page or open the GitHub issue link from the header.</div>';
  console.error(e);
});
