// Coffee Pie Language Manager
// Auto-detects locale, persists preference, swaps text without reload.
// Dictionary: /translations.json
(function () {
    'use strict';

    var SUPPORTED = ['es', 'en', 'pt', 'fr', 'de', 'ja', 'ko', 'zh', 'ru', 'ar', 'hi'];
    var DEFAULT = 'es';
    var STORAGE_KEY = 'cp_lang';
    var ORIGINAL_ATTR = 'data-cp-original';
    var TRANSLATED_ATTR = 'data-cp-translated';
    var dict = null;       // { "textKey": { "es":"...", "en":"...", ... } }
    var fastLookup = null; // Map: normalizedES -> fullKeyEntry
    var currentLang = DEFAULT;

    // ---- Locale detection ----

    function normalizeLang(raw) {
        if (!raw) return null;
        var tag = String(raw).split('-')[0].toLowerCase();
        return SUPPORTED.indexOf(tag) !== -1 ? tag : null;
    }

    function detectLocale() {
        // 1. Saved preference
        var saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            var norm = normalizeLang(saved);
            if (norm) return norm;
        }
        // 2. document cookie (used by some Wix/backend setups)
        try {
            var cookieMatch = document.cookie.match(/(?:^|;\s*)uds_lang=([^;]*)/);
            if (cookieMatch) {
                var cnorm = normalizeLang(cookieMatch[1]);
                if (cnorm) return cnorm;
            }
        } catch (e) { /* ignore */ }
        // 3. Browser navigator
        if (navigator.language) {
            var bnorm = normalizeLang(navigator.language);
            if (bnorm) return bnorm;
        }
        // 4. <html lang> attribute
        if (document.documentElement.lang) {
            var hnorm = normalizeLang(document.documentElement.lang);
            if (hnorm) return hnorm;
        }
        // 5. Fallback
        return DEFAULT;
    }

    // ---- Dictionary loading ----

    function loadDictionary(cb) {
        if (dict) return cb();

        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/translations.json', true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200 || xhr.status === 304) {
                try {
                    dict = JSON.parse(xhr.responseText);
                    buildFastLookup();
                    cb();
                } catch (e) {
                    console.warn('Coffee Pie Lang: failed to parse translations.json', e);
                    dict = {};
                    fastLookup = new Map();
                    cb();
                }
            } else {
                console.warn('Coffee Pie Lang: could not load translations.json (status ' + xhr.status + ')');
                dict = {};
                fastLookup = new Map();
                cb();
            }
        };
        xhr.send();
    }

    function buildFastLookup() {
        fastLookup = new Map();
        // Build index keyed by the Spanish text (es) normalized to single-line
        for (var key in dict) {
            if (!dict.hasOwnProperty(key)) continue;
            var entry = dict[key];
            if (!entry.es) continue;
            var normalized = normalizeText(entry.es);
            if (normalized) {
                // Store ALL entries that map to this normalized text
                var arr = fastLookup.get(normalized);
                if (!arr) { arr = []; fastLookup.set(normalized, arr); }
                arr.push(entry);
            }
        }
    }

    function normalizeText(t) {
        if (!t) return '';
        return t.replace(/[\n\t]+/g, ' ').replace(/\s+/g, ' ').trim();
    }

    // ---- Translation engine ----

    function translateText(text, toLang) {
        if (!text || !toLang || !fastLookup) return null;
        var norm = normalizeText(text);
        if (!norm) return null;

        // Exact match first
        var entries = fastLookup.get(norm);
        if (!entries) return null;

        for (var i = 0; i < entries.length; i++) {
            if (entries[i][toLang] && entries[i][toLang] !== entries[i].es) {
                // For multiline entries, normalize both sides for comparison
                if (normalizeText(entries[i].es) === norm) {
                    return entries[i][toLang];
                }
            }
        }
        return null;
    }

    function translateElement(el, toLang) {
        if (!el) return;

        // Skip elements that should not be translated
        if (el.closest('[data-cp-no-translate]')) return;
        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'NOSCRIPT') return;
        if (el.tagName === 'CODE' || el.tagName === 'PRE') return;
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return;

        // Process child nodes
        var childNodes = Array.prototype.slice.call(el.childNodes);
        for (var i = 0; i < childNodes.length; i++) {
            var node = childNodes[i];
            if (node.nodeType === Node.TEXT_NODE) {
                translateTextNode(node, toLang);
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                // For elements that contain only text (like <span>, <p>, <li>, <a>, <th>, <td>, <button>)
                if (node.children.length === 0 && node.childNodes.length === 1 && node.firstChild.nodeType === Node.TEXT_NODE) {
                    translateTextNode(node.firstChild, toLang);
                } else {
                    translateElement(node, toLang);
                }
            }
        }
    }

    function translateTextNode(textNode, toLang) {
        var original = textNode.parentElement.getAttribute(ORIGINAL_ATTR);
        var workingText = original || textNode.textContent;

        // Skip tiny/empty text
        var trimmed = workingText.trim();
        if (trimmed.length < 2) return;
        // Skip pure numbers
        if (/^[\d\s.,'%$€£¥+#*\-–—]+$/.test(trimmed)) return;

        var translated = translateText(workingText, toLang);
        if (translated !== null && translated !== workingText) {
            if (!original) {
                textNode.parentElement.setAttribute(ORIGINAL_ATTR, workingText);
            }
            textNode.textContent = translated;
            textNode.parentElement.setAttribute(TRANSLATED_ATTR, toLang);
        }
    }

    // Restore all original text before re-translating
    function restoreAllOriginals() {
        var els = document.querySelectorAll('[' + ORIGINAL_ATTR + ']');
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            var original = el.getAttribute(ORIGINAL_ATTR);
            var textNode = el.firstChild;
            if (textNode && textNode.nodeType === Node.TEXT_NODE && original) {
                textNode.textContent = original;
            }
        }
    }

    // ---- Apply translation to entire page ----

    function applyLanguage(lang) {
        if (!dict || !fastLookup) return;
        currentLang = lang;

        // First restore all originals to base state
        restoreAllOriginals();

        // If target is Spanish, nothing more to do (originals are Spanish)
        if (lang === 'es') {
            document.documentElement.lang = 'es';
            updateLanguageIndicator('es');
            return;
        }

        // Walk the DOM and translate
        translateElement(document.body, lang);

        document.documentElement.lang = lang;
        updateLanguageIndicator(lang);
    }

    // ---- Language indicator (optional visual feedback) ----

    function updateLanguageIndicator(lang) {
        // If there's a custom indicator element, update it
        var indicator = document.getElementById('cp-lang-indicator');
        if (indicator) {
            indicator.textContent = lang.toUpperCase();
        }
    }

    // ---- Wix LanguageSelector integration ----

    function watchWixLanguageSelector() {
        // The Wix LanguageSelector is a radio-button based component
        // It uses buttons with class wbgQXa for the active state
        // Watch for clicks on language selector buttons and re-translate

        var debounceTimer;

        function onLangChange() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                var newLang = detectLocaleFromDOM();
                if (newLang && newLang !== currentLang) {
                    localStorage.setItem(STORAGE_KEY, newLang);
                    applyLanguage(newLang);
                }
            }, 300);
        }

        // Watch for DOM mutations in the language selector area
        var observer = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var m = mutations[i];
                if (m.type === 'attributes' && m.attributeName === 'class') {
                    onLangChange();
                    break;
                }
            }
        });

        // Try to find and observe all language selector buttons
        function attachObserver() {
            var selectors = document.querySelectorAll('.WfZwmg button, [data-language-selector] button');
            selectors.forEach(function (btn) {
                observer.observe(btn, { attributes: true, attributeFilter: ['class'] });
                btn.addEventListener('click', function () {
                    // The click fires before the class change, so delay
                    setTimeout(onLangChange, 350);
                });
            });
        }

        attachObserver();

        // Re-attach after Wix platform hydrates the page
        setTimeout(attachObserver, 1500);
        setTimeout(attachObserver, 4000);
    }

    function detectLocaleFromDOM() {
        // Check what Wix has set as the active language
        // Wix toggles the "wbgQXa" class on active lang button
        var activeBtn = document.querySelector('.WfZwmg button.wbgQXa');
        if (!activeBtn) {
            activeBtn = document.querySelector('.WfZwmg button[aria-current="true"]');
        }
        if (activeBtn) {
            var label = (activeBtn.textContent || '').trim().toLowerCase();
            var langMap = {
                'es': 'es', 'en': 'en', 'pt': 'pt', 'fr': 'fr', 'de': 'de',
                'ja': 'ja', '日本語': 'ja',
                'ko': 'ko', '한국어': 'ko',
                'zh': 'zh', '中文': 'zh',
                'ru': 'ru', 'Русский': 'ru',
                'ar': 'ar', 'العربية': 'ar',
                'hi': 'hi', 'हिन्दी': 'hi'
            };
            if (langMap[label]) return langMap[label];
        }

        // Fallback: check <html lang>
        if (document.documentElement.lang) {
            var hnorm = normalizeLang(document.documentElement.lang);
            if (hnorm) return hnorm;
        }
        return null;
    }

    // ---- Public API ----

    function setLanguage(lang) {
        lang = normalizeLang(lang) || DEFAULT;
        localStorage.setItem(STORAGE_KEY, lang);
        applyLanguage(lang);
    }

    function getLanguage() {
        return currentLang;
    }

    // ---- Initialization ----

    function init() {
        var detected = detectLocale();
        currentLang = detected;
        localStorage.setItem(STORAGE_KEY, detected);

        loadDictionary(function () {
            // Apply initial translation
            restoreAllOriginals();
            if (currentLang !== 'es') {
                translateElement(document.body, currentLang);
            }
            document.documentElement.lang = currentLang;
            updateLanguageIndicator(currentLang);

            // Start watching for Wix language changes
            watchWixLanguageSelector();
        });
    }

    // Expose globals
    window.CoffeePieLang = {
        set: setLanguage,
        get: getLanguage,
        refresh: function () { applyLanguage(currentLang); },
        supported: SUPPORTED
    };

    // Auto-init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
