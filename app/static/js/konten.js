(() => {
  if (location.pathname !== '/konten') return;
  const $ = id => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const node = (tag, text) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; };
  let lagerorte = [];
  let konten = [];

  async function api(path, options) {
    const r = await fetch(path, options);
    let data;
    try { data = await r.json(); } catch { data = null; }
    if (!r.ok) throw new Error((data && typeof data.detail === 'string') ? data.detail : t('common.errors.request_failed'));
    return data;
  }

  function roleLabel(role) { return t('role.' + role); }

  function filialenLabel(lagerort_ids) {
    if (!lagerort_ids.length) return t('konten.no_lagerorte');
    return lagerort_ids
      .map(id => { const lo = lagerorte.find(l => l.id === id); return lo ? lo.code : id; })
      .join(', ');
  }

  function zeichneListe() {
    const body = $('rows');
    body.replaceChildren();
    for (const konto of konten) {
      const tr = document.createElement('tr');
      const loeschKnopf = document.createElement('button');
      loeschKnopf.type = 'button';
      loeschKnopf.className = 'secondary';
      loeschKnopf.textContent = t('konten.delete');
      loeschKnopf.addEventListener('click', () => loeschen(konto));
      const zelle = document.createElement('td');
      zelle.append(loeschKnopf);
      tr.append(
        node('td', konto.kassennummer),
        node('td', konto.name),
        node('td', roleLabel(konto.role)),
        node('td', filialenLabel(konto.lagerort_ids)),
        zelle
      );
      body.append(tr);
    }
  }

  async function loeschen(konto) {
    if (!confirm(t('konten.delete_confirm', { name: konto.name }))) return;
    try {
      await api('/api/konten/' + konto.id, { method: 'DELETE' });
      konten = konten.filter(k => k.id !== konto.id);
      zeichneListe();
    } catch (e) {
      alert(e.message);
    }
  }

  function zeichneFilialen() {
    const fieldset = $('neuFilialen');
    fieldset.querySelectorAll('label').forEach(el => el.remove());
    for (const lagerort of lagerorte) {
      const label = document.createElement('label');
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.value = String(lagerort.id);
      box.className = 'filiale-checkbox';
      label.append(box, document.createTextNode(' ' + lagerort.code + ' · ' + lagerort.name));
      fieldset.append(label);
    }
  }

  function aktualisierePasswortfeld() {
    const braucht = $('neuRole').value !== 'mitarbeiter';
    $('neuPasswortFeld').hidden = !braucht;
  }

  async function anlegen() {
    $('neuStatus').textContent = '';
    const role = $('neuRole').value;
    const lagerort_ids = Array.from($('neuFilialen').querySelectorAll('.filiale-checkbox:checked')).map(b => Number(b.value));
    const body = {
      kassennummer: $('neuKassennummer').value.trim(),
      name: $('neuName').value.trim(),
      role,
      lagerort_ids,
    };
    if (role !== 'mitarbeiter') body.password = $('neuPasswort').value;
    try {
      const konto = await api('/api/konten', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      konten.push(konto);
      zeichneListe();
      $('neuKassennummer').value = '';
      $('neuName').value = '';
      $('neuPasswort').value = '';
      $('neuFilialen').querySelectorAll('.filiale-checkbox').forEach(b => { b.checked = false; });
      $('neuStatus').textContent = t('konten.created', { name: konto.name });
    } catch (e) {
      $('neuStatus').textContent = e.message;
    }
  }

  async function laden() {
    $('status').textContent = t('konten.loading');
    $('retry').hidden = true;
    try {
      const daten = await api('/api/konten');
      konten = daten.konten;
      $('status').hidden = true;
      zeichneListe();
    } catch (e) {
      $('status').textContent = e.message;
      $('retry').hidden = false;
    }
  }

  async function stammdaten() {
    const daten = await api('/api/umlagerung/stammdaten');
    lagerorte = daten.quellen.filter(l => l.verkauf);
    zeichneFilialen();
  }

  $('retry').addEventListener('click', laden);
  $('anlegen').addEventListener('click', anlegen);
  $('neuRole').addEventListener('change', aktualisierePasswortfeld);
  window.SportfabrikI18n.ready.then(async () => {
    aktualisierePasswortfeld();
    await stammdaten();
    await laden();
  });
})();
