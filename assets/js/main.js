/* sidhvin.com: navigation, carousels and site search. No dependencies. */
(function () {
  'use strict';
  var body = document.body;

  /* ---------------------------------------------------------- top bar */
  var bar = document.querySelector('.topbar');
  function onScroll() { bar.classList.toggle('scrolled', window.scrollY > 4); }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------------------------------------------------------- menus */
  function setOpen(li, open) {
    li.classList.toggle('open', open);
    var t = li.querySelector(':scope > .item > .toggle');
    if (t) t.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  document.querySelectorAll('.has-sub > .item > .toggle').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var li = btn.closest('li');
      setOpen(li, !li.classList.contains('open'));
    });
  });
  // Close desktop dropdowns when clicking elsewhere or pressing Escape.
  function closeDesktopMenus() {
    document.querySelectorAll('.main-nav li.open').forEach(function (li) { setOpen(li, false); });
  }
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.main-nav')) closeDesktopMenus();
  });
  // In the mobile drawer, expand the branch that contains the current page.
  document.querySelectorAll('.drawer li.active.has-sub').forEach(function (li) { setOpen(li, true); });

  var menuBtn = document.querySelector('.menu-btn');
  function setDrawer(open) {
    body.classList.toggle('drawer-open', open);
    menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  menuBtn.addEventListener('click', function () { setDrawer(!body.classList.contains('drawer-open')); });
  document.querySelector('.drawer-backdrop').addEventListener('click', function () { setDrawer(false); });

  /* ---------------------------------------------------------- carousels */
  document.querySelectorAll('.carousel').forEach(function (car) {
    var slides = Array.prototype.slice.call(car.querySelectorAll('.slide'));
    var caption = car.querySelector('.caption');
    var dotsBox = car.querySelector('.dots');
    if (!slides.length) return;
    var index = 0, timer = null;
    var interval = Math.max(parseInt(car.dataset.interval, 10) || 3000, 1500);
    var dots = slides.map(function (_, i) {
      var d = document.createElement('button');
      d.type = 'button';
      d.setAttribute('aria-label', 'Show image ' + (i + 1));
      d.addEventListener('click', function () { show(i); restart(); });
      dotsBox.appendChild(d);
      return d;
    });
    function show(i) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle('active', k === index); });
      dots.forEach(function (d, k) { d.classList.toggle('active', k === index); });
      caption.textContent = slides[index].dataset.caption || '';
    }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function start() {
      stop();
      if (car.dataset.autostart === 'true' && slides.length > 1 &&
          !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        timer = setInterval(function () { show(index + 1); }, interval);
      }
    }
    function restart() { if (timer) start(); }
    car.querySelector('.prev').addEventListener('click', function () { show(index - 1); restart(); });
    car.querySelector('.next').addEventListener('click', function () { show(index + 1); restart(); });
    car.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { show(index - 1); restart(); }
      if (e.key === 'ArrowRight') { show(index + 1); restart(); }
    });
    car.addEventListener('mouseenter', stop);
    car.addEventListener('mouseleave', start);
    var x0 = null;
    car.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    car.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 40) { show(index + (dx < 0 ? 1 : -1)); restart(); }
      x0 = null;
    });
    show(0);
    start();
  });

  /* ---------------------------------------------------------- search */
  var panel = document.querySelector('.search-panel');
  var input = panel.querySelector('input');
  var results = panel.querySelector('.search-results');
  var index = null;

  function openSearch() {
    panel.hidden = false;
    input.focus();
    if (!index) {
      fetch('/assets/data/search-index.json')
        .then(function (r) { return r.json(); })
        .then(function (data) { index = data; runSearch(); })
        .catch(function () { index = []; });
    }
  }
  function closeSearch() { panel.hidden = true; }
  document.querySelector('.search-btn').addEventListener('click', openSearch);
  panel.querySelector('.search-close').addEventListener('click', closeSearch);
  panel.addEventListener('click', function (e) { if (e.target === panel) closeSearch(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeSearch(); setDrawer(false); closeDesktopMenus(); }
  });

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function reEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  function runSearch() {
    var q = input.value.trim().toLowerCase();
    results.innerHTML = '';
    if (!q || !index) return;
    var terms = q.split(/\s+/).filter(Boolean);
    var hits = index.map(function (p) {
      var title = p.title.toLowerCase(), text = p.text.toLowerCase(), score = 0;
      for (var i = 0; i < terms.length; i++) {
        var t = terms[i], inTitle = title.indexOf(t) >= 0, inText = text.indexOf(t) >= 0;
        if (!inTitle && !inText) return null;
        score += (inTitle ? 10 : 0) + (inText ? 1 : 0);
      }
      return { page: p, score: score };
    }).filter(Boolean).sort(function (a, b) { return b.score - a.score; });

    if (!hits.length) {
      results.innerHTML = '<li class="r-none">No results for “' + esc(input.value.trim()) + '”</li>';
      return;
    }
    var mark = new RegExp('(' + terms.map(reEsc).join('|') + ')', 'gi');
    results.innerHTML = hits.map(function (h) {
      var p = h.page, lower = p.text.toLowerCase(), at = lower.indexOf(terms[0]);
      var start = Math.max(0, at - 70);
      var snip = (start > 0 ? '…' : '') + p.text.substr(start, 220) + (p.text.length > start + 220 ? '…' : '');
      return '<li><a href="' + p.url + '"><div class="r-title">' + esc(p.title).replace(mark, '<mark>$1</mark>') +
        '</div><div class="r-url">sidhvin.com' + p.url + '</div><div class="r-snippet">' +
        esc(snip).replace(mark, '<mark>$1</mark>') + '</div></a></li>';
    }).join('');
  }
  input.addEventListener('input', runSearch);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { var first = results.querySelector('a'); if (first) location.href = first.href; }
  });
})();
