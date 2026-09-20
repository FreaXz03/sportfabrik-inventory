(function(){
  var STORAGE_KEY='sportfabrikTheme';
  function storedTheme(){try{var t=localStorage.getItem(STORAGE_KEY);return(t==='dark'||t==='light')?t:null;}catch(e){return null;}}
  function currentTheme(){var stored=storedTheme();if(stored)return stored;return window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}
  function apply(theme){document.documentElement.setAttribute('data-theme',theme);}
  function createToggleButton(){
    var btn=document.createElement('button');
    btn.type='button';
    btn.className='theme-toggle secondary';
    function t(key){return window.SportfabrikI18n?window.SportfabrikI18n.t(key):key;}
    function refresh(){
      var dark=currentTheme()==='dark';
      btn.textContent=(dark?'☀️ ':'🌙 ')+t(dark?'theme.light_mode':'theme.dark_mode');
      btn.setAttribute('aria-label',t(dark?'theme.enable_light':'theme.enable_dark'));
    }
    refresh();
    if(window.SportfabrikI18n)document.addEventListener('sportfabrik:i18n-ready',refresh);
    btn.addEventListener('click',function(){
      var next=currentTheme()==='dark'?'light':'dark';
      try{localStorage.setItem(STORAGE_KEY,next);}catch(e){}
      apply(next);
      refresh();
    });
    return btn;
  }
  window.SportfabrikTheme={createToggleButton:createToggleButton};
  if(!document.querySelector('script[src^="/static/js/session.js"]')){
    var nav=document.querySelector('nav');
    var target=nav||document.querySelector('header');
    if(target)target.append(createToggleButton());
  }
})();
