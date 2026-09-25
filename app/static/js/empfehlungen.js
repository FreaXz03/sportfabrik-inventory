// Empfehlung der Zentrale (D-F3, 25.09.2026): je Modell und Filiale eine
// Stufe ab einem Datum vorschlagen; Übersicht mit dem Antwortstatus je
// Filiale (Abweichungen).
(() => {
  if (location.pathname !== '/empfehlungen') return;
  const $ = id => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const node = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
  const heute = () => new Date().toISOString().slice(0, 10);
  let lagerorte = [];

  async function api(path, options) {
    const r = await fetch(path, options);
    let data;
    try { data = await r.json(); } catch { data = null; }
    if (!r.ok) throw new Error((data && typeof data.detail === 'string') ? data.detail : t('common.errors.request_failed'));
    return data;
  }

  function statusLabel(zeile) {
    if (zeile.status === 'offen') return t('empfehlung.status.offen');
    if (zeile.status === 'uebernommen') return t('empfehlung.status.uebernommen');
    return t('empfehlung.status.abgelehnt') + (zeile.ablehnungsgrund ? ' – ' + zeile.ablehnungsgrund : '');
  }

  async function ladeUebersicht() {
    $('status').textContent = t('empfehlung.loading');
    $('status').hidden = false;
    $('retry').hidden = true;
    $('listeWrap').hidden = true;
    try {
      const daten = await api('/api/empfehlungen');
      $('status').hidden = true;
      const zeilen = daten.empfehlungen || [];
      $('leer').hidden = zeilen.length > 0;
      $('listeWrap').hidden = zeilen.length === 0;
      const body = $('rows');
      body.replaceChildren();
      for (const zeile of zeilen) {
        const tr = document.createElement('tr');
        const name = [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') + (zeile.lieferanten_artikelnr ? ' (' + zeile.lieferanten_artikelnr + ')' : '');
        tr.append(
          node('td', name),
          node('td', zeile.lagerort.code + ' · ' + zeile.lagerort.name),
          node('td', '−' + zeile.prozent + ' %'),
          node('td', zeile.ab_datum.split('-').reverse().join('.')),
          node('td', statusLabel(zeile))
        );
        body.append(tr);
      }
    } catch (e) {
      $('status').textContent = e.message;
      $('retry').hidden = false;
    }
  }

  function lagerorteFuellen(quellen) {
    if (lagerorte.length) return;
    lagerorte = quellen.filter(l => l.verkauf);
    const auswahl = $('lagerort');
    for (const lagerort of lagerorte) auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, String(lagerort.id)));
  }

  function artikelZelle(marke, bezeichnung, nummer) {
    const zelle = node('td');
    zelle.append(node('strong', [marke, bezeichnung].filter(Boolean).join(' ') || '—'));
    if (nummer) zelle.append(document.createElement('br'), node('span', nummer, 'muted'));
    return zelle;
  }

  async function suchen() {
    const lagerortId = $('lagerort').value;
    if (!lagerortId) { $('sucheStatus').textContent = t('empfehlung.pick_lagerort_first'); return; }
    const q = $('sucheFeld').value.trim();
    $('sucheStatus').textContent = t('bestand.loading');
    try {
      const parameter = new URLSearchParams({ lagerort_id: lagerortId, limit: '500' });
      if (q) parameter.set('q', q);
      const ergebnis = await api('/api/bestand?' + parameter);
      const modelle = new Map();
      for (const z of ergebnis.zeilen) {
        if (!modelle.has(z.artikel_id)) modelle.set(z.artikel_id, z);
      }
      const body = document.createElement('tbody');
      for (const m of modelle.values()) {
        const tr = document.createElement('tr');
        const prozent = document.createElement('select');
        for (const wert of [30, 50, 70]) prozent.add(new Option('−' + wert + ' %', String(wert)));
        const datum = document.createElement('input');
        datum.type = 'date';
        datum.value = heute();
        const knopf = node('button', t('empfehlung.set'));
        knopf.type = 'button';
        knopf.addEventListener('click', async () => {
          knopf.disabled = true;
          try {
            await api('/api/empfehlungen', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                artikel_id: m.artikel_id,
                lagerort_id: Number(lagerortId),
                prozent: Number(prozent.value),
                ab_datum: datum.value,
              }),
            });
            $('sucheStatus').textContent = t('empfehlung.set_done', { artikel: m.marke + ' ' + m.bezeichnung });
            ladeUebersicht();
          } catch (e) {
            $('sucheStatus').textContent = e.message;
          } finally {
            knopf.disabled = false;
          }
        });
        const prozentZelle = node('td');
        prozentZelle.append(prozent);
        const datumZelle = node('td');
        datumZelle.append(datum);
        const aktionZelle = node('td');
        aktionZelle.append(knopf);
        tr.append(artikelZelle(m.marke, m.bezeichnung, m.lieferanten_artikelnr), prozentZelle, datumZelle, aktionZelle);
        body.append(tr);
      }
      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const kopf = document.createElement('tr');
      for (const key of ['bestand.table_article', 'empfehlung.table_prozent', 'empfehlung.table_ab', 'empfehlung.table_actions']) kopf.append(node('th', t(key)));
      thead.append(kopf);
      table.append(thead, body);
      $('treffer').replaceChildren(modelle.size ? table : '');
      $('sucheStatus').textContent = modelle.size ? '' : t('reduktion_wahl.pick_none');
    } catch (e) {
      $('sucheStatus').textContent = e.message;
    }
  }

  $('suchen').addEventListener('click', suchen);
  $('sucheFeld').addEventListener('keydown', (ereignis) => { if (ereignis.key === 'Enter') { ereignis.preventDefault(); suchen(); } });
  $('retry').addEventListener('click', ladeUebersicht);

  window.SportfabrikI18n.ready.then(async () => {
    const stammdaten = await api('/api/umlagerung/stammdaten');
    lagerorteFuellen(stammdaten.quellen);
    ladeUebersicht();
  });
})();
