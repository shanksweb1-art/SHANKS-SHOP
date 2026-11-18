(function() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function(err) {
        console.warn('SW registration failed:', err);
      });
    });
  }
  function updateOnlineStatus() {
    var offline = !navigator.onLine;
    document.documentElement.classList.toggle('app-offline', offline);
    var bar = document.getElementById('offline-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'offline-bar';
      bar.style.cssText = 'display:none;position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#b45309;color:#fff;text-align:center;padding:8px 12px;font:600 13px/1.4 system-ui,sans-serif;box-shadow:0 -2px 8px rgba(0,0,0,.2)';
      bar.textContent = 'You are offline. Cached pages and recently loaded data remain available; changes may not sync until connection returns.';
      document.body && document.body.appendChild(bar);
    }
    if (bar) bar.style.display = offline ? 'block' : 'none';
  }
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateOnlineStatus);
  } else {
    updateOnlineStatus();
  }
})();
