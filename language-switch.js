(() => {
  const language = document.documentElement.lang === 'en' ? 'en' : 'es';
  const base = new URL('.', document.baseURI);
  const params = new URLSearchParams(location.search);
  // Keep the selector available while a photo or contact panel is open.
  const switcher = document.querySelector('.language-switch');
  ['.viewer-top', '.contact-card'].forEach(selector => {
    const container = document.querySelector(selector);
    if (container && switcher) container.prepend(switcher.cloneNode(true));
  });
  const keys = ['profile', 'fnb', 'events', 'leadership', 'project', 'gallery', 'formation'];
  if (typeof selectPanel === 'function' && keys.includes(params.get('panel'))) selectPanel(params.get('panel'));
  const range = document.getElementById('focusRange');
  if (range && params.has('scale')) {
    const scale = Number(params.get('scale'));
    if (Number.isFinite(scale) && scale >= 86 && scale <= 108) {
      range.value = scale;
      range.dispatchEvent(new Event('input'));
    }
  }
  if (params.get('auto') === 'off' && typeof toggleAuto === 'function') toggleAuto();
  if (params.get('contact') === 'open' && typeof openContact === 'function') openContact();
  if (params.has('photo') && typeof show === 'function') {
    const photo = Number(params.get('photo'));
    if (Number.isInteger(photo) && photo >= 0 && photo < document.querySelectorAll('.gallery-grid .card').length) show(photo);
  }
  document.querySelectorAll('.language-switch a').forEach(link => {
    link.addEventListener('click', () => {
      const targetLanguage = link.lang;
      const url = new URL(link.getAttribute('href'), base);
      url.search = location.search;
      url.searchParams.set('lang', targetLanguage);
      url.hash = location.hash;
      // The viewer keeps the same file parameter, including its original PDF URL.
      if (url.searchParams.has('from')) {
        const from = url.searchParams.get('from').replace(/^en\//, '');
        if (['index.html', 'diplomas.html', 'galeria.html'].includes(from))
          url.searchParams.set('from', (targetLanguage === 'en' ? 'en/' : '') + from);
      }
      const code = document.getElementById('panelCode')?.textContent;
      if (code) {
        url.searchParams.set('panel', keys[Number(code.split('-').pop())] || 'profile');
        url.searchParams.set('scale', range.value);
        url.searchParams.set('auto', document.getElementById('clusterCanvas').classList.contains('is-auto') ? 'on' : 'off');
        url.searchParams.set('contact', document.getElementById('contactPopover').classList.contains('open') ? 'open' : 'closed');
      }
      const lightbox = document.getElementById('lightbox');
      url.searchParams.delete('photo');
      if (lightbox && !lightbox.hidden && typeof current !== 'undefined') url.searchParams.set('photo', current);
      try { localStorage.setItem('racv-hospitality-language', targetLanguage); } catch (_) {}
      link.href = url.href;
    });
  });
})();
