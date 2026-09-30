// Kopfzeile: aktive Filiale und Konto (23.09.2026 neu gestaltet) und seit
// 30.09.2026 das Einstellungsfenster (Redesign Phase 6): Sprache, Darstellung,
// Filialwechsel, Artikelexport, Abmelden. Filiale, Konto und der Menüpunkt
// „Einstellungen" (Ereignis `sportfabrik:settings-open`) öffnen es. Meldet die
// Anmeldung als Ereignis `sportfabrik:me`, damit nav.js Einträge nach Rolle zeigt.
(function(){
  function t(key,vars){return window.SportfabrikI18n?window.SportfabrikI18n.t(key,vars):key;}
  function onLang(fn){document.addEventListener('sportfabrik:i18n-ready',fn);}

  function initialen(me){
    var teile=String(me.name||'').trim().split(/\s+/).filter(Boolean);
    if(!teile.length)return String(me.kassennummer||'?').slice(-2);
    return (teile[0][0]+(teile.length>1?teile[teile.length-1][0]:'')).toUpperCase();
  }

  // Anzeige der aktiven Filiale; ein Klick öffnet die Einstellungen (dort wechselt man sie).
  function filiale(me){
    var knopf=document.createElement('button');
    knopf.type='button';
    knopf.className='store-pill';
    knopf.setAttribute('aria-haspopup','dialog');
    var punkt=document.createElement('span');
    punkt.className='store-dot';
    punkt.setAttribute('aria-hidden','true');
    var text=document.createElement('span');
    text.className='store-name';
    function beschriften(){text.textContent=me.lagerort?me.lagerort.code+' · '+me.lagerort.name:t('session.all_lagerorte');}
    beschriften();onLang(beschriften);
    knopf.append(punkt,text);
    knopf.addEventListener('click',oeffnen);
    return knopf;
  }

  function filialWahl(me){
    var auswahl=document.createElement('select');
    auswahl.className='settings-select';
    auswahl.setAttribute('aria-label',t('session.switch_lagerort_aria'));
    onLang(function(){auswahl.setAttribute('aria-label',t('session.switch_lagerort_aria'));});
    if(me.kann_alle_filialen_waehlen){
      var alle=document.createElement('option');
      alle.value='';alle.textContent=t('session.all_lagerorte');
      onLang(function(){alle.textContent=t('session.all_lagerorte');});
      auswahl.append(alle);
    }
    me.lagerorte.forEach(function(lo){
      var option=document.createElement('option');
      option.value=String(lo.id);option.textContent=lo.code+' · '+lo.name;
      auswahl.append(option);
    });
    auswahl.value=me.lagerort?String(me.lagerort.id):'';
    auswahl.addEventListener('change',function(){
      fetch('/api/active-lagerort',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({lagerort_id:auswahl.value?Number(auswahl.value):null})
      }).then(function(){location.reload();});
    });
    return auswahl;
  }

  function sprachwahl(){
    var gruppe=document.createElement('div');
    gruppe.className='lang-switch';
    gruppe.setAttribute('role','group');
    gruppe.setAttribute('aria-label','Sprache / Langue / Language');
    window.SportfabrikI18n.languages.forEach(function(lang){
      var knopf=document.createElement('button');
      knopf.type='button';knopf.className='secondary lang-option';
      knopf.textContent=lang.toUpperCase();
      knopf.dataset.lang=lang;
      knopf.addEventListener('click',function(){window.SportfabrikI18n.setLanguage(lang).then(markieren);});
      gruppe.append(knopf);
    });
    function markieren(){
      gruppe.querySelectorAll('.lang-option').forEach(function(knopf){
        knopf.classList.toggle('active',knopf.dataset.lang===window.SportfabrikI18n.lang);
      });
    }
    markieren();onLang(markieren);
    return gruppe;
  }

  function exportKnopf(){
    var knopf=document.createElement('button');
    knopf.type='button';knopf.className='secondary';knopf.textContent=t('articles.export_button');
    onLang(function(){if(!knopf.disabled)knopf.textContent=t('articles.export_button');});
    knopf.addEventListener('click',async function(){
      knopf.disabled=true;knopf.textContent=t('articles.export_in_progress');
      try{
        var antwort=await fetch('/api/articles/export?'+window.articleExportParams());
        if(!antwort.ok){var fehler=await antwort.json();throw new Error(typeof fehler.detail==='string'?fehler.detail:t('articles.export_failed'));}
        var url=URL.createObjectURL(await antwort.blob());var link=document.createElement('a');link.href=url;
        var name=(antwort.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/);
        link.download=name?name[1]:'Artikel.xlsx';document.body.append(link);link.click();link.remove();setTimeout(function(){URL.revokeObjectURL(url);},1000);
      }catch(fehler){alert(fehler.message);}
      finally{knopf.disabled=false;knopf.textContent=t('articles.export_button');}
    });
    return knopf;
  }

  // Rund mit Initialen; öffnet ebenfalls die Einstellungen.
  function kontoKnopf(me){
    var knopf=document.createElement('button');
    knopf.type='button';
    knopf.className='account-toggle';
    knopf.textContent=initialen(me);
    knopf.setAttribute('aria-haspopup','dialog');
    function aria(){knopf.setAttribute('aria-label',t('session.account_aria'));knopf.title=t('session.account_aria');}
    aria();onLang(aria);
    knopf.addEventListener('click',oeffnen);
    return knopf;
  }

  function zeile(schluessel,inhalt){
    var huelle=document.createElement('div');
    huelle.className='settings-row';
    var titel=document.createElement('span');
    titel.className='settings-label';
    function beschriften(){titel.textContent=t(schluessel);}
    beschriften();onLang(beschriften);
    huelle.append(titel,inhalt);
    return huelle;
  }

  function einstellungenBauen(me){
    var d=document.createElement('dialog');
    d.className='settings-dialog';
    d.setAttribute('aria-labelledby','einstellungenTitel');
    var kopf=document.createElement('div');
    kopf.className='settings-head';
    var titel=document.createElement('h2');
    titel.id='einstellungenTitel';
    function beschriften(){titel.textContent=t('nav.settings');}
    beschriften();onLang(beschriften);
    var zu=document.createElement('button');
    zu.type='button';zu.className='secondary settings-close';
    function zuText(){zu.textContent=t('settings.close');}
    zuText();onLang(zuText);
    zu.addEventListener('click',function(){d.close();});
    kopf.append(titel,zu);
    var wer=document.createElement('div');
    wer.className='account-who';
    var name=document.createElement('strong');
    name.textContent=me.name||me.kassennummer;
    var details=document.createElement('span');
    function detailText(){details.textContent=t('session.kassennummer_prefix')+me.kassennummer+' · '+t('role.'+me.role);}
    detailText();onLang(detailText);
    wer.append(name,details);
    d.append(kopf,wer);
    if(window.SportfabrikI18n)d.append(zeile('settings.language',sprachwahl()));
    if(window.SportfabrikTheme)d.append(zeile('settings.theme',window.SportfabrikTheme.createToggleButton()));
    if(me.lagerorte&&(me.lagerorte.length>1||me.kann_alle_filialen_waehlen))d.append(zeile('settings.branch',filialWahl(me)));
    if(location.pathname.replace(/\/$/,'')==='/articles'&&window.articleExportParams)d.append(exportKnopf());
    var abmelden=document.createElement('button');
    abmelden.type='button';abmelden.className='secondary settings-logout';
    abmelden.textContent=t('session.logout');
    onLang(function(){abmelden.textContent=t('session.logout');});
    abmelden.addEventListener('click',function(){fetch('/logout',{method:'POST'}).then(function(){location.href='/login';});});
    d.append(abmelden);
    // Klick auf den abgedunkelten Rand schliesst; Esc und Fokusfalle kommen vom <dialog>.
    d.addEventListener('click',function(ereignis){if(ereignis.target===d)d.close();});
    return d;
  }

  var angemeldet=null;
  var einstellungen=null;
  function oeffnen(){
    if(!angemeldet)return;
    if(!einstellungen){einstellungen=einstellungenBauen(angemeldet);document.body.append(einstellungen);}
    if(!einstellungen.open)einstellungen.showModal();
  }
  document.addEventListener('sportfabrik:settings-open',oeffnen);

  fetch('/api/me').then(function(r){return r.ok?r.json():null;}).then(function(me){
    if(!me) return;
    if(window.SportfabrikI18n&&me.language)window.SportfabrikI18n.syncFromAccount(me.language);
    document.querySelectorAll('[data-chef-only]').forEach(function(el){el.hidden = !['chef', 'admin'].includes(me.role);});
    angemeldet=me;
    document.dispatchEvent(new CustomEvent('sportfabrik:me',{detail:me}));
    var header=document.querySelector('header');
    if(!header) return;
    var werkzeuge=document.createElement('div');
    werkzeuge.className='header-tools';
    werkzeuge.append(filiale(me),kontoKnopf(me));
    header.append(werkzeuge);
    if(me.role==='mitarbeiter'){
      var uploadHero=document.getElementById('uploadHero');
      if(uploadHero) uploadHero.remove();
    }
  }).catch(function(){});
})();
