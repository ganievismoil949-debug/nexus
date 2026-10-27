/* Small original line icons. No external fonts, scripts or network assets. */
(() => {
  const paths={
    sparkles:'M12 3 14.5 9.5 21 12 14.5 14.5 12 21 9.5 14.5 3 12 9.5 9.5Z',
    house:'M3 11 12 3 21 11 M5 10V21H19V10 M9 21V14H15V21',
    'message-circle':'M21 11A9 9 0 0 1 7 19L3 21 4 16A9 9 0 1 1 21 11Z',
    brain:'M12 4C8 0 5 4 6 7C1 8 2 14 5 15C3 20 8 23 12 19 M12 4C16 0 19 4 18 7C23 8 22 14 19 15C21 20 16 23 12 19 M12 4V19 M6 7 8 9 M19 15 16 14',
    'settings-2':'M4 6H20 M4 12H20 M4 18H20 M8 3V9 M16 9V15 M10 15V21',
    mic:'M9 4A3 3 0 0 1 15 4V11A3 3 0 0 1 9 11Z M6 10V11A6 6 0 0 0 18 11V10 M12 17V21 M9 21H15',
    square:'M6 6H18V18H6Z',plus:'M12 5V19 M5 12H19','arrow-up':'M12 20V4 M5 11 12 4 19 11',
    play:'M8 4 20 12 8 20Z',mail:'M3 5H21V19H3Z M3 5 12 13 21 5',send:'M3 3 22 12 3 21 7 12Z M7 12H22',
  };
  document.querySelectorAll('[data-lucide]').forEach(el=>{
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('width','18');svg.setAttribute('height','18');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.6');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');svg.setAttribute('aria-hidden','true');
    const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',paths[el.dataset.lucide]||paths.sparkles);svg.append(path);el.replaceWith(svg);
  });
})();
