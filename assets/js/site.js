/* Echelon Day Care - shared site-wide JS
   - Mobile nav hamburger toggle
   - Footer year token (in case a page forgot the inline script)
*/
(function () {
  'use strict';

  // ---- Mobile nav toggle ---------------------------------------------
  var toggle = document.querySelector('[data-nav-toggle]');
  var nav    = document.querySelector('nav.primary-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    // Close menu when a link is clicked (so on-page anchors work cleanly)
    nav.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.tagName === 'A') {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // ---- Footer year token ---------------------------------------------
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
})();
