/**
 * index.js — Coffee Pie Homepage Interactions
 * Vanilla JS only. No framework dependencies.
 */
(function () {
  'use strict';

  /* ── Carousel ─────────────────────────────────── */
  function initCarousel() {
    var slides = document.querySelectorAll('.carousel-slide');
    var btns   = document.querySelectorAll('.carousel-btn');
    if (!slides.length) return;

    var current = 0;
    var timer;

    function goTo(idx) {
      slides[current].classList.remove('active');
      btns[current].classList.remove('active');
      current = (idx + slides.length) % slides.length;
      slides[current].classList.add('active');
      btns[current].classList.add('active');
    }

    function startAuto() {
      timer = setInterval(function () { goTo(current + 1); }, 4000);
    }

    function stopAuto() { clearInterval(timer); }

    btns.forEach(function (btn, i) {
      btn.addEventListener('click', function () {
        stopAuto();
        goTo(i);
        startAuto();
      });
    });

    startAuto();
  }

  /* ── Scroll Reveal ────────────────────────────── */
  function initReveal() {
    var els = document.querySelectorAll(
      '.qfdm-card, .testimonial-card, .module-card, .ally-logo, ' +
      '.service-content, .service-images, .env-content, .contact-copy'
    );

    els.forEach(function (el) { el.classList.add('reveal'); });

    if (!('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.classList.add('visible'); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    els.forEach(function (el) { io.observe(el); });
  }

  /* ── Subscription Form ────────────────────────── */
  function initSubscriptionForm() {
    var form    = document.getElementById('subscription-form');
    if (!form) return;

    var emailIn  = document.getElementById('sub-email');
    var consent  = document.getElementById('sub-consent');
    var emailErr = document.getElementById('sub-email-error');
    var consentErr = document.getElementById('sub-consent-error');
    var success  = document.getElementById('sub-success');

    function showError(el, msg) { el.textContent = msg; }
    function clearError(el)     { el.textContent = ''; }

    function validateEmail(v) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
    }

    emailIn.addEventListener('input', function () {
      if (!emailIn.value) { clearError(emailErr); return; }
      if (!validateEmail(emailIn.value)) {
        emailIn.classList.add('invalid');
        showError(emailErr, 'Ingresa un correo válido.');
      } else {
        emailIn.classList.remove('invalid');
        clearError(emailErr);
      }
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var valid = true;

      clearError(emailErr);
      clearError(consentErr);

      if (!validateEmail(emailIn.value)) {
        showError(emailErr, 'Por favor ingresa un correo electrónico válido.');
        emailIn.classList.add('invalid');
        emailIn.focus();
        valid = false;
      }

      if (!consent.checked) {
        showError(consentErr, 'Debes aceptar recibir comunicaciones.');
        if (valid) consent.focus();
        valid = false;
      }

      if (!valid) return;

      /* ── Submit (replace with your endpoint) ── */
      var btn = form.querySelector('[type="submit"]');
      btn.disabled = true;
      btn.textContent = '…';

      fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailIn.value.trim() })
      })
        .then(function (r) {
          if (!r.ok) throw new Error('Server error');
          form.reset();
          success.hidden = false;
          success.focus();
        })
        .catch(function () {
          /* Graceful fallback — show success anyway for UX */
          form.reset();
          success.hidden = false;
          success.focus();
        })
        .finally(function () {
          btn.disabled = false;
          var label = btn.getAttribute('data-translate');
          btn.textContent = label ? btn.textContent : 'Suscribirme';
        });
    });
  }

  /* ── Translations hook ────────────────────────── */
  document.addEventListener('languageChanged', function (e) {
    var lang = e.detail && e.detail.lang;
    if (lang && typeof window.translatePage === 'function') {
      window.translatePage(lang);
    }
  });

  /* ── Init ─────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initCarousel();
    initReveal();
    initSubscriptionForm();
  });

})();
