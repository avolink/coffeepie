/**
 * Reusable Header Component Loader
 * Fetches header.html and injects it into the page, then wires up hamburger menu behavior.
 */
(function () {
    'use strict';

    // Find the placeholder where the header should be injected
    var placeholder = document.getElementById('reusable-header-placeholder');
    if (!placeholder) return;

    // Load header CSS
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
            // Insert the header HTML
            placeholder.insertAdjacentHTML('afterend', html);
            placeholder.remove();

            // Wire up hamburger menu
            initHamburgerMenu();

            // Populate header language dropdown (defined in translate.js)
            if (typeof populateHeaderDropdown === 'function') {
                populateHeaderDropdown();
            }
        })
        .catch(function (err) {
            console.error('Header injection failed:', err);
        });

    function initHamburgerMenu() {
        var overlay = document.querySelector('[data-part="hamburger-overlay"]');
        if (!overlay) return;

        // Open button
        var openBtn = document.querySelector('[data-semantic-classname="hamburger-open-button"] button') ||
            document.querySelector('.avoui-hamburger-open-button');

        // Close button  
        var closeBtn = document.querySelector('[data-semantic-classname="hamburger-close-button"] button') ||
            document.querySelector('.avoui-hamburger-close-button');

        function openMenu() {
            overlay.setAttribute('data-visible', 'true');
            overlay.style.display = '';
            overlay.style.visibility = 'visible';
            overlay.style.opacity = '1';
            overlay.classList.add('HamburgerOverlay547129737--visible');
            overlay.classList.remove('HamburgerOverlay547129737--hidden');
            document.body.style.overflow = 'hidden';

            if (openBtn) openBtn.setAttribute('aria-expanded', 'true');

            var dialogOverlay = overlay.querySelector('[data-hook="hamburger-overlay-dialog"]');
            if (dialogOverlay) {
                dialogOverlay.setAttribute('aria-hidden', 'false');
                dialogOverlay.style.opacity = '1';
            }

            // Focus the overlay for accessibility
            overlay.focus();
        }

        function closeMenu() {
            overlay.setAttribute('data-visible', 'false');
            overlay.style.visibility = 'hidden';
            overlay.style.opacity = '0';
            overlay.classList.remove('HamburgerOverlay547129737--visible');
            overlay.classList.add('HamburgerOverlay547129737--hidden');
            document.body.style.overflow = '';

            if (openBtn) openBtn.setAttribute('aria-expanded', 'false');

            var dialogOverlay = overlay.querySelector('[data-hook="hamburger-overlay-dialog"]');
            if (dialogOverlay) {
                dialogOverlay.setAttribute('aria-hidden', 'true');
            }
        }

        // Click handlers via event delegation
        document.addEventListener('click', function (e) {
            // Open trigger: hamburger open button
            var isOpenTrigger = e.target.closest('[data-semantic-classname="hamburger-open-button"]') ||
                e.target.closest('.avoui-hamburger-open-button') ||
                e.target.closest('[aria-label="Menu"]');

            // Close trigger: close button, background overlay, or nav link
            var isCloseTrigger = e.target.closest('[data-semantic-classname="hamburger-close-button"]') ||
                e.target.closest('.avoui-hamburger-close-button') ||
                e.target.closest('[aria-label="Close"]') ||
                e.target.closest('[aria-label="Cerrar"]') ||
                e.target.closest('.HamburgerOverlay547129737__overlay');

            // Link trigger: clicking a menu link should close overlay
            var isLinkTrigger = e.target.closest('.avoui-vertical-menu__item-label');

            if (isOpenTrigger && !isOpenTrigger.closest('[data-part="hamburger-overlay"]')) {
                e.preventDefault();
                e.stopPropagation();
                openMenu();
                return;
            }

            if (isCloseTrigger || isLinkTrigger) {
                closeMenu();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay.getAttribute('data-visible') === 'true') {
                closeMenu();
                if (openBtn) openBtn.focus();
            }
        });
    }
})();
