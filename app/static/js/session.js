(function(){
  fetch('/api/me').then(function(r){return r.ok?r.json():null;}).then(function(me){
    if(!me) return;
    var header=document.querySelector('header');
    if(!header) return;
    var bar=document.createElement('div');
    bar.className='session-bar';
    var label=document.createElement('span');
    label.textContent=(me.name?me.name+' \u00b7 ':'')+'Kassennummer '+me.kassennummer+' \u00b7 '+(me.role==='chef'?'Filialleiter':'Mitarbeiter');
    var logout=document.createElement('button');
    logout.type='button';logout.className='secondary';logout.textContent='Abmelden';
    logout.addEventListener('click',function(){fetch('/logout',{method:'POST'}).then(function(){location.href='/login';});});
    bar.append(label,logout);
    if(window.SportfabrikTheme){
      var settingsWrap=document.createElement('div');
      settingsWrap.className='settings-menu';
      var settingsToggle=document.createElement('button');
      settingsToggle.type='button';
      settingsToggle.className='secondary settings-toggle';
      settingsToggle.textContent='\u2699\ufe0f';
      settingsToggle.title='Einstellungen';
      settingsToggle.setAttribute('aria-label','Einstellungen');
      settingsToggle.setAttribute('aria-haspopup','true');
      settingsToggle.setAttribute('aria-expanded','false');
      var settingsPanel=document.createElement('div');
      settingsPanel.className='settings-panel';
      settingsPanel.hidden=true;
      settingsPanel.append(window.SportfabrikTheme.createToggleButton());
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
    if(me.role!=='chef'){
      var uploadLink=document.querySelector('nav a[href="/preview"]');
      if(uploadLink) uploadLink.remove();
      var uploadHero=document.getElementById('uploadHero');
      if(uploadHero) uploadHero.remove();
    }
  }).catch(function(){});
})();
