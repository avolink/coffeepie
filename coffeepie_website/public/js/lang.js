// Coffee Pie Language Manager
// Auto-detects locale, persists preference, swaps text without reload.
// Dictionary: /translations.json
// Supports __group__ merged-paragraph entries for WRichText components.
(function () {
    'use strict';

    var SUPPORTED = ['es', 'en', 'pt', 'fr', 'de', 'ja', 'ko', 'zh', 'ru', 'ar', 'hi'];
    var DEFAULT = 'es';
    var STORAGE_KEY = 'cp_lang';
    var ORIGINAL_ATTR = 'data-cp-original';
    var TRANSLATED_ATTR = 'data-cp-translated';
    var GROUP_ATTR = 'data-cp-group';
    var GROUP_SEPARATOR = ' ||| ';
    var dict = null;
    var fastLookup = null;   // Map: normalizedES -> [entry, ...]
    var groupLookup = null;  // Map: normalizedES -> entry (for __group__ keys)
    var currentLang = DEFAULT;

    // ---- Locale detection ----

    function normalizeLang(raw) {
        if (!raw) return null;
        var tag = String(raw).split('-')[0].toLowerCase();
        return SUPPORTED.indexOf(tag) !== -1 ? tag : null;
    }

    function detectLocale() {
        var saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            var norm = normalizeLang(saved);
            if (norm) return norm;
        }
        try {
            var cookieMatch = document.cookie.match(/(?:^|;\s*)uds_lang=([^;]*)/);
            if (cookieMatch) {
                var cnorm = normalizeLang(cookieMatch[1]);
                if (cnorm) return cnorm;
            }
        } catch (e) { /* ignore */ }
        if (navigator.language) {
            var bnorm = normalizeLang(navigator.language);
            if (bnorm) return bnorm;
        }
        if (document.documentElement.lang) {
            var hnorm = normalizeLang(document.documentElement.lang);
            if (hnorm) return hnorm;
        }
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
                    groupLookup = new Map();
                    cb();
                }
            } else {
                dict = {};
                fastLookup = new Map();
                groupLookup = new Map();
                cb();
            }
        };
        xhr.send();
    }

    function buildFastLookup() {
        fastLookup = new Map();
        groupLookup = new Map();
        for (var key in dict) {
            if (!dict.hasOwnProperty(key)) continue;
            var entry = dict[key];
            if (!entry.es) continue;
            var normalized = normalizeText(entry.es);
            if (!normalized) continue;

            if (key.indexOf('__group__') === 0) {
                groupLookup.set(normalized, entry);
            } else {
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

        var entries = fastLookup.get(norm);
        if (!entries) return null;

        for (var i = 0; i < entries.length; i++) {
            if (entries[i][toLang] && entries[i][toLang] !== entries[i].es) {
                if (normalizeText(entries[i].es) === norm) {
                    return entries[i][toLang];
                }
            }
        }
        return null;
    }

    // ---- Group (merged paragraph) translation ----

    function tryGroupTranslate(el, toLang) {
        if (groupLookup.size === 0) return false;
        if (el.getAttribute(GROUP_ATTR)) return false; // already processed

        var children = el.children;
        if (!children || children.length < 2) return false;

        // Collect text-bearing child elements (skip empty/guard ones)
        var textParts = [];
        var childElements = [];
        for (var i = 0; i < children.length; i++) {
            var child = children[i];
            var text = (child.textContent || '').trim();
            if (text.length < 2) continue;
            if (/^[\s\u200B\u00A0]*$/.test(text)) continue;
            textParts.push(text);
            childElements.push(child);
        }

        if (textParts.length < 2) return false;

        // Build concatenated text with separator
        var concatText = textParts.join(GROUP_SEPARATOR);
        var normConcat = normalizeText(concatText);

        // Look up group translation
        var groupEntry = groupLookup.get(normConcat);
        if (!groupEntry) return false;
        if (!groupEntry[toLang] || groupEntry[toLang] === groupEntry.es) return false;

        var translatedText = groupEntry[toLang];
        var translatedParts = splitGroupTranslation(translatedText, textParts.length, concatText);

        if (translatedParts && translatedParts.length === textParts.length) {
            // Apply translations to individual children
            for (var p = 0; p < childElements.length; p++) {
                var child = childElements[p];
                if (!child.getAttribute(ORIGINAL_ATTR)) {
                    child.setAttribute(ORIGINAL_ATTR, textParts[p]);
                }
                child.textContent = translatedParts[p].trim();
                child.setAttribute(TRANSLATED_ATTR, toLang);
            }
            el.setAttribute(GROUP_ATTR, 'true');
            return true;
        }

        return false;
    }

    function splitGroupTranslation(translated, expectedParts, originalConcat) {
        // Strategy 1: split by exact separator
        var parts = translated.split(GROUP_SEPARATOR);
        if (parts.length === expectedParts) return parts;

        // Strategy 2: split by separator without surrounding spaces
        parts = translated.split('|||');
        if (parts.length === expectedParts) return parts;

        // Strategy 3: split by sentence boundaries using Intl.Segmenter
        if (window.Intl && window.Intl.Segmenter) {
            try {
                var segmenter = new Intl.Segmenter(undefined, { granularity: 'sentence' });
                var segments = Array.from(segmenter.segment(translated), function (s) { return s.segment; });
                if (segments.length === expectedParts) return segments;
            } catch (e) { /* ignore */ }
        }

        // Strategy 4: try matching original parts by length and finding them in translated
        var origParts = originalConcat.split(GROUP_SEPARATOR);
        if (origParts.length === expectedParts) {
            parts = [];
            var startPos = 0;
            for (var i = 0; i < expectedParts - 1; i++) {
                var origLen = origParts[i].length;
                var totalLen = translated.length;
                var ratio = origLen / originalConcat.length;
                var splitAt = Math.round(startPos + ratio * totalLen);
                // Adjust to nearest sentence boundary
                var searchStart = Math.max(0, splitAt - 40);
                var searchEnd = Math.min(translated.length, splitAt + 40);
                var sentenceEnd = findSentenceEnd(translated, splitAt, searchStart, searchEnd);
                parts.push(translated.substring(startPos, sentenceEnd).trim());
                startPos = sentenceEnd;
            }
            parts.push(translated.substring(startPos).trim());
            if (parts.length === expectedParts) return parts;
        }

        return null;
    }

    function findSentenceEnd(text, preferred, searchStart, searchEnd) {
        // Find a sentence-ending character near the preferred position
        var sentenceEnds = /[.?!。！？\n](?=\s|$)/g;
        var match;
        var best = preferred;
        while ((match = sentenceEnds.exec(text)) !== null) {
            var pos = match.index + match[0].length;
            if (pos >= searchStart && pos <= searchEnd) {
                if (Math.abs(pos - preferred) < Math.abs(best - preferred)) {
                    best = pos;
                }
            }
        }
        return best;
    }

    // ---- DOM translation ----

    function translateElement(el, toLang) {
        if (!el) return;

        if (el.closest('[data-cp-no-translate]')) return;
        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'NOSCRIPT') return;
        if (el.tagName === 'CODE' || el.tagName === 'PRE') return;
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return;

        // Try group-level translation for rich text components
        if (el.hasAttribute && el.getAttribute('data-testid') === 'richTextElement') {
            if (tryGroupTranslate(el, toLang)) {
                return;
            }
        }

        var childNodes = Array.prototype.slice.call(el.childNodes);
        for (var i = 0; i < childNodes.length; i++) {
            var node = childNodes[i];
            if (node.nodeType === Node.TEXT_NODE) {
                translateTextNode(node, toLang);
            } else if (node.nodeType === Node.ELEMENT_NODE) {
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

        var trimmed = workingText.trim();
        if (trimmed.length < 2) return;
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
            // Restore text node if element has only one text node child
            if (el.childNodes.length === 1 && el.firstChild && el.firstChild.nodeType === Node.TEXT_NODE) {
                el.firstChild.textContent = original;
            } else {
                el.textContent = original;
            }
            el.removeAttribute(TRANSLATED_ATTR);
        }
        // Clear group markers so groups can re-translate
        var groups = document.querySelectorAll('[' + GROUP_ATTR + ']');
        for (var j = 0; j < groups.length; j++) {
            groups[j].removeAttribute(GROUP_ATTR);
        }
    }

    // ---- Apply translation to entire page ----

    function applyLanguage(lang) {
        if (!dict || !fastLookup) return;
        currentLang = lang;

        restoreAllOriginals();

        if (lang === 'es') {
            document.documentElement.lang = 'es';
            updateLanguageIndicator('es');
            return;
        }

        translateElement(document.body, lang);

        document.documentElement.lang = lang;
        updateLanguageIndicator(lang);
    }

    // ---- Language indicator ----

    function updateLanguageIndicator(lang) {
        var indicator = document.getElementById('cp-lang-indicator');
        if (indicator) {
            indicator.textContent = lang.toUpperCase();
        }
    }

    // ---- Wix LanguageSelector integration ----

    function watchWixLanguageSelector() {
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

        var observer = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var m = mutations[i];
                if (m.type === 'attributes' && m.attributeName === 'class') {
                    onLangChange();
                    break;
                }
            }
        });

        function attachObserver() {
            var selectors = document.querySelectorAll('.WfZwmg button, [data-language-selector] button');
            selectors.forEach(function (btn) {
                observer.observe(btn, { attributes: true, attributeFilter: ['class'] });
                btn.addEventListener('click', function () {
                    setTimeout(onLangChange, 350);
                });
            });
        }

        attachObserver();

        setTimeout(attachObserver, 1500);
        setTimeout(attachObserver, 4000);
    }

    function detectLocaleFromDOM() {
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
            restoreAllOriginals();
            if (currentLang !== 'es') {
                translateElement(document.body, currentLang);
            }
            document.documentElement.lang = currentLang;
            updateLanguageIndicator(currentLang);

            watchWixLanguageSelector();
        });
    }

    window.CoffeePieLang = {
        set: setLanguage,
        get: getLanguage,
        refresh: function () { applyLanguage(currentLang); },
        supported: SUPPORTED
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
