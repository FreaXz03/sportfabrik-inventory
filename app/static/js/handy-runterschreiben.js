// Phone: which items have reached -50%/-70% in this store or will within 30
// days (rule 6), with a "Done" button, plus setting a manual reduction by
// hand. Reading and setting follow the same store limits as elsewhere
// (rule 9, checked server-side).
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var el = P.el;

  var lagerortSelect = document.getElementById('lagerort');
  var status = document.getElementById('status');
  var gruppenBox = document.getElementById('gruppen');
  var pickView = document.getElementById('pickView');
  var itemView = document.getElementById('itemView');
  var itemHint = document.getElementById('itemHint');
  var itemButtons = document.getElementById('itemButtons');
  var itemStatus = document.getElementById('itemStatus');
  var manuellListe = document.getElementById('manuellListe');
  var manuellLeer = document.getElementById('manuellLeer');

  var daten = null;
  var item = null;
  var wahl = null; // explicit lagerort_id, or null = server decides (active store)

  function datum(value) {
    return value ? value.split('-').reverse().join('.') : '—';
  }

  function stageChip(prozent) {
    var chip = el('span', 'chip chip-stage');
    chip.dataset.stage = String(prozent);
    chip.append(el('span', 'chip-dot'), document.createTextNode('−' + prozent + ' %'));
    return chip;
  }

  function artikelKarte(a) {
    var card = el('li', 'm-position');
    var head = el('div', 'm-position-head');
    head.append(
      el('strong', null, [a.marke, a.bezeichnung].filter(Boolean).join(' ') || '—'),
      el('span', 'm-sub', a.lieferanten_artikelnr || '')
    );
    var counts = el('div', 'm-position-counts');
    counts.append(
      stageChip(a.stufe),
      el('span', null, t('reduktion.table_variants') + ': ' + a.varianten),
      el('span', null, t('reduktion.table_pieces') + ': ' + P.qty(a.stueck)),
      el('span', null, t('reduktion.table_arrival') + ': ' + datum(a.eingang))
    );
    card.append(head, counts);
    if (a.stand === 'faellig') {
      var field = el('div', 'm-position-field');
      var button = el('button', 'secondary', t('reduktion.confirm'));
      button.type = 'button';
      button.addEventListener('click', async function () {
        button.disabled = true;
        button.classList.add('is-loading');
        try {
          await P.fetchJson('/api/reduktionen/bestaetigen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ artikel_id: a.artikel_id, lagerort_id: daten.lagerort.id, stufe: a.stufe })
          });
          status.textContent = t('reduktion.confirmed', { artikel: [a.marke, a.bezeichnung].filter(Boolean).join(' ') });
          await load();
        } catch (error) {
          button.disabled = false;
          button.classList.remove('is-loading');
          status.textContent = error.message;
        }
      });
      field.append(button);
      card.append(field);
    }
    return card;
  }

  function renderGroups() {
    gruppenBox.replaceChildren();
    ['faellig', 'bald'].forEach(function (stand) {
      [70, 50].forEach(function (stufe) {
        var eintraege = daten.artikel.filter(function (a) { return a.stand === stand && a.stufe === stufe; });
        if (!eintraege.length) return;
        var section = el('section');
        section.append(el('h2', null, t('reduktion.group_' + stand, { stufe: stufe })));
        var list = el('ul', 'm-positions');
        eintraege.forEach(function (a) { list.append(artikelKarte(a)); });
        section.append(list);
        gruppenBox.append(section);
      });
    });
    status.textContent = daten.artikel.length ? t('reduktion.count_line', { anzahl: daten.artikel.length }) : t('reduktion.empty');
  }

  function renderManuell() {
    var liste = daten.manuell || [];
    manuellLeer.hidden = liste.length > 0;
    manuellListe.hidden = liste.length === 0;
    manuellListe.replaceChildren();
    liste.forEach(function (a) {
      var card = el('li', 'm-position');
      var head = el('div', 'm-position-head');
      head.append(
        el('strong', null, [a.marke, a.bezeichnung].filter(Boolean).join(' ') || '—'),
        el('span', 'm-sub', [a.gesetzt_von, datum((a.gesetzt_am || '').slice(0, 10))].filter(Boolean).join(' · '))
      );
      var counts = el('div', 'm-position-counts');
      counts.append(stageChip(a.prozent));
      card.append(head, counts);
      manuellListe.append(card);
    });
  }

  function fillLagerort() {
    if (lagerortSelect.options.length) return;
    daten.lagerorte.forEach(function (lo) { lagerortSelect.add(new Option(lo.code + ' · ' + lo.name, lo.id)); });
    lagerortSelect.value = String(daten.lagerort.id);
  }

  async function load() {
    status.textContent = t('reduktion.loading');
    try {
      var data = await P.fetchJson('/api/reduktionen' + (wahl ? '?lagerort_id=' + wahl : ''));
      daten = data;
      fillLagerort();
      renderGroups();
      renderManuell();
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function showPick() {
    item = null;
    itemView.hidden = true;
    pickView.hidden = false;
  }

  async function openItem(picked) {
    item = picked;
    pickView.hidden = true;
    itemView.hidden = false;
    itemStatus.textContent = '';
    document.getElementById('itemBrand').textContent = item.brand || '';
    document.getElementById('itemTitle').textContent = item.description || '';
    document.getElementById('itemVariant').textContent = P.variantText(item);
    itemHint.textContent = t('reduktion_wahl.pick_hint');
    itemButtons.replaceChildren();
    window.scrollTo(0, 0);
    try {
      var data = await P.fetchJson('/api/articles/' + item.id + '/reduktion');
      var eintrag = data.filialen.find(function (f) { return f.lagerort.id === daten.lagerort.id; });
      if (!eintrag) { itemHint.textContent = t('reduktion.load_error'); return; }
      itemHint.textContent = eintrag.lagerort.code + ' · ' + eintrag.lagerort.name;
      if (!eintrag.darf_aendern) {
        itemStatus.textContent = t('errors.auth.no_lagerort_access');
        return;
      }
      itemButtons.append(window.SportfabrikReduktion.knoepfe(item.id, daten.lagerort.id, eintrag, function (neu) {
        itemStatus.textContent = t('reduktion_wahl.saved', { filiale: daten.lagerort.code, stufe: window.SportfabrikReduktion.text(neu) });
        load();
      }, itemStatus));
    } catch (error) {
      itemHint.textContent = error.message;
    }
  }

  var pick = P.picker({
    container: document.getElementById('picker'),
    onPick: openItem
  });

  document.getElementById('other').addEventListener('click', function () { showPick(); pick.clear(); });
  lagerortSelect.addEventListener('change', function () {
    wahl = lagerortSelect.value;
    load();
  });
  document.addEventListener('sportfabrik:i18n-ready', function () {
    if (daten) { renderGroups(); renderManuell(); }
  });

  load();
})();
