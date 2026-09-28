// Phone article picker, shared by every phone page that starts with "which
// article?": camera scan, typed or Bluetooth-scanned EAN, supplier number or
// name. An exact EAN hit picks the article at once; otherwise the user taps a
// result. Builds its own controls inside `container`.
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var el = P.el;

  function variantText(item) {
    return [item.color, item.size].filter(Boolean).join(' · ');
  }

  function picker(options) {
    var container = options.container;
    var storeKey = options.storeKey || null;
    var state = { query: '', items: [], total: 0 };
    var seq = 0;

    var camera = el('button', 'large m-wide');
    camera.type = 'button';
    var cameraLabel = el('span');
    camera.append(P.icon('scan'), cameraLabel);

    var form = el('form', 'm-scan');
    form.setAttribute('role', 'search');
    var inputId = 'pick-' + Math.random().toString(36).slice(2);
    var label = el('label');
    label.htmlFor = inputId;
    var row = el('div', 'm-scan-row');
    var input = el('input');
    input.id = inputId;
    input.type = 'search';
    input.maxLength = 200;
    input.setAttribute('enterkeyhint', 'search');
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('autocapitalize', 'off');
    input.spellcheck = false;
    var submit = el('button', 'large secondary');
    submit.type = 'submit';
    row.append(input, submit);
    form.append(label, row);

    var status = el('p', 'muted');
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    var list = el('ul', 'm-list');
    container.append(camera, form, status, list);

    function texts() {
      cameraLabel.textContent = t('phone.scan_button');
      label.textContent = t('phone.search_label');
      submit.textContent = t('phone.search_button');
    }

    function remember() {
      if (!storeKey) return;
      try { sessionStorage.setItem(storeKey, JSON.stringify(state)); } catch (e) { }
    }

    function restore() {
      if (!storeKey) return;
      try {
        var saved = JSON.parse(sessionStorage.getItem(storeKey) || 'null');
        if (saved) { state.query = saved.query || ''; state.items = saved.items || []; state.total = saved.total || 0; }
      } catch (e) { }
      input.value = state.query;
    }

    function render() {
      texts();
      list.replaceChildren();
      if (!state.query) { status.textContent = ''; return; }
      if (!state.items.length) { status.textContent = t('phone.search_none'); return; }
      status.textContent = state.total > state.items.length
        ? t('phone.search_more', { shown: state.items.length, total: state.total })
        : t('phone.search_count', { n: state.total });
      state.items.forEach(function (item) {
        var li = el('li');
        var button = el('button');
        button.type = 'button';
        button.append(
          el('strong', null, [item.brand, item.description].filter(Boolean).join(' ')),
          el('span', 'm-num', P.money(item.latest_uvp) || ''),
          el('span', 'm-sub', [variantText(item), item.supplier_article_no].filter(Boolean).join(' · '))
        );
        button.addEventListener('click', function () { options.onPick(item); });
        li.append(button);
        list.append(li);
      });
    }

    async function search(query) {
      query = String(query || '').trim();
      if (!query) return;
      var mine = ++seq;
      state.query = query;
      input.value = query;
      status.textContent = t('phone.searching');
      list.replaceChildren();
      try {
        if (/^\d{8,14}$/.test(query)) {
          var exact = await P.fetchJson('/api/articles?page_size=25&ean=' + encodeURIComponent(query));
          if (mine !== seq) return;
          if (exact.items.length === 1) {
            state.items = exact.items; state.total = 1; remember();
            status.textContent = '';
            options.onPick(exact.items[0]);
            return;
          }
        }
        var data = await P.fetchJson('/api/articles?page_size=25&q=' + encodeURIComponent(query));
        if (mine !== seq) return;
        state.items = data.items; state.total = data.total;
        remember();
        render();
      } catch (error) {
        if (mine === seq) status.textContent = error.message;
      }
    }

    camera.addEventListener('click', async function () {
      var code = await P.scan();
      if (code) search(code);
    });
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      input.blur();
      search(input.value);
    });
    document.addEventListener('sportfabrik:i18n-ready', render);

    restore();
    render();
    return {
      items: function () { return state.items; },
      render: render,
      clear: function () { state.query = ''; state.items = []; state.total = 0; input.value = ''; remember(); render(); }
    };
  }

  P.picker = picker;
  P.variantText = variantText;
})();
