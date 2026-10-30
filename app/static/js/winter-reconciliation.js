(function () {
  const $ = id => document.getElementById(id);
  const t = (...args) => window.SportfabrikI18n.t(...args);
  const node = (tag, text) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; return el; };
  let view = null, sourceFile = null, targetLabels = new Map(), controls = [], busy = false;
  function reset() { view = null; $('winterReview').hidden = true; $('winterApply').disabled = true; }
  async function request(url, body) {
    const response = await fetch(url, body ? { method: 'POST', body } : {});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : t('wareneingaenge.load_error'));
    return data;
  }
  function selections() {
    const result = {};
    for (const c of controls) if (c.check.checked && targetLabels.has(c.input.value)) result[c.group.key] = targetLabels.get(c.input.value);
    return result;
  }
  function update(changed = true) {
    if (!view) return;
    if (changed) $('winterConfirmed').checked = false;
    const targets = new Map();
    let valid = true, selected = 0;
    for (const c of controls) {
      const id = targetLabels.get(c.input.value), original = view.originals.find(o => o.id === id);
      c.message.textContent = c.group.warnings.join(' ') + (c.group.applied ? ' ' + t('winter.already_used') : '');
      if (!original) c.message.append(node('span', t('winter.needs_match')));
      else {
        c.message.append(node('span', t('winter.compare', { old: original.quantity, current: c.group.quantity })));
        if (original.blocked) c.message.append(node('span', ' ' + t('winter.already_received')));
      }
      if (c.check.checked) {
        selected++;
        if (!original || original.blocked || c.group.applied || c.group.warnings.length) valid = false;
        if (original) targets.set(id, (targets.get(id) || 0) + Number(c.group.quantity));
      }
    }
    let oldTotal = 0, newTotal = 0, mismatch = false;
    for (const [id, quantity] of targets) {
      const old = Number(view.originals.find(o => o.id === id).quantity);
      oldTotal += old; newTotal += quantity; mismatch ||= old !== quantity;
    }
    const revision = $('winterRevise').checked;
    $('winterReason').disabled = !revision;
    if (mismatch && (!revision || $('winterReason').value.trim().length < 10)) valid = false;
    $('winterSelected').textContent = t('winter.selection_summary', { count: selected, old: oldTotal, current: newTotal, unchanged: view.originals.length - targets.size }) + (mismatch ? ' ' + t('winter.quantity_conflict') : '');
    $('winterApply').disabled = busy || !selected || !valid || !$('winterConfirmed').checked;
  }
  function render() {
    controls = []; targetLabels = new Map();
    $('winterTargets').replaceChildren(); $('winterOriginals').replaceChildren();
    const labels = new Map();
    for (const original of view.originals) {
      const label = original.name + ' · ' + original.quantity + ' · ' + Object.keys(original.sizes).join(' / ') + ' [' + original.id + ']';
      targetLabels.set(label, original.id); labels.set(original.id, label);
      const option = node('option'); option.value = label; $('winterTargets').append(option);
      $('winterOriginals').append(node('li', label));
    }
    const fragment = document.createDocumentFragment();
    for (const group of view.groups) {
      const row = node('tr'), choose = node('td'), check = node('input'); check.type = 'checkbox'; check.setAttribute('aria-label', t('winter.choose') + ': ' + group.name);
      const original = view.originals.find(o => o.id === group.target_id);
      check.checked = !!original && original.quantity * 1 === group.quantity * 1 && !original.blocked && !group.applied && !group.warnings.length;
      check.disabled = group.applied || !!group.warnings.length;
      choose.append(check); row.append(choose);
      const description = node('td'); description.append(node('strong', group.name));
      for (const source of group.rows) description.append(node('p', t('winter.source', { page: source.page, paired: source.paired_page, section: source.section, number: source.printed_article_no || '—' })));
      row.append(description, node('td', Object.entries(group.sizes).map(([size, q]) => size + ': ' + q).join(' · ') || '0'));
      const target = node('td'), input = node('input'); input.type = 'text'; input.setAttribute('list', 'winterTargets'); input.setAttribute('aria-label', t('winter.target') + ': ' + group.name);
      input.value = labels.get(group.target_id) || ''; target.append(input); row.append(target);
      const message = node('td'); row.append(message);
      controls.push({ group, check, input, message });
      check.addEventListener('change', () => update()); input.addEventListener('input', () => update()); fragment.append(row);
    }
    $('winterRows').replaceChildren(fragment);
    $('winterTotals').textContent = t('winter.totals', { branch: view.branch, old: view.original_total, current: view.new_total });
    $('winterHistory').replaceChildren();
    for (const h of view.history) {
      const detail = node('details'); detail.append(node('summary', h.filename + ' · ' + h.date + ' · ' + (h.actor || '—')));
      if (h.reason) detail.append(node('p', h.reason));
      detail.append(node('p', t('winter.before')));
      for (const r of h.before) detail.append(node('p', r.name + ' · ' + r.size + ': ' + r.expected));
      detail.append(node('p', t('winter.after')));
      for (const r of h.after) detail.append(node('p', r.size + ': ' + r.quantity));
      $('winterHistory').append(detail);
    }
    $('winterRevise').checked = false; $('winterReason').value = ''; $('winterReview').hidden = false; update();
  }
  function body() { const data = new FormData(); data.append('file', sourceFile); return data; }
  $('winterUpload').addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    reset(); sourceFile = $('winterFile').files[0]; if (!sourceFile) return;
    busy = true; $('winterUpload').inert = true; $('winterRead').disabled = true; $('winterStatus').textContent = t('winter.loading');
    try {
      view = await request('/api/winter-abgleich/' + $('winterOrder').value + '/vorschau', body()); render(); $('winterStatus').textContent = '';
    } catch (error) { $('winterStatus').textContent = error.message; }
    finally { busy = false; $('winterUpload').inert = false; $('winterRead').disabled = false; update(false); }
  });
  for (const id of ['winterFile', 'winterOrder']) $(id).addEventListener('change', reset);
  for (const id of ['winterRevise', 'winterReason']) $(id).addEventListener('input', () => update());
  $('winterConfirmed').addEventListener('change', () => update(false));
  $('winterApply').addEventListener('click', async () => {
    if (busy || $('winterApply').disabled || !view) return;
    if (!window.confirm(t($('winterRevise').checked ? 'winter.confirm_revision' : 'winter.confirm_apply'))) return;
    const data = body(); data.append('confirmed', 'true'); data.append('fingerprint', view.fingerprint);
    data.append('selection', JSON.stringify(selections())); data.append('revise_quantities', String($('winterRevise').checked));
    data.append('reason', $('winterRevise').checked ? $('winterReason').value.trim() : '');
    busy = true; $('winterUpload').inert = true; $('winterRead').disabled = true; $('winterReview').inert = true; update(false);
    try {
      const result = await request('/api/winter-abgleich/' + $('winterOrder').value + '/uebernehmen', data);
      reset(); $('winterStatus').textContent = t(result.repeated ? 'winter.repeated' : 'winter.done');
    } catch (error) { $('winterStatus').textContent = error.message; }
    finally { busy = false; $('winterUpload').inert = false; $('winterRead').disabled = false; $('winterReview').inert = false; update(false); }
  });
  window.SportfabrikI18n.ready.then(async () => {
    try {
      const data = await request('/api/winter-abgleich');
      for (const order of data.orders) $('winterOrder').append(new Option(order.number + ' · ' + order.branch, order.id));
      const selected = new URLSearchParams(location.search).get('receipt'); if (selected) $('winterOrder').value = selected;
      if (!data.orders.length) $('winterStatus').textContent = t('winter.no_orders');
    } catch (error) { $('winterStatus').textContent = error.message; }
  });
})();
