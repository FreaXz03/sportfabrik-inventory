// Phone: confirm goods arrival. Expected deliveries (order confirmations,
// orders) for the active store; stock is only created once arrival is
// confirmed (rule 3). Booking in this belongs to everyone (D21).
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var el = P.el;

  var listView = document.getElementById('listView');
  var detailView = document.getElementById('detailView');
  var deliveryList = document.getElementById('deliveryList');
  var status = document.getElementById('status');
  var back = document.getElementById('back');
  var confirmButton = document.getElementById('confirm');
  var detailError = document.getElementById('detailError');

  var deliveries = [];
  var state = { delivery: null, busy: false };

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function formatDate(value) {
    return value ? value.slice(0, 10).split('-').reverse().join('.') : '—';
  }

  function renderList() {
    deliveryList.replaceChildren();
    if (!deliveries.length) { status.textContent = t('wareneingaenge.empty'); return; }
    status.textContent = '';
    deliveries.forEach(function (delivery) {
      var count = delivery.positionen.length;
      var li = el('li');
      var button = el('button');
      button.type = 'button';
      button.append(
        el('strong', null, t('wareneingaenge.document_line', { typ: t('document_types.' + delivery.dokument.typ), nummer: delivery.dokument.nummer })),
        el('span', 'm-num', String(count)),
        el('span', 'm-sub', [delivery.dokument.lieferant, formatDate(delivery.dokument.datum)].filter(Boolean).join(' · '))
      );
      button.addEventListener('click', function () { openDelivery(delivery, true); });
      li.append(button);
      deliveryList.append(li);
    });
  }

  function positionRow(position) {
    var li = el('li', 'm-position');
    var head = el('div', 'm-position-head');
    head.append(
      el('strong', null, [position.marke, position.bezeichnung].filter(Boolean).join(' ') || '—'),
      el('span', 'm-sub', [position.farbe, position.groesse].filter(Boolean).join(' · '))
    );
    var counts = el('div', 'm-position-counts');
    counts.append(
      el('span', null, t('wareneingaenge.table_expected') + ' ' + P.qty(position.menge_erwartet)),
      el('span', null, t('wareneingaenge.table_open') + ' ' + P.qty(position.menge_offen))
    );
    var input = el('input');
    input.type = 'text';
    input.inputMode = 'decimal';
    input.autocomplete = 'off';
    input.value = position.menge_offen;
    input.dataset.position = position.id;
    input.setAttribute('aria-label', t('wareneingaenge.quantity_label', { position: position.id }));
    var field = el('div', 'm-position-field');
    field.append(el('span', null, t('wareneingaenge.table_now')), input);
    li.append(head, counts, field);
    return li;
  }

  function renderDetail() {
    var delivery = state.delivery;
    if (!delivery) return;
    document.getElementById('detailType').textContent = delivery.lagerort.code + ' · ' + delivery.lagerort.name;
    document.getElementById('detailTitle').textContent = t('wareneingaenge.document_line', { typ: t('document_types.' + delivery.dokument.typ), nummer: delivery.dokument.nummer });
    document.getElementById('detailMeta').textContent = [
      delivery.dokument.lieferant ? t('wareneingaenge.supplier_prefix') + delivery.dokument.lieferant : null,
      formatDate(delivery.dokument.datum)
    ].filter(Boolean).join(' · ');
    var positions = document.getElementById('positionList');
    positions.replaceChildren();
    delivery.positionen.forEach(function (position) { positions.append(positionRow(position)); });
    var dateField = document.getElementById('dateField');
    var dateInput = document.getElementById('arrivalDate');
    dateField.hidden = !delivery.lagerort.verkauf;
    document.getElementById('noDateHint').hidden = !!delivery.lagerort.verkauf;
    if (delivery.lagerort.verkauf && !dateInput.value) dateInput.value = today();
    confirmButton.disabled = state.busy;
  }

  function openDelivery(delivery, push) {
    if (push) history.pushState({ v: delivery.id }, '', '?v=' + delivery.id);
    state.delivery = delivery;
    detailError.hidden = true;
    listView.hidden = true;
    detailView.hidden = false;
    window.scrollTo(0, 0);
    renderDetail();
  }

  function showList() {
    state.delivery = null;
    detailView.hidden = true;
    listView.hidden = false;
  }

  function fromUrl() {
    var id = Number(new URLSearchParams(location.search).get('v'));
    var delivery = id ? deliveries.find(function (d) { return d.id === id; }) : null;
    if (delivery) { openDelivery(delivery, false); return; }
    if (id) history.replaceState(null, '', location.pathname);
    showList();
  }

  async function load() {
    status.textContent = t('wareneingaenge.loading');
    try {
      var data = await P.fetchJson('/api/wareneingaenge');
      deliveries = data.wareneingaenge;
      renderList();
      fromUrl();
    } catch (error) {
      status.textContent = error.message;
    }
  }

  confirmButton.addEventListener('click', async function () {
    var delivery = state.delivery;
    if (!delivery || state.busy) return;
    var mengen = {};
    document.querySelectorAll('#positionList input[data-position]').forEach(function (input) {
      var value = input.value.trim();
      if (value !== '' && Number(value) !== 0) mengen[input.dataset.position] = value;
    });
    state.busy = true;
    detailError.hidden = true;
    confirmButton.classList.add('is-loading');
    confirmButton.disabled = true;
    try {
      var dateInput = document.getElementById('arrivalDate');
      var result = await P.fetchJson('/api/wareneingaenge/' + delivery.id + '/ankunft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mengen: mengen, eingangsdatum: delivery.lagerort.verkauf ? dateInput.value : null })
      });
      var message = result.status === 'eingetroffen'
        ? t('wareneingaenge.confirmed_complete')
        : t('wareneingaenge.confirmed_partial', { offen: result.offene_positionen });
      var over = result.mehrlieferungen || [];
      if (over.length) message += ' ' + t('wareneingaenge.over_delivery', { anzahl: over.length });
      history.back();
      await load();
      status.textContent = message;
    } catch (error) {
      detailError.hidden = false;
      detailError.textContent = error.message;
    } finally {
      state.busy = false;
      confirmButton.classList.remove('is-loading');
      confirmButton.disabled = false;
    }
  });

  back.addEventListener('click', function (event) {
    if (!detailView.hidden) { event.preventDefault(); history.back(); }
  });
  window.addEventListener('popstate', fromUrl);
  document.addEventListener('sportfabrik:i18n-ready', function () {
    if (state.delivery) renderDetail(); else renderList();
  });

  if (location.search && !/^\?v=\d+$/.test(location.search)) history.replaceState(null, '', location.pathname);
  load();
})();
