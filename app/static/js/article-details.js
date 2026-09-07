(() => {
  const match = location.pathname.match(/^\/articles\/(\d+)\/history$/);
  if (!match) return;
  const base = '/api/articles/' + match[1];
  const $ = id => document.getElementById(id);
  const node = (tag,text) => {const e=document.createElement(tag);e.textContent=text??'—';return e;};
  const date = value => value ? value.slice(0,10).split('-').reverse().join('.') : 'Ohne Datum';
  let prices=[],noteGeneration=0;
  $('articleExtras').hidden=false;
  async function api(path,options){const r=await fetch(base+path,options);if(r.status===204)return null;let data;try{data=await r.json();}catch{throw new Error('Ungültige Serverantwort. Bitte erneut versuchen.');}if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:(r.status===422?'Bitte einen Text mit 1 bis 2000 Zeichen eingeben.':'Anfrage fehlgeschlagen.'));return data;}
  function svgNode(tag,attributes,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attributes))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
  function drawPrices(){
    const unit=$('priceUnit').value;
    const rows=prices.filter(p=>JSON.stringify(p.unit)===unit);
    const table=document.createElement('table');const head=document.createElement('thead');const hr=document.createElement('tr');for(const h of ['Rechnungsdatum','UVP (CHF)','Rechnung','Gelieferte Menge'])hr.append(node('th',h));head.append(hr);table.append(head);const body=document.createElement('tbody');
    for(const p of rows){const tr=document.createElement('tr');tr.append(node('td',date(p.date)),node('td',p.uvp));const td=document.createElement('td'),a=node('a',p.invoice_number);a.href='/invoices/'+p.invoice_id;td.append(a);tr.append(td,node('td',p.quantity===null?'Unbekannt':new Intl.NumberFormat('de-CH').format(p.quantity)+' '+(p.unit||'')));body.append(tr);}table.append(body);$('priceTable').replaceChildren(table);$('priceTable').hidden=!rows.length;
    const points=rows.filter(p=>p.date).map(p=>({...p,x:Date.parse(p.date+'T00:00:00Z'),y:Number(p.uvp)}));
    $('priceChart').replaceChildren();
    if(!points.length){$('priceStatus').textContent=rows.length?'Kein Rechnungsdatum vorhanden; Preise stehen in der Tabelle.':'Noch keine UVP-Werte für diesen Artikel vorhanden.';return;}
    $('priceStatus').textContent=points.length===1?'Ein Preis erfasst – weitere Rechnungen ergänzen den Verlauf.':`${points.length} Preisangaben mit Datum. Punkte zeigen den UVP; Verbindungslinien dienen der Orientierung.`;
    if(rows.length>points.length)$('priceStatus').textContent+=' Werte ohne Datum stehen nur in der Tabelle.';
    const xmin=Math.min(...points.map(p=>p.x)),xmax=Math.max(...points.map(p=>p.x));const low=Math.min(...points.map(p=>p.y)),high=Math.max(...points.map(p=>p.y));const pad=Math.max((high-low)*.15,1);const step=Math.max(5,Math.ceil((high-low+2*pad)/30)*5);const ymin=Math.floor((low>=0?Math.max(0,low-pad):low-pad)/step)*step,ymax=Math.ceil((high+pad)/step)*step;
    const x=v=>xmin===xmax?450:115+(v-xmin)/(xmax-xmin)*710;const y=v=>215-(v-ymin)/(ymax-ymin)*170;
    const svg=svgNode('svg',{viewBox:'0 0 900 270',role:'img','aria-label':'UVP-Verlauf in CHF. Genaue Werte in der anschliessenden Tabelle.'});
    for(let val=ymin;val<=ymax;val+=step){svg.append(svgNode('line',{x1:115,x2:825,y1:y(val),y2:y(val),stroke:'var(--border)'}),svgNode('text',{x:105,y:y(val)+4,'text-anchor':'end',fill:'var(--text-muted)','font-size':12},val.toFixed(2)+' CHF'));}
    svg.append(svgNode('polyline',{points:points.map(p=>`${x(p.x)},${y(p.y)}`).join(' '),fill:'none',stroke:'var(--accent)','stroke-width':2}));
    for(const p of points){const c=svgNode('circle',{cx:x(p.x),cy:y(p.y),r:5,fill:'var(--accent)',tabindex:0});c.append(svgNode('title',{},`${date(p.date)}: CHF ${p.uvp} · Rechnung ${p.invoice_number}`));svg.append(c);}
    svg.append(svgNode('text',{x:115,y:245,fill:'var(--text-muted)','font-size':12},date(points[0].date)),svgNode('text',{x:825,y:245,'text-anchor':'end',fill:'var(--text-muted)','font-size':12},date(points[points.length-1].date)));
    $('priceChart').append(svg);
  }
  async function loadPrices(){$('reloadPrices').disabled=true;$('priceStatus').textContent='Preise werden geladen …';try{prices=(await api('/prices')).items;const options=[...new Set(prices.map(p=>JSON.stringify(p.unit)))];$('priceUnit').replaceChildren();for(const value of options)$('priceUnit').add(new Option(JSON.parse(value)||'Einheit unbekannt',value));drawPrices();}catch(e){$('priceStatus').textContent=e.message;}finally{$('reloadPrices').disabled=false;}}
  function editor(note,card){const form=document.createElement('form');form.className='note-editor';const label=node('label','Notiz bearbeiten'),area=document.createElement('textarea');area.value=note.body;area.maxLength=2000;area.required=true;area.rows=2;area.setAttribute('aria-label','Notiz bearbeiten');const save=node('button','Änderung speichern'),cancel=node('button','Abbrechen'),message=node('p','');cancel.type='button';cancel.className='secondary';cancel.addEventListener('click',()=>renderNote(note,card));form.append(label,area,save,cancel,message);form.addEventListener('submit',async e=>{e.preventDefault();save.disabled=true;cancel.disabled=true;try{const updated=await api('/notes/'+note.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({body:area.value,version:note.version})});renderNote(updated,card);}catch(error){message.textContent=error.message;}finally{save.disabled=false;cancel.disabled=false;}});card.replaceChildren(form);area.focus();}
  function renderNote(note,card){card.replaceChildren();card.className='article-note';const text=node('p',note.body);text.className='note-text';card.append(text);if(note.can_edit){const edit=node('button','Bearbeiten');edit.type='button';edit.className='secondary';edit.addEventListener('click',()=>editor(note,card));const remove=node('button','Löschen');remove.type='button';remove.className='secondary';remove.addEventListener('click',async()=>{if(!confirm('Diese Notiz wirklich löschen?\n\n'+note.body))return;remove.disabled=true;edit.disabled=true;try{await api('/notes/'+note.id+'?version='+note.version,{method:'DELETE'});await loadNotes();}catch(error){$('noteStatus').textContent=error.message;remove.disabled=false;edit.disabled=false;}});card.append(edit,remove);}}
  async function loadNotes(){
    const generation=++noteGeneration;
    $('reloadNotes').disabled=true;
    try{
      let page=1, data, notes=[];
      do{
        data=await api('/notes?page='+page++);
        if(generation!==noteGeneration)return;
        notes.push(...data.items);
      }while(data.items.length && notes.length<data.total);
      $('noteList').replaceChildren();
      for(const note of notes){const card=document.createElement('article');renderNote(note,card);$('noteList').append(card);}
      $('noteStatus').textContent=notes.length?'':'Noch keine Notizen vorhanden.';
    }catch(e){if(generation===noteGeneration)$('noteStatus').textContent=e.message;}
    finally{if(generation===noteGeneration)$('reloadNotes').disabled=false;}
  }
  $('noteForm').addEventListener('submit',async event=>{event.preventDefault();$('saveNote').disabled=true;try{await api('/notes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body:$('noteBody').value})});$('noteBody').value='';await loadNotes();}catch(e){$('noteStatus').textContent=e.message;}finally{$('saveNote').disabled=false;}});
  $('reloadPrices').addEventListener('click',loadPrices);$('priceUnit').addEventListener('change',drawPrices);$('reloadNotes').addEventListener('click',loadNotes);loadPrices();loadNotes();
})();
