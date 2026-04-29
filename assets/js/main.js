/* Echelon Day Care - small site-wide enhancements */
(function () {
  'use strict';

  // ---- Mobile nav toggle ----------------------------------------------------
  const toggle   = document.querySelector('[data-nav-toggle]');
  const nav      = document.querySelector('[data-primary-nav]');
  const overlay  = document.querySelector('[data-nav-overlay]');
  const closeBtn = document.querySelector('[data-nav-close]');

  function setNav(open) {
    if (!nav) return;
    nav.dataset.open = open ? 'true' : 'false';
    if (overlay) overlay.dataset.open = open ? 'true' : 'false';
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    document.body.style.overflow = open ? 'hidden' : '';
  }

  if (toggle)  toggle.addEventListener('click', function () { setNav(nav.dataset.open !== 'true'); });
  if (overlay) overlay.addEventListener('click', function () { setNav(false); });
  if (closeBtn) closeBtn.addEventListener('click', function () { setNav(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setNav(false); });

  // ---- Year token in footer -------------------------------------------------
  const yearEl = document.querySelector('[data-year]');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // ---- Generic lightbox -----------------------------------------------------
  const box      = document.querySelector('[data-lightbox]');
  const boxImg   = box && box.querySelector('[data-lightbox-img]');
  const boxCap   = box && box.querySelector('[data-lightbox-caption]');
  const boxClose = box && box.querySelector('[data-lightbox-close]');
  const boxPrev  = box && box.querySelector('[data-lightbox-prev]');
  const boxNext  = box && box.querySelector('[data-lightbox-next]');

  let group = [];
  let idx = 0;

  function openBox(items, startAt) {
    if (!box) return;
    group = items; idx = startAt;
    update();
    box.dataset.open = 'true';
    box.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    if (boxClose) boxClose.focus();
  }
  function closeBox() {
    if (!box) return;
    box.dataset.open = 'false';
    box.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }
  function step(delta) {
    if (!group.length) return;
    idx = (idx + delta + group.length) % group.length;
    update();
  }
  function update() {
    const item = group[idx];
    if (!item) return;
    boxImg.src = item.src;
    boxImg.alt = item.caption || '';
    if (boxCap) boxCap.textContent = item.caption || '';
  }

  document.querySelectorAll('[data-lightbox-group]').forEach(function (groupEl) {
    const triggers = Array.from(groupEl.querySelectorAll('[data-src]'));
    const items = triggers.map(function (t) { return { src: t.dataset.src, caption: t.dataset.caption || '' }; });
    triggers.forEach(function (t, i) {
      t.addEventListener('click', function () { openBox(items, i); });
      t.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openBox(items, i); }
      });
    });
  });

  if (box) {
    if (boxClose) boxClose.addEventListener('click', closeBox);
    if (boxPrev)  boxPrev.addEventListener('click', function () { step(-1); });
    if (boxNext)  boxNext.addEventListener('click', function () { step(1); });
    box.addEventListener('click', function (e) { if (e.target === box) closeBox(); });
    document.addEventListener('keydown', function (e) {
      if (box.dataset.open !== 'true') return;
      if (e.key === 'Escape') closeBox();
      if (e.key === 'ArrowRight') step(1);
      if (e.key === 'ArrowLeft')  step(-1);
    });
  }

  // ---- Tour video play overlay ---------------------------------------------
  document.querySelectorAll('[data-video-shell]').forEach(function (shell) {
    const video = shell.querySelector('video');
    const play  = shell.querySelector('[data-video-play]');
    if (!video || !play) return;
    play.addEventListener('click', function () {
      video.controls = true;
      play.hidden = true;
      video.play();
    });
  });
})();
