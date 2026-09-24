(() => {
  const match = location.pathname.match(/^\/articles\/(\d+)\/history$/);
  if (!match) return;
  const base = '/api/articles/' + match[1];
  const $ = id => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const node = (tag,text) => {const e=document.createElement(tag);e.textContent=text??'—';return e;};
  const date = value => value ? value.slice(0,10).split('-').reverse().join('.') : t('article_details.no_date');
  let prices=[],stock=null;
  $('articleExtras').hidden=false;
  // Artikeldetails aufgeräumt (24.09.2026): Kategorie und EAN/Etikett erst auf
  // Knopfdruck, unten der Bestand statt der Belegpositionen.
  $('articleActions').hidden=false;
  $('listPanel').hidden=true;
  for(const [button,panel] of [['editKategorie','kategoriePanel'],['toggleEan','eanPanel']]){
    $(button).addEventListener('click',()=>{const open=$(panel).hidden;$(panel).hidden=!open;$(button).setAttribute('aria-expanded',String(open));if(open)$(panel).scrollIntoView({behavior:'smooth',block:'start'});});
  }
  async function api(path,options){const r=await fetch(base+path,options);if(r.status===204)return null;let data;try{data=await r.json();}catch{throw new Error(t('common.errors.invalid_response'));}if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:(r.status===422?t('article_details.errors.note_length'):t('common.errors.request_failed')));return data;}
  function svgNode(tag,attributes,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attributes))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
  function drawPrices(){
    const unit=$('priceUnit').value;
    const rows=prices.filter(p=>JSON.stringify(p.unit)===unit);
    const table=document.createElement('table');const head=document.createElement('thead');const hr=document.createElement('tr');for(const h of [t('article_details.price_table.invoice_date'),t('article_details.price_table.uvp'),t('article_details.price_table.invoice'),t('article_details.price_table.delivered_quantity')])hr.append(node('th',h));head.append(hr);table.append(head);const body=document.createElement('tbody');
    for(const p of rows){const tr=document.createElement('tr');tr.append(node('td',date(p.date)),node('td',p.uvp));const td=document.createElement('td'),a=node('a',p.invoice_number);a.href='/invoices/'+p.invoice_id;td.append(a);tr.append(td,node('td',p.quantity===null?t('article_details.quantity_unknown'):new Intl.NumberFormat('de-CH').format(p.quantity)+' '+(p.unit||'')));body.append(tr);}table.append(body);$('priceTable').replaceChildren(table);$('priceTable').hidden=!rows.length;
    const points=rows.filter(p=>p.date).map(p=>({...p,x:Date.parse(p.date+'T00:00:00Z'),y:Number(p.uvp)}));
    $('priceChart').replaceChildren();
    if(!points.length){$('priceStatus').textContent=rows.length?t('article_details.price_status.no_dates'):t('article_details.price_status.empty');return;}
    $('priceStatus').textContent=points.length===1?t('article_details.price_status.single'):t('article_details.price_status.multiple',{count:points.length});
    if(rows.length>points.length)$('priceStatus').textContent+=' '+t('article_details.price_status.undated_suffix');
    const xmin=Math.min(...points.map(p=>p.x)),xmax=Math.max(...points.map(p=>p.x));const low=Math.min(...points.map(p=>p.y)),high=Math.max(...points.map(p=>p.y));const pad=Math.max((high-low)*.15,1);const step=Math.max(5,Math.ceil((high-low+2*pad)/30)*5);const ymin=Math.floor((low>=0?Math.max(0,low-pad):low-pad)/step)*step,ymax=Math.ceil((high+pad)/step)*step;
    const x=v=>xmin===xmax?450:115+(v-xmin)/(xmax-xmin)*710;const y=v=>215-(v-ymin)/(ymax-ymin)*170;
    const svg=svgNode('svg',{viewBox:'0 0 900 270',class:'price-chart',role:'img','aria-label':t('article_details.chart_aria_label')});
    for(let val=ymin;val<=ymax;val+=step){svg.append(svgNode('line',{x1:115,x2:825,y1:y(val),y2:y(val),stroke:'var(--border)'}),svgNode('text',{x:105,y:y(val)+4,'text-anchor':'end',fill:'var(--text-muted)','font-size':12},val.toFixed(2)+' CHF'));}
    svg.append(svgNode('polyline',{points:points.map(p=>`${x(p.x)},${y(p.y)}`).join(' '),fill:'none',stroke:'var(--accent)','stroke-width':2}));
    for(const p of points){const c=svgNode('circle',{cx:x(p.x),cy:y(p.y),r:5,fill:'var(--accent)',tabindex:0});c.append(svgNode('title',{},t('article_details.chart_point_title',{date:date(p.date),uvp:p.uvp,invoice:p.invoice_number})));svg.append(c);}
    svg.append(svgNode('text',{x:115,y:245,fill:'var(--text-muted)','font-size':12},date(points[0].date)),svgNode('text',{x:825,y:245,'text-anchor':'end',fill:'var(--text-muted)','font-size':12},date(points[points.length-1].date)));
    $('priceChart').append(svg);
  }
  async function loadPrices(){$('priceStatus').textContent=t('article_details.loading_prices');try{prices=(await api('/prices')).items;const options=[...new Set(prices.map(p=>JSON.stringify(p.unit)))];$('priceUnit').replaceChildren();for(const value of options)$('priceUnit').add(new Option(JSON.parse(value)||t('article_details.unit_unknown'),value));drawPrices();}catch(e){$('priceStatus').textContent=e.message;}}

  function drawStock(){
    if(!stock)return;
    const table=document.createElement('table');const hr=document.createElement('tr');
    for(const key of ['bestand.table_lagerort','bestand.table_color','bestand.table_size','fields.ean','bestand.table_quantity','bestand.table_arrival_date'])hr.append(node('th',t(key)));
    const head=document.createElement('thead');head.append(hr);table.append(head);const body=document.createElement('tbody');
    for(const z of stock.zeilen){const tr=document.createElement('tr');const arrival=z.aeltestes_eingangsdatum?date(z.aeltestes_eingangsdatum):t(z.lagerort.verkauf?'bestand.no_arrival_date':'bestand.external_no_date');
      tr.append(node('td',z.lagerort.code+' · '+z.lagerort.name),node('td',z.farbe),node('td',z.groesse),node('td',z.ean),node('td',new Intl.NumberFormat('de-CH').format(Number(z.menge))),node('td',arrival));body.append(tr);}
    table.append(body);$('stockTable').replaceChildren(table);$('stockTable').hidden=!stock.zeilen.length;
    $('stockStatus').textContent=stock.zeilen.length?t('bestand.count_line',{anzahl:stock.total,summe:new Intl.NumberFormat('de-CH').format(Number(stock.summe))}):t('article_details.stock_empty');
  }
  async function loadStock(){$('stockStatus').textContent=t('bestand.loading');try{const r=await fetch('/api/bestand?alle=true&limit=500&artikel_von='+match[1]);const data=await r.json();if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:t('bestand.load_error'));stock=data;drawStock();}catch(e){$('stockStatus').textContent=e.message==='Failed to fetch'?t('common.connection_lost'):e.message;}}
  $('priceUnit').addEventListener('change',drawPrices);loadPrices();loadStock();
  document.addEventListener('sportfabrik:i18n-ready',()=>{if(prices.length)drawPrices();drawStock();});
})();
