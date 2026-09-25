// Rechte Seite der Kopfzeile: Filiale und Konto-Menü (23.09.2026 neu
// gestaltet - vorher eine eigene zweite Zeile). Meldet die Anmeldung als
// Ereignis `sportfabrik:me`, damit nav.js Einträge nach Rolle zeigen kann.
(function(){
  function t(key,vars){return window.SportfabrikI18n?window.SportfabrikI18n.t(key,vars):key;}
  function onLang(fn){document.addEventListener('sportfabrik:i18n-ready',fn);}

  function initialen(me){
    var teile=String(me.name||'').trim().split(/\s+/).filter(Boolean);
    if(!teile.length)return String(me.kassennummer||'?').slice(-2);
    return (teile[0][0]+(teile.length>1?teile[teile.length-1][0]:'')).toUpperCase();
  }

  function filiale(me){
    var huelle=document.createElement('div');
    huelle.className='store-pill';
    var punkt=document.createElement('span');
    punkt.className='store-dot';
    punkt.setAttribute('aria-hidden','true');
    huelle.append(punkt);
    if(me.lagerorte&&(me.lagerorte.length>1||me.kann_alle_filialen_waehlen)){
      var auswahl=document.createElement('select');
      auswahl.className='store-select';
      function aria(){auswahl.setAttribute('aria-label',t('session.switch_lagerort_aria'));}
      aria();onLang(aria);
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
      huelle.append(auswahl);
    }else{
      var text=document.createElement('span');
      text.className='store-name';
      text.textContent=me.lagerort?me.lagerort.code+' · '+me.lagerort.name:t('session.all_lagerorte');
      huelle.append(text);
    }
    return huelle;
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

  function kontoMenue(me){
    var huelle=document.createElement('div');
    huelle.className='account-menu';
    var knopf=document.createElement('button');
    knopf.type='button';
    knopf.className='account-toggle';
    knopf.textContent=initialen(me);
    knopf.setAttribute('aria-haspopup','true');
    knopf.setAttribute('aria-expanded','false');
    function aria(){knopf.setAttribute('aria-label',t('session.account_aria'));knopf.title=t('session.account_aria');}
    aria();onLang(aria);

    var panel=document.createElement('div');
    panel.className='account-panel';
    panel.hidden=true;
    var wer=document.createElement('div');
    wer.className='account-who';
    var name=document.createElement('strong');
    name.textContent=me.name||me.kassennummer;
    var details=document.createElement('span');
    function detailText(){details.textContent=t('session.kassennummer_prefix')+me.kassennummer+' · '+t('role.'+me.role);}
    detailText();onLang(detailText);
    wer.append(name,details);
    panel.append(wer);
    if(window.SportfabrikI18n)panel.append(sprachwahl());
    if(window.SportfabrikTheme)panel.append(window.SportfabrikTheme.createToggleButton());
    if(location.pathname.replace(/\/$/,'')==='/articles')panel.append(exportKnopf());
    var abmelden=document.createElement('button');
    abmelden.type='button';abmelden.className='secondary account-logout';
    abmelden.textContent=t('session.logout');
    onLang(function(){abmelden.textContent=t('session.logout');});
    abmelden.addEventListener('click',function(){fetch('/logout',{method:'POST'}).then(function(){location.href='/login';});});
    panel.append(abmelden);

    function zu(){panel.hidden=true;knopf.setAttribute('aria-expanded','false');}
    knopf.addEventListener('click',function(ereignis){
      ereignis.stopPropagation();
      var auf=panel.hidden;
      panel.hidden=!auf;
      knopf.setAttribute('aria-expanded',String(auf));
    });
    document.addEventListener('click',function(ereignis){if(!panel.hidden&&!huelle.contains(ereignis.target))zu();});
    document.addEventListener('keydown',function(ereignis){
      if(ereignis.key==='Escape'&&!panel.hidden){zu();knopf.focus();}
    });
    huelle.append(knopf,panel);
    return huelle;
  }

  fetch('/api/me').then(function(r){return r.ok?r.json():null;}).then(function(me){
    if(!me) return;
    if(window.SportfabrikI18n&&me.language)window.SportfabrikI18n.syncFromAccount(me.language);
    document.querySelectorAll('[data-chef-only]').forEach(function(el){el.hidden = !['chef', 'admin'].includes(me.role);});
    document.dispatchEvent(new CustomEvent('sportfabrik:me',{detail:me}));
    var header=document.querySelector('header');
    if(!header) return;
    var werkzeuge=document.createElement('div');
    werkzeuge.className='header-tools';
    werkzeuge.append(filiale(me),kontoMenue(me));
    header.append(werkzeuge);
    if(me.role==='mitarbeiter'){
      var uploadHero=document.getElementById('uploadHero');
      if(uploadHero) uploadHero.remove();
    }
  }).catch(function(){});
})();
