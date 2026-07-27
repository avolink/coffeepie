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

/**
 * Asistente virtual (site-wide loader).
 *
 * Vive aquí porque /footer.js es el único script que cargan TODAS las páginas
 * exportadas de Wix, y su marcado está horneado: añadir una etiqueta <script>
 * a mano significaría editar quince ficheros y acordarse del decimosexto. El
 * cargador va en su propio IIFE, separado del de arriba, porque aquél sale
 * temprano cuando la página no tiene footer — y el asistente debe aparecer
 * igualmente.
 *
 * Las páginas propias de la aplicación (machines.html, panel.html) incluyen
 * cp-chat.js con su etiqueta, así que aquí se comprueba antes de duplicar.
 */
(function () {
    'use strict';

    if (window.CoffeePieChat) return;                       // ya montado por la página
    if (document.querySelector('script[src^="/js/cp-chat.js"]')) return;

    if (!document.querySelector('link[href^="/css/cp-chat.css"]')) {
        var css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = '/css/cp-chat.css';
        document.head.appendChild(css);
    }

    var s = document.createElement('script');
    s.src = '/js/cp-chat.js';
    s.defer = true;
    document.head.appendChild(s);
})();
