/**
 * Reusable Footer Component Loader
 * Fetches footer.html and injects it into the page.
 * Also ensures language/translation support (lang.js) is loaded.
 */
(function () {
    'use strict';

    var placeholder = document.getElementById('reusable-footer-placeholder');
    if (!placeholder) return;

    if (!document.querySelector('link[href="/footer.css"]')) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/footer.css';
        document.head.appendChild(link);
    }

    if (!document.querySelector('script[src="/js/lang.js"]') && !window.CoffeePieLang) {
        var langScript = document.createElement('script');
        langScript.src = '/js/lang.js';
        document.head.appendChild(langScript);
    }

    fetch('/footer.html')
        .then(function (response) {
            if (!response.ok) throw new Error('Failed to load footer.html');
            return response.text();
        })
        .then(function (html) {
            placeholder.insertAdjacentHTML('afterend', html);
            placeholder.remove();
            initFooterVideo();
            if (window.CoffeePieLang && typeof window.CoffeePieLang.refresh === 'function') {
                window.CoffeePieLang.refresh();
            }
        })
        .catch(function (err) {
            console.error('Footer injection failed:', err);
        });

    function initFooterVideo() {
        var footer = document.getElementById('cp-footer');
        var video = document.getElementById('cp-footer-video');
        var playBtn = document.getElementById('cp-footer-play-btn');
        var pauseBtn = document.getElementById('cp-footer-pause-btn');
        var muteBtn = document.getElementById('cp-footer-mute-btn');

        if (!footer || !video) return;

        footer.setAttribute('data-playing', 'true');
        footer.setAttribute('data-muted', 'true');

        pauseBtn.addEventListener('click', function () {
            video.pause();
            footer.setAttribute('data-playing', 'false');
        });

        playBtn.addEventListener('click', function () {
            video.play();
            footer.setAttribute('data-playing', 'true');
        });

        muteBtn.addEventListener('click', function () {
            if (video.muted) {
                video.muted = false;
                footer.setAttribute('data-muted', 'false');
                muteBtn.setAttribute('aria-pressed', 'true');
            } else {
                video.muted = true;
                footer.setAttribute('data-muted', 'true');
                muteBtn.setAttribute('aria-pressed', 'false');
            }
        });

        video.addEventListener('play', function () {
            footer.setAttribute('data-playing', 'true');
        });

        video.addEventListener('pause', function () {
            footer.setAttribute('data-playing', 'false');
        });
    }
})();
