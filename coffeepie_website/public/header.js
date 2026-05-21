/**
 * Reusable Header Component Loader
 * Fetches header.html and injects it into the page.
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
