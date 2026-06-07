/**
 * Reusable Header Component Loader
 * Fetches header.html and injects it into the page.
 * Also ensures language/translation support (lang.js) is loaded.
 * Hamburger menu is handled by translate.js (Vanilla JS implementation).
 *
 * Grid context: #comp-kbgakxea uses grid-area + position:sticky which requires
 * a CSS grid parent. Avo-generated pages supply this natively via their wrapper
 * divs. Standalone pages (e.g. /products/*) need an explicit wrapper container.
 */
(function () {
    'use strict';

    var placeholder = document.getElementById('reusable-header-placeholder');
    if (!placeholder) return;

    if (!document.querySelector('link[href="/header.css"]')) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/header.css';
        document.head.appendChild(link);
    }

    if (!document.querySelector('script[src="/js/lang.js"]') && !window.CoffeePieLang) {
        var langScript = document.createElement('script');
        langScript.src = '/js/lang.js';
        document.head.appendChild(langScript);
    }

    // translate.js handles language dropdown, hamburger menu, and populateHeaderDropdown()
    if (!document.querySelector('script[src="/translate.js"]')) {
        var translateScript = document.createElement('script');
        translateScript.src = '/translate.js';
        document.head.appendChild(translateScript);
    }

    fetch('/header.html')
        .then(function (response) {
            if (!response.ok) throw new Error('Failed to load header.html');
            return response.text();
        })
        .then(function (html) {
            var isInAvoContainer = !!placeholder.closest('#masterPage, .masterPage, [data-testid="responsive-container-content"]');

            if (isInAvoContainer) {
                placeholder.insertAdjacentHTML('afterend', html);
                placeholder.remove();
            } else {
                var wrapper = document.createElement('div');
                wrapper.className = 'cp-header-grid-wrapper';
                placeholder.parentNode.insertBefore(wrapper, placeholder);
                wrapper.innerHTML = html;
                placeholder.remove();
            }

            if (typeof populateHeaderDropdown === 'function') {
                populateHeaderDropdown();
            }
            if (typeof updateCartUI === 'function') {
                updateCartUI();
            } else if (window.updateCartUI) {
                window.updateCartUI();
            }
        })
        .catch(function (err) {
            console.error('Header injection failed:', err);
        });
})();
