// Phone home screen: one tile per phone function the role may use. The server
// enforces the same limits (app/core/handy.py); hiding a tile is only comfort.
(function () {
  var t = window.SFPhone.t;
  var icon = window.SFPhone.icon;
  var CHEF = ['chef', 'admin'];
  var TILES = [
    { href: '/m/suche', icon: 'scan', key: 'search', primary: true },
    { href: '/m/zaehlen', icon: 'package', key: 'count' },
  ];
  var me = null;

  function render() {
    if (!me) return;
    document.getElementById('greetingName').textContent = String(me.name || '').split(/\s+/)[0] || me.kassennummer;
    var tiles = document.getElementById('tiles');
    tiles.replaceChildren();
    TILES.filter(function (tile) { return !tile.chefOnly || CHEF.indexOf(me.role) !== -1; })
      .forEach(function (tile) {
        var a = document.createElement('a');
        a.className = 'm-tile' + (tile.primary ? ' primary' : '');
        a.href = tile.href;
        var label = document.createElement('strong');
        label.textContent = t('phone.tile_' + tile.key);
        var hint = document.createElement('span');
        hint.textContent = t('phone.tile_' + tile.key + '_hint');
        a.append(icon(tile.icon), label, icon('chevron-right', 'chevron'), hint);
        tiles.append(a);
      });
  }

  document.addEventListener('sportfabrik:me', function (event) { me = event.detail; render(); });
  document.addEventListener('sportfabrik:i18n-ready', render);
})();
