(function(){
  function t(key,vars){return window.SportfabrikI18n?window.SportfabrikI18n.t(key,vars):key;}
  fetch('/api/me').then(function(r){return r.ok?r.json():null;}).then(function(me){
    if(!me) return;
    if(window.SportfabrikI18n&&me.language)window.SportfabrikI18n.syncFromAccount(me.language);
    var header=document.querySelector('header');
    if(!header) return;
    var bar=document.createElement('div');
    bar.className='session-bar';
    var label=document.createElement('span');
    function refreshLabel(){
      label.textContent=(me.name?me.name+' \u00b7 ':'')+t('session.kassennummer_prefix')+me.kassennummer+' \u00b7 '+t('role.'+me.role);
    }
    refreshLabel();
    document.addEventListener('sportfabrik:i18n-ready',refreshLabel);
    var logout=document.createElement('button');
    logout.type='button';logout.className='secondary';logout.textContent=t('session.logout');
    document.addEventListener('sportfabrik:i18n-ready',function(){logout.textContent=t('session.logout');});
    logout.addEventListener('click',function(){fetch('/logout',{method:'POST'}).then(function(){location.href='/login';});});
    bar.append(label);
    if(me.lagerorte&&(me.lagerorte.length>1||me.kann_alle_filialen_waehlen)){
      var lagerortSelect=document.createElement('select');
      lagerortSelect.className='secondary lagerort-select';
      lagerortSelect.setAttribute('aria-label',t('session.switch_lagerort_aria'));
      if(me.kann_alle_filialen_waehlen){
        var allOption=document.createElement('option');
        allOption.value='';allOption.textContent=t('session.all_lagerorte');
        lagerortSelect.append(allOption);
      }
      me.lagerorte.forEach(function(lo){
        var option=document.createElement('option');
        option.value=String(lo.id);option.textContent=lo.code+' \u00b7 '+lo.name;
        lagerortSelect.append(option);
      });
      lagerortSelect.value=me.lagerort?String(me.lagerort.id):'';
      lagerortSelect.addEventListener('change',function(){
        fetch('/api/active-lagerort',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({lagerort_id:lagerortSelect.value?Number(lagerortSelect.value):null})
        }).then(function(){location.reload();});
      });
      bar.append(lagerortSelect);
    }else if(me.lagerort){
      var lagerortLabel=document.createElement('span');
      lagerortLabel.className='lagerort-label';
      lagerortLabel.textContent=me.lagerort.code+' \u00b7 '+me.lagerort.name;
      bar.append(lagerortLabel);
    }
    bar.append(logout);
    if(window.SportfabrikTheme){
      var settingsWrap=document.createElement('div');
      settingsWrap.className='settings-menu';
      var settingsToggle=document.createElement('button');
      settingsToggle.type='button';
      settingsToggle.className='secondary settings-toggle';
      settingsToggle.textContent='\u2699\ufe0f';
      settingsToggle.title=t('common.settings');
      settingsToggle.setAttribute('aria-label',t('common.settings'));
      settingsToggle.setAttribute('aria-haspopup','true');
      settingsToggle.setAttribute('aria-expanded','false');
      document.addEventListener('sportfabrik:i18n-ready',function(){
        settingsToggle.title=t('common.settings');
        settingsToggle.setAttribute('aria-label',t('common.settings'));
      });
      var settingsPanel=document.createElement('div');
      settingsPanel.className='settings-panel';
      settingsPanel.hidden=true;
      settingsPanel.append(window.SportfabrikTheme.createToggleButton());
      if(window.SportfabrikI18n){
        var langSwitch=document.createElement('div');
        langSwitch.className='lang-switch';
        langSwitch.setAttribute('role','group');
        langSwitch.setAttribute('aria-label','Sprache / Langue / Language');
        window.SportfabrikI18n.languages.forEach(function(lang){
          var option=document.createElement('button');
          option.type='button';option.className='secondary lang-option';
          option.textContent=lang.toUpperCase();
          option.dataset.lang=lang;
          option.addEventListener('click',function(){window.SportfabrikI18n.setLanguage(lang).then(highlightLang);});
          langSwitch.append(option);
        });
        function highlightLang(){
          langSwitch.querySelectorAll('.lang-option').forEach(function(btn){
            btn.classList.toggle('active',btn.dataset.lang===window.SportfabrikI18n.lang);
          });
        }
        highlightLang();
        document.addEventListener('sportfabrik:i18n-ready',highlightLang);
        settingsPanel.append(langSwitch);
      }
      if(location.pathname.replace(/\/$/,'')==='/articles'){
        var exportButton=document.createElement('button');
        exportButton.type='button';exportButton.className='secondary';exportButton.textContent=t('articles.export_button');
        document.addEventListener('sportfabrik:i18n-ready',function(){if(!exportButton.disabled)exportButton.textContent=t('articles.export_button');});
        exportButton.addEventListener('click',async function(){
          exportButton.disabled=true;exportButton.textContent=t('articles.export_in_progress');
          try{
            var response=await fetch('/api/articles/export?'+window.articleExportParams());
            if(!response.ok){var error=await response.json();throw new Error(typeof error.detail==='string'?error.detail:t('articles.export_failed'));}
            var url=URL.createObjectURL(await response.blob());var link=document.createElement('a');link.href=url;
            var filename=(response.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/);
            link.download=filename?filename[1]:'Artikel.xlsx';document.body.append(link);link.click();link.remove();setTimeout(function(){URL.revokeObjectURL(url);},1000);
          }catch(error){alert(error.message);}
          finally{exportButton.disabled=false;exportButton.textContent=t('articles.export_button');}
        });
        settingsPanel.append(exportButton);
      }
      settingsToggle.addEventListener('click',function(event){
        event.stopPropagation();
        var willOpen=settingsPanel.hidden;
        settingsPanel.hidden=!willOpen;
        settingsToggle.setAttribute('aria-expanded',String(willOpen));
      });
      document.addEventListener('click',function(event){
        if(!settingsPanel.hidden&&!settingsWrap.contains(event.target)){
          settingsPanel.hidden=true;
          settingsToggle.setAttribute('aria-expanded','false');
        }
      });
      document.addEventListener('keydown',function(event){
        if(event.key==='Escape'&&!settingsPanel.hidden){
          settingsPanel.hidden=true;
          settingsToggle.setAttribute('aria-expanded','false');
          settingsToggle.focus();
        }
      });
      settingsWrap.append(settingsToggle,settingsPanel);
      bar.append(settingsWrap);
    }
    header.append(bar);
    if(me.role==='mitarbeiter'){
      var uploadLink=document.querySelector('nav a[href="/preview"]');
      if(uploadLink) uploadLink.remove();
      var uploadHero=document.getElementById('uploadHero');
      if(uploadHero) uploadHero.remove();
    }
  }).catch(function(){});
})();
