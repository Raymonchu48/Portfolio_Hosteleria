/* Separate translated pages, matching the user's sports and IT portfolios. */
(() => {
  const language = document.documentElement.lang === 'en' ? 'en' : 'es';
  const base = new URL('.', document.baseURI);
  const page = location.pathname.split('/').pop() || 'index.html';
  const params = new URLSearchParams(location.search);
  let saved;
  try { saved = localStorage.getItem('racv-hospitality-language'); } catch (_) {}
  // An English deep link and an explicit selector always take precedence.
  if (language === 'es' && params.get('lang') !== 'es' && saved === 'en') {
    const destination = new URL('en/' + page, base);
    destination.search = location.search;
    destination.hash = location.hash;
    location.replace(destination.href);
    return;
  }
  try { localStorage.setItem('racv-hospitality-language', language); } catch (_) {}
})();
