const $ = (id) => document.getElementById(id);
const t = (...a) => window.SportfabrikI18n.t(...a);
let page = 1,
  total = 0,
  controller = null,
  filters = new URLSearchParams();
const pageSize = 100;
let sortBy = 'brand',
  sortDir = 'asc';

window.articleExportParams = () => { const params = new URLSearchParams(filters); params.set('sort_by', sortBy); params.set('sort_dir', sortDir); return params; };
function cell(value) {
  const td = document.createElement('td');
  td.textContent = value ?? '—';
  return td;
}

function date(value) {
  if (!value) return '—';
  return value.split('-').reverse().join('.');
}

async function load() {
  if (controller) controller.abort();
  const current = new AbortController();
  controller = current;

  $('status').textContent = t('articles.loading');
  $('table').hidden = true;
  $('prev').disabled = true;
  $('next').disabled = true;

  const params = new URLSearchParams(filters);
  params.set('page', page);
  params.set('page_size', pageSize);
  params.set('sort_by', sortBy);
  params.set('sort_dir', sortDir);

  try {
    const response = await fetch('/api/articles?' + params, { signal: current.signal });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : t('articles.search_failed'));
    }

    if (controller !== current) return;

    total = data.total;
    const fragment = document.createDocumentFragment();

    for (const item of data.items) {
      // Aufbau wie im Bestand (24.09.2026): Kategorie zuerst, Marke und
      // Bezeichnung in einer Zelle, Lieferanten-Nr. und EAN in einer.
      const tr = document.createElement('tr');
      tr.append(cell(window.SportfabrikKategorien.name(item.kategorie) || null));
      const link = document.createElement('a');
      link.href = '/articles/' + item.id + '/history';
      link.textContent = [item.brand, item.description].filter(Boolean).join(' ') || t('articles.view_article');
      const name = document.createElement('strong');
      name.append(link);
      const artikel = document.createElement('td');
      artikel.append(name);
      const nummern = cell(item.supplier_article_no);
      if (item.ean) {
        const ean = document.createElement('span');
        ean.className = 'muted';
        ean.textContent = item.ean;
        nummern.append(document.createElement('br'), ean);
      }
      tr.append(artikel, nummern);

      for (const value of [
        item.color,
        item.size,
        item.delivered
          .map((d) => `${d.quantity ?? t('articles.delivered_quantity_unknown')} ${d.unit ?? t('articles.delivered_unit_unknown')}`)
          .join(' / ') || '—',
        item.latest_uvp !== null ? `${item.latest_uvp} CHF` : null,
        date(item.uvp_date),
        date(item.first_seen),
        date(item.last_seen)
      ]) {
        tr.append(cell(value));
      }

      fragment.append(tr);
    }

    $('rows').replaceChildren(fragment);
    $('table').hidden = !data.items.length;
    $('status').classList.toggle('empty-state', !total);
    $('status').textContent = total
      ? t('articles.status.found', { total, from: Math.min((page - 1) * pageSize + 1, total), to: Math.min(page * pageSize, total) })
      : filters.toString()
        ? t('articles.status.no_results')
        : t('articles.status.empty');
    $('page').textContent = t('articles.status.page', { page, total: Math.max(1, Math.ceil(total / pageSize)) });
    $('prev').disabled = page <= 1;
    $('next').disabled = page * pageSize >= total;
  } catch (error) {
    if (error.name === 'AbortError') return;
    $('status').classList.remove('empty-state');
    $('status').textContent =
      error.message === 'Failed to fetch'
        ? t('articles.errors.connection_lost')
        : error.message;
    $('page').textContent = '';
  }
}

// Filter aus der Adresse - die Links unter „Anstehend" in der Übersicht
// (24.09.2026). Gut sichtbar angezeigt, mit einem Knopf zurück zu allen.
const VORGABEN = { ohne_ean: 'articles.filter_active.no_ean', kategorie_fehlt: 'articles.filter_active.no_category' };
let vorgabe = null;
const adresse = new URLSearchParams(location.search);
for (const key of Object.keys(VORGABEN)) {
  if (adresse.get(key) === 'true') {
    vorgabe = key;
    filters.set(key, 'true');
  }
}
// „Anstehend" je Filiale (28.09.2026): nur Varianten mit Bestand dort.
const vorgabeFiliale = vorgabe && /^\d+$/.test(adresse.get('lagerort_id') || '') ? (adresse.get('filiale') || '') : null;
if (vorgabeFiliale !== null) filters.set('lagerort_id', adresse.get('lagerort_id'));
if (vorgabe === 'kategorie_fehlt') $('kategorien').value = 'ohne';
function vorgabeZeigen() {
  $('vorgabe').hidden = !vorgabe;
  if (vorgabe) $('vorgabeText').textContent = t('filter_active.label') + ' ' + t(VORGABEN[vorgabe]) + (vorgabeFiliale ? ' · ' + vorgabeFiliale : '');
}
function vorgabeWeg() {
  vorgabe = null;
  vorgabeZeigen();
  history.replaceState(null, '', location.pathname);
}
$('vorgabeWeg').addEventListener('click', () => {
  filters.delete('ohne_ean');
  filters.delete('kategorie_fehlt');
  filters.delete('lagerort_id');
  $('kategorien').value = '';
  vorgabeWeg();
  page = 1;
  load();
});
document.addEventListener('sportfabrik:i18n-ready', vorgabeZeigen);
vorgabeZeigen();

$('filters').addEventListener('submit', (event) => {
  event.preventDefault();
  // Eine neue Suche ersetzt den Filter aus der Übersicht.
  if (vorgabe) vorgabeWeg();
  filters = new URLSearchParams([...new FormData(event.target)].filter(([, value]) => value !== ''));
  // Ein Auswahlfeld, zwei Server-Parameter: „ohne" ist keine Kategorie-Id.
  const kategorie = filters.get('kategorie');
  filters.delete('kategorie');
  if (kategorie === 'ohne') filters.set('kategorie_fehlt', 'true');
  else if (kategorie) filters.set('kategorie_id', kategorie);
  page = 1;
  load();
});

// Scanner schicken nach dem Barcode ein Enter - sofort suchen und das
// Feld für den nächsten Scan markieren (23.09.2026: EAN-Feld zuerst).
$('eanSuche').addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  $('filters').requestSubmit();
  $('eanSuche').select();
});

// `autofocus` greift nicht in jedem Browser, wenn die Seite aus dem Menü
// geöffnet wird - das EAN-Feld hier ausdrücklich aktiv setzen (23.09.2026).
$('eanSuche').focus();

$('resetBtn').addEventListener('click', () => {
  $('filters').reset();
  if (vorgabe) vorgabeWeg();
  $('eanSuche').focus();
  filters = new URLSearchParams();
  page = 1;
  load();
});

$('prev').addEventListener('click', () => {
  page--;
  load();
});

$('next').addEventListener('click', () => {
  page++;
  load();
});

async function brands() {
  try {
    const response = await fetch('/api/brands');
    if (!response.ok) throw new Error();

    for (const brand of await response.json()) {
      $('brands').add(new Option(brand, brand));
    }
  } catch {
    $('brands').disabled = true;
    $('brands').title = t('articles.errors.brands_failed');
  }
}

async function kategorien() {
  try {
    const response = await fetch('/api/kategorien');
    if (!response.ok) throw new Error();

    const select = $('kategorien');
    let group = null;
    for (const kategorie of (await response.json()).items) {
      if (!group || group.label !== kategorie.hauptgruppe) {
        group = document.createElement('optgroup');
        group.label = kategorie.hauptgruppe;
        select.append(group);
      }
      // Voller Name: zugeklappt zeigt das Auswahlfeld nur den Eintrag.
      group.append(new Option(window.SportfabrikKategorien.name(kategorie), kategorie.id));
    }
  } catch {
    $('kategorien').title = t('articles.errors.kategorien_failed');
  }
}

function updateSortIndicators() {
  document.querySelectorAll('#table thead th.sortable').forEach((th) => {
    th.classList.toggle('sort-asc', th.dataset.sort === sortBy && sortDir === 'asc');
    th.classList.toggle('sort-desc', th.dataset.sort === sortBy && sortDir === 'desc');
  });
}

document.querySelectorAll('#table thead th.sortable').forEach((th) => {
  th.addEventListener('click', () => {
    const col = th.dataset.sort;

    if (sortBy === col) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortBy = col;
      sortDir = 'asc';
    }

    page = 1;
    updateSortIndicators();
    load();
  });
});

updateSortIndicators();

const COLUMN_STORAGE_KEY = 'sportfabrikArticlesHiddenColumnsV4';

function loadHiddenColumns() {
  try {
    return new Set(JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY)) || []);
  } catch {
    return new Set();
  }
}

function saveHiddenColumns(set) {
  try {
    localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify([...set]));
  } catch {
    // ignored
  }
}

function applyColumnVisibility(hidden) {
  const table = $('articlesTable');
  table.className = '';

  for (const col of hidden) {
    table.classList.add('hide-col-' + col);
  }
}

const hiddenColumns = loadHiddenColumns();

document.querySelectorAll('#columnPicker input[type=checkbox]').forEach((cb) => {
  const col = cb.dataset.col;
  cb.checked = !hiddenColumns.has(col);

  cb.addEventListener('change', () => {
    if (cb.checked) hiddenColumns.delete(col);
    else hiddenColumns.add(col);

    applyColumnVisibility(hiddenColumns);
    saveHiddenColumns(hiddenColumns);
  });
});

applyColumnVisibility(hiddenColumns);
brands();
kategorien();
load();
document.addEventListener('sportfabrik:i18n-ready', load);
