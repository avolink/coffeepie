/**
 * Reusable Header Component Loader
 * Fetches header.html and injects it into the page.
 * Also ensures language/translation support (lang.js) is loaded.
 * Hamburger menu is handled by translate.js (Vanilla JS implementation).
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

    fetch('/header.html')
        .then(function (response) {
            if (!response.ok) throw new Error('Failed to load header.html');
            return response.text();
        })
        .then(function (html) {
            placeholder.insertAdjacentHTML('afterend', html);
            placeholder.remove();

            if (typeof populateHeaderDropdown === 'function') {
                populateHeaderDropdown();
            }
        })
        .catch(function (err) {
            console.error('Header injection failed:', err);
        });
})();
