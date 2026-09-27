(() => {
  if (location.pathname !== '/statistiken') return;
  const $ = id => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const node = (tag, text) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; };
  const chf = value => new Intl.NumberFormat('de-CH', { style: 'currency', currency: 'CHF' }).format(Number(value));
  const menge = value => new Intl.NumberFormat('de-CH').format(Number(value));
  let lagerorteGesetzt = false;

  function svgNode(tag, attributes, text) {
    const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attributes)) e.setAttribute(k, v);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function kategorieLabel(zeile) {
    if (!zeile.hauptgruppe) return t('statistik.no_category');
    return zeile.sportbereich ? zeile.hauptgruppe + ' · ' + zeile.sportbereich : zeile.hauptgruppe;
  }

  function drawKategorien(kategorien) {
    $('kategorienLeer').hidden = !!kategorien.length;
    const container = $('kategorienChart');
    container.replaceChildren();
    if (!kategorien.length) return;
    const max = Math.max(...kategorien.map(k => Number(k.stueck)));
    const rowHeight = 28;
    const height = kategorien.length * rowHeight + 10;
    const svg = svgNode('svg', { viewBox: `0 0 900 ${height}`, class: 'price-chart', role: 'img', 'aria-label': t('statistik.kategorien_heading') });
    kategorien.forEach((zeile, index) => {
      const y = index * rowHeight + 5;
      const wert = Number(zeile.stueck);
      const breite = max > 0 ? (wert / max) * 620 : 0;
      svg.append(
        svgNode('text', { x: 0, y: y + 15, fill: 'var(--text)', 'font-size': 13 }, kategorieLabel(zeile)),
        svgNode('rect', { x: 260, y, width: Math.max(breite, 2), height: rowHeight - 8, fill: 'var(--accent)' }),
        svgNode('text', { x: 260 + breite + 8, y: y + 15, fill: 'var(--text-muted)', 'font-size': 13 }, menge(zeile.stueck))
      );
    });
    container.append(svg);
  }

  function drawEmpfehlung(zeilen) {
    const body = $('empfehlungRows');
    body.replaceChildren();
    for (const zeile of zeilen) {
      const tr = document.createElement('tr');
      const name = [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') + (zeile.lieferanten_artikelnr ? ' (' + zeile.lieferanten_artikelnr + ')' : '');
      tr.append(node('td', name), node('td', menge(zeile.verkauft)), node('td', menge(zeile.bestand)));
      body.append(tr);
    }
  }

  function lagerorteFuellen(lagerorte) {
    if (lagerorteGesetzt) return;
    const auswahl = $('lagerort');
    const alle = new Option(t('statistik.filter_lagerort_alle'), '');
    auswahl.add(alle);
    for (const lagerort of lagerorte) {
      auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, String(lagerort.id)));
    }
    lagerorteGesetzt = true;
  }

  async function laden() {
    $('status').textContent = t('statistik.loading');
    $('status').hidden = false;
    $('retry').hidden = true;
    for (const id of ['einnahmenPanel', 'kategorienPanel', 'empfehlungPanel']) $(id).hidden = true;
    try {
      const parameter = new URLSearchParams({ zeitraum: $('zeitraum').value });
      if ($('lagerort').value) parameter.set('lagerort_id', $('lagerort').value);
      const antwort = await fetch('/api/statistik?' + parameter.toString());
      if (!antwort.ok) throw new Error(t('common.errors.request_failed'));
      const daten = await antwort.json();
      lagerorteFuellen(daten.lagerorte || []);
      $('status').hidden = true;
      $('einnahmenBetrag').textContent = chf(daten.einnahmen_geschaetzt);
      $('einnahmenPanel').hidden = false;
      drawKategorien(daten.kategorien);
      $('kategorienPanel').hidden = false;
      drawEmpfehlung(daten.bestellempfehlung);
      $('empfehlungPanel').hidden = false;
    } catch (e) {
      $('status').textContent = e.message;
      $('retry').hidden = false;
    }
  }

  $('retry').addEventListener('click', laden);
  $('zeitraum').addEventListener('change', laden);
  $('lagerort').addEventListener('change', laden);
  window.SportfabrikI18n.ready.then(laden);
})();
