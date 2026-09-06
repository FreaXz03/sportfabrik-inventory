(function(){
  fetch('/api/me').then(function(r){return r.ok?r.json():null;}).then(function(me){
    if(!me) return;
    var header=document.querySelector('header');
    if(!header) return;
    var bar=document.createElement('div');
    bar.className='session-bar';
    var label=document.createElement('span');
    label.textContent=(me.name?me.name+' \u00b7 ':'')+'Kassennummer '+me.kassennummer+' \u00b7 '+(me.role==='chef'?'Chef':'Mitarbeiter');
    var logout=document.createElement('button');
    logout.type='button';logout.className='secondary';logout.textContent='Abmelden';
    logout.addEventListener('click',function(){fetch('/logout',{method:'POST'}).then(function(){location.href='/login';});});
    bar.append(label,logout);
    header.append(bar);
    if(me.role!=='chef'){
      var uploadLink=document.querySelector('nav a[href="/preview"]');
      if(uploadLink) uploadLink.remove();
    }
  }).catch(function(){});
})();
