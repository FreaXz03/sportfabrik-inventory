const $ = (id) => document.getElementById(id);
const t = (...a) => window.SportfabrikI18n.t(...a);
const path = location.pathname;
const list = path === '/invoices';
const article = path.startsWith('/articles/');
const endpoint = list ? '/api/invoices' : '/api' + path;
let page = 1,
     q = '',
     controller = null;
const pageSize = 25;
let sortBy = '',
     sortDir = 'asc';

let canDelete = false;
const meReady = fetch('/api/me')
     .then((r) => (r.ok ? r.json() : null))
     .then((m) => {
          canDelete = !!(m && (m.role === 'chef' || m.role === 'admin'));
     })
     .catch(() => { });

// Artikel löschen (24.09.2026): nur Filialleiter/Zentrale und nur
// von Hand erfasste Artikel ohne Beleg - der Server prüft beides.
function renderArticleDeleteBox(product) {
     const box = $('deleteBox');
     if (!canDelete) {
          box.hidden = true;
          return;
     }
     box.hidden = false;
     box.replaceChildren();
     if (!product.manuell) {
          box.append(el('p', t('artikel_loeschen.has_document_hint')));
          return;
     }
     const btn = document.createElement('button');
     btn.type = 'button';
     btn.className = 'secondary danger';
     btn.textContent = t('artikel_loeschen.button');
     const msg = document.createElement('span');
     msg.className = 'warning-text';
     msg.textContent = t('artikel_loeschen.hint');
     btn.addEventListener('click', async () => {
          const name = [product.brand, product.description].filter(Boolean).join(' ');
          if (!confirm(t('artikel_loeschen.confirm', { artikel: name }))) return;
          btn.disabled = true;
          msg.textContent = t('artikel_loeschen.in_progress');
          try {
               const response = await fetch('/api/articles/' + product.id, { method: 'DELETE' });
               const result = await response.json().catch(() => ({}));
               if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : t('errors.artikel_loeschen.failed'));
               location.href = '/articles';
          } catch (error) {
               msg.textContent = error.message === 'Failed to fetch' ? t('common.connection_lost') : error.message;
               btn.disabled = false;
          }
     });
     const wrap = document.createElement('div');
     wrap.className = 'filters';
     wrap.append(btn, msg);
     box.append(wrap);
}

// Gebuchte Belege werden storniert, nicht gelöscht (Regel 2, 01.10.2026);
// nur ein Beleg ohne jede Buchung lässt sich noch löschen. Der Server prüft das.
async function renderDeleteBox(invoice) {
     const box = $('deleteBox');

     if (invoice.status === 'storniert') {
          box.hidden = false;
          box.replaceChildren(el('p', t('history.cancel.done_note', {
               date: date(invoice.cancelled_at),
               name: invoice.cancelled_by_name ?? '—'
          })));
          return;
     }

     await meReady;
     if (!canDelete) {
          box.hidden = true;
          return;
     }

     let preview;
     try {
          const response = await fetch('/api/invoices/' + invoice.id + '/cancel-preview');
          if (!response.ok) throw new Error();
          preview = await response.json();
     } catch {
          box.hidden = true;
          return;
     }
     if (preview.zeilen.length > 0) {
          renderCancelBox(invoice, preview);
          return;
     }

     box.hidden = false;
     box.replaceChildren();

     const label = el('label', t('history.delete.label'));
     const input = document.createElement('input');
     input.placeholder = invoice.invoice_number;
     input.setAttribute('aria-label', t('history.delete.confirm_aria'));

     const wrap = document.createElement('div');
     wrap.style.display = 'flex';
     wrap.style.gap = '12px';
     wrap.style.alignItems = 'center';
     wrap.style.flexWrap = 'wrap';

     const btn = document.createElement('button');
     btn.type = 'button';
     btn.textContent = t('history.delete.button');
     btn.disabled = true;
     btn.className = 'secondary';

     const msg = document.createElement('span');
     msg.className = 'muted';

     input.addEventListener('input', () => {
          btn.disabled = input.value.trim() !== invoice.invoice_number;
     });

     btn.addEventListener('click', async () => {
          btn.disabled = true;
          input.disabled = true;
          msg.textContent = t('history.delete.in_progress');

          try {
               const response = await fetch('/api/invoices/' + invoice.id, { method: 'DELETE' });
               const result = await response.json();

               if (!response.ok) {
                    throw new Error(typeof result.detail === 'string' ? result.detail : t('history.delete.failed'));
               }

               location.href = '/invoices';
          } catch (error) {
               msg.textContent = error.message;
               input.disabled = false;
               btn.disabled = input.value.trim() !== invoice.invoice_number;
          }
     });

     wrap.append(input, btn, msg);
     box.append(label, wrap);
}

function renderCancelBox(invoice, preview) {
     const box = $('deleteBox');
     box.hidden = false;
     box.replaceChildren();

     const hint = el('p', t('history.cancel.hint'));
     const msg = document.createElement('span');
     msg.className = 'muted';

     const table = document.createElement('table');
     const head = document.createElement('tr');
     for (const key of ['article', 'now', 'receipt', 'after', 'moved']) {
          head.append(el('th', t('history.cancel.col_' + key)));
     }
     table.append(head);
     for (const z of preview.zeilen) {
          const row = document.createElement('tr');
          const name = [z.marke, z.bezeichnung, z.lieferanten_artikelnr, z.farbe, z.groesse].filter(Boolean).join(' · ');
          for (const value of [name, z.bestand_jetzt, '−' + z.wareneingang, z.bestand_danach, z.spaetere_bewegungen ? t('history.cancel.yes') : '']) {
               row.append(el('td', value));
          }
          if (Number(z.bestand_danach) < 0) row.lastElementChild.previousElementSibling.className = 'warning-text';
          table.append(row);
     }

     const confirmBtn = document.createElement('button');
     confirmBtn.type = 'button';
     confirmBtn.className = 'secondary danger';
     confirmBtn.textContent = t('history.cancel.confirm_button');
     const abortBtn = document.createElement('button');
     abortBtn.type = 'button';
     abortBtn.className = 'secondary';
     abortBtn.textContent = t('history.cancel.abort');
     const wrap = document.createElement('div');
     wrap.className = 'filters';
     wrap.append(confirmBtn, abortBtn, msg);

     const openBtn = document.createElement('button');
     openBtn.type = 'button';
     openBtn.className = 'secondary';
     openBtn.textContent = t('history.cancel.button');
     const details = document.createElement('div');
     details.hidden = true;
     details.append(table);
     if (preview.hat_negativen_bestand) {
          const warn = el('p', t('history.cancel.negative_warning'));
          warn.className = 'warning-text';
          details.append(warn);
     }
     details.append(wrap);

     openBtn.addEventListener('click', () => {
          details.hidden = false;
          openBtn.hidden = true;
     });
     abortBtn.addEventListener('click', () => {
          details.hidden = true;
          openBtn.hidden = false;
     });
     confirmBtn.addEventListener('click', async () => {
          confirmBtn.disabled = true;
          abortBtn.disabled = true;
          msg.textContent = t('history.cancel.in_progress');
          try {
               const response = await fetch('/api/invoices/' + invoice.id + '/cancel', { method: 'POST' });
               const result = await response.json().catch(() => ({}));
               if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : t('history.cancel.failed'));
               location.reload();
          } catch (error) {
               msg.textContent = error.message === 'Failed to fetch' ? t('common.connection_lost') : error.message;
               confirmBtn.disabled = false;
               abortBtn.disabled = false;
          }
     });

     box.append(hint, openBtn, details);
}

function el(tag, text) {
     const n = document.createElement(tag);
     n.textContent = text ?? '—';
     return n;
}

function date(s) {
     return s ? s.slice(0, 10).split('-').reverse().join('.') : '—';
}

function importedBy(i) {
     return i.imported_by_name || i.imported_by_kassennummer || '—';
}

function sourceLabel(i) {
     return i.ocr_used ? ' ' + t('dashboard.ocr_scan_suffix') : '';
}

function link(text, url) {
     const n = el('a', text);
     n.href = url;
     return n;
}

function add(row, value) {
     const td = document.createElement('td');
     td.append(value instanceof Node ? value : document.createTextNode(value ?? '—'));
     row.append(td);
}

if (!list) {
     $('search').hidden = true;
     $('title').textContent = article ? t('history.title.article_history') : t('history.title.invoice_details');
     $('intro').textContent = t('history.intro.detail');
}

async function load() {
     await meReady;

     if (controller) controller.abort();
     const current = new AbortController();
     controller = current;

     $('retry').hidden = true;
     $('deleteBox').hidden = true;
     $('table').hidden = true;
     $('prev').disabled = true;
     $('next').disabled = true;
     $('status').textContent = t('history.loading');

     const params = new URLSearchParams({ page, page_size: pageSize });
     if (list) params.set('q', q);
     else if (sortBy) {
          params.set('sort_by', sortBy);
          params.set('sort_dir', sortDir);
     }

     try {
          const response = await fetch(endpoint + '?' + params, { signal: current.signal });
          const data = await response.json();

          if (!response.ok) {
               throw new Error(typeof data.detail === 'string' ? data.detail : t('dashboard.load_error'));
          }

          if (controller !== current) return;

          if (data.invoice) {
               $('title').textContent = t('history.invoice_title_prefix', { number: data.invoice.invoice_number });
               $('intro').textContent = t('history.invoice_intro', {
                    supplier: data.invoice.supplier ?? '',
                    invoice_date: date(data.invoice.invoice_date),
                    document_date: date(data.invoice.document_date),
                    filename: data.invoice.filename ?? '—',
                    imported_by: importedBy(data.invoice) + sourceLabel(data.invoice)
               });
               renderDeleteBox(data.invoice);
          }

          if (data.product) {
               $('title').textContent = `${data.product.brand ?? ''} ${data.product.description ?? t('history.title.article_history')}`;
               $('intro').textContent = data.product.supplier_article_no?.trim()
                    ? t('history.product_intro_with_supplier_no', { number: data.product.supplier_article_no })
                    : t('history.product_intro_without_supplier_no', { ean: data.product.ean ?? '—' });
               renderArticleDeleteBox(data.product);
          }

          const headers = list
               ? [t('history.list.col_invoice'), t('history.list.col_date'), t('history.list.col_supplier'), t('history.list.col_positions'), t('history.list.col_filename'), t('history.list.col_uploaded'), t('history.list.col_uploaded_by')]
               : [
                    t('history.detail.col_position_page'),
                    t('history.detail.col_invoice_date'),
                    t('history.detail.col_article'),
                    ...(article ? [] : [t('fields.ean')]),
                    t('history.detail.col_article_no'),
                    t('fields.color'),
                    t('fields.size'),
                    t('fields.quantity'),
                    t('fields.unit'),
                    t('fields.uvp'),
                    t('history.detail.col_raw_text')
               ];

          const hr = document.createElement('tr');
          const sortKeys = [
               'position',
               'invoice_date',
               'description',
               ...(article ? [] : ['ean']),
               'article_no',
               'color',
               'size',
               'quantity',
               'unit',
               'uvp'
          ];

          headers.forEach((h, index) => {
               const th = el('th', h);

               if (!list && sortKeys[index]) {
                    const key = sortKeys[index];
                    const active = sortBy === key;
                    th.textContent = '';
                    th.className = 'sortable' + (active ? (sortDir === 'asc' ? ' sort-asc' : ' sort-desc') : '');
                    const button = el('button', h);
                    button.type = 'button';
                    th.setAttribute('aria-sort', active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none');
                    button.addEventListener('click', () => {
                         sortDir = sortBy === key && sortDir === 'asc' ? 'desc' : 'asc';
                         sortBy = key;
                         page = 1;
                         load();
                    });
                    th.append(button);
               }

               hr.append(th);
          });

          $('head').replaceChildren(hr);

          const fragment = document.createDocumentFragment();
          for (const item of data.items) {
               const row = document.createElement('tr');

               if (list) {
                    add(row, link(item.invoice_number, '/invoices/' + item.id));
                    if (item.status === 'storniert') {
                         const mark = document.createElement('span');
                         mark.className = 'muted';
                         mark.textContent = ' · ' + t('history.status.cancelled');
                         row.lastElementChild.append(mark);
                    }

                    for (const value of [
                         date(item.invoice_date),
                         item.supplier,
                         String(item.item_count),
                         item.filename,
                         date(item.uploaded_at),
                         importedBy(item) + sourceLabel(item)
                    ]) {
                         add(row, value);
                    }
               } else {
                    add(row, `${item.row_number ?? '—'} / ${item.page ?? '—'}`);

                    const invoice = document.createElement('div');
                    invoice.append(link(item.invoice_number, '/invoices/' + item.invoice_id), el('p', date(item.invoice_date)));
                    add(row, invoice);

                    add(row, link(`${item.brand ?? ''} ${item.description ?? ''}`, '/articles/' + item.product_id + '/history'));
                    row.lastElementChild.className = 'description';
                    if (!article) add(row, item.ean);
                    add(row, `${item.article_no ?? '—'} / ${item.supplier_article_no ?? '—'}`);
                    add(row, item.color);
                    add(row, item.size);
                    add(row, item.quantity);
                    add(row, item.unit);
                    add(row, item.uvp === null ? '—' : item.uvp + ' CHF');

                    if (item.source_available) {
                         const details = document.createElement('details');
                         details.append(el('summary', t('common.view')), el('pre', item.raw_lines.join('\n')));

                         if (item.correction_audit) {
                              const audit = item.correction_audit;
                              details.append(
                                   el('p', t('history.corrected_by', { name: audit.by.name || audit.by.kassennummer || t('common.unknown'), at: audit.at }))
                              );

                              for (const [key, change] of Object.entries(audit.changes)) {
                                   details.append(
                                        el('p', t('history.audit.change_line', { field: t('fields.' + key), before: change.before ?? t('history.audit.empty_value'), after: change.after ?? t('history.audit.empty_value') }))
                                   );
                              }
                         }

                         add(row, details);
                    } else {
                         add(row, t('history.no_raw_text'));
                    }
               }

               fragment.append(row);
          }

          $('rows').replaceChildren(fragment);
          $('table').hidden = !data.items.length;
          $('status').textContent = data.total
               ? t('history.status.found', { total: data.total, unit: list ? t('history.status.unit_invoices') : t('history.status.unit_positions'), from: Math.min((page - 1) * pageSize + 1, data.total), to: Math.min(page * pageSize, data.total) })
               : list
                    ? t('history.status.no_invoices')
                    : t('history.status.no_positions');
          $('page').textContent = t('articles.status.page', { page, total: Math.max(1, Math.ceil(data.total / pageSize)) });
          $('prev').disabled = page <= 1;
          $('next').disabled = page * pageSize >= data.total;
     } catch (error) {
          if (error.name === 'AbortError') return;
          $('status').textContent = error.message === 'Failed to fetch' ? t('history.connection_lost') : error.message;
          $('page').textContent = '';
          $('retry').hidden = false;
     }
}

$('search').addEventListener('submit', (e) => {
     e.preventDefault();
     q = new FormData(e.target).get('q').trim();
     page = 1;
     load();
});

$('resetBtn').addEventListener('click', () => {
     $('search').reset();
     q = '';
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

$('retry').addEventListener('click', load);
load();
document.addEventListener('sportfabrik:i18n-ready', load);
