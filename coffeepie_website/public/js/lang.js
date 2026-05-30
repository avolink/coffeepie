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

    function enforceLTRNumbers(text) {
        if (!text) return text;
        // Match sequences of ASCII alphanumeric characters, standard symbols, and spaces
        // but only wrap them if they contain at least one digit.
        var asciiSeqRegex = /[a-zA-Z\d\$€£¥\+‐\-®™#%*@()\[\]\/\\:;',.‘’“”'_]+(?:\s+[a-zA-Z\d\$€£¥\+‐\-®™#%*@()\[\]\/\\:;',.‘’“”'_]+)*(?:\s*[a-zA-Z\d\$€£¥\+‐\-®™#%*@()\[\]\/\\:;',.‘’“”'_]+)?/gi;
        
        return text.replace(asciiSeqRegex, function (match) {
            if (/\d/.test(match)) {
                return '\u200E' + match + '\u200E';
            }
            return match;
        });
    }

    // ---- Translation engine ----

    function translateText(text, toLang) {
        if (!text || !toLang || !fastLookup) return null;
        var norm = normalizeText(text);
        if (!norm) return null;

        var entries = fastLookup.get(norm);
        if (!entries) {
            if (toLang === 'ar') {
                return enforceLTRNumbers(text);
            }
            return null;
        }

        for (var i = 0; i < entries.length; i++) {
            if (entries[i][toLang] && entries[i][toLang] !== entries[i].es) {
                if (normalizeText(entries[i].es) === norm) {
                    var res = entries[i][toLang];
                    if (toLang === 'ar') {
                        res = enforceLTRNumbers(res);
                    }
                    return res;
                }
            }
        }
        if (toLang === 'ar') {
            return enforceLTRNumbers(text);
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
        if (toLang === 'ar') {
            translatedText = enforceLTRNumbers(translatedText);
        }
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

        // Skip wrapper spans that already track their own original (inline-fragment fix)
        if (el.hasAttribute && el.hasAttribute(ORIGINAL_ATTR) && el.childNodes.length === 1 && el.firstChild && el.firstChild.nodeType === Node.TEXT_NODE) {
            translateTextNode(el.firstChild, toLang);
            return;
        }

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

    function countTextSiblings(textNode) {
        var siblings = textNode.parentElement.childNodes;
        var count = 0;
        for (var s = 0; s < siblings.length; s++) {
            if (siblings[s] !== textNode && siblings[s].nodeType === Node.TEXT_NODE && siblings[s].textContent.trim().length > 0) {
                count++;
            }
        }
        return count;
    }

    function translateTextNode(textNode, toLang) {
        var parent = textNode.parentElement;
        var parentOriginal = parent.getAttribute(ORIGINAL_ATTR);
        var parentHasMultiple = countTextSiblings(textNode) > 0;

        // If parent has multiple text children and already stores an original,
        // that original belongs to a DIFFERENT text node. Use this node's own content.
        var workingText;
        if (parentOriginal && parentHasMultiple) {
            workingText = textNode.textContent;
        } else {
            workingText = parentOriginal || textNode.textContent;
        }

        var trimmed = workingText.trim();
        if (trimmed.length < 2) return;
        if (/^[\d\s.,'%$€£¥+#*\-–—]+$/.test(trimmed)) {
            if (toLang === 'ar' && /\d/.test(trimmed)) {
                var enforced = '\u200E' + workingText + '\u200E';
                if (textNode.textContent !== enforced) {
                    if (parentHasMultiple) {
                        var wrapper = document.createElement('span');
                        wrapper.setAttribute(ORIGINAL_ATTR, workingText);
                        wrapper.textContent = enforced;
                        wrapper.setAttribute(TRANSLATED_ATTR, toLang);
                        parent.replaceChild(wrapper, textNode);
                    } else {
                        if (!parentOriginal) {
                            parent.setAttribute(ORIGINAL_ATTR, workingText);
                        }
                        textNode.textContent = enforced;
                        parent.setAttribute(TRANSLATED_ATTR, toLang);
                    }
                }
            }
            return;
        }

        if (parentOriginal && textNode.textContent.trim().length === 0) return;

        var translated = translateText(workingText, toLang);
        if (translated !== null && translated !== workingText) {
            // Preserve original leading and trailing whitespace to prevent string concatenation issues
            var matchLeading = workingText.match(/^[\s\u00A0\n\t]+/);
            var matchTrailing = workingText.match(/[\s\u00A0\n\t]+$/);
            if (matchLeading && !translated.startsWith(matchLeading[0])) {
                translated = matchLeading[0] + translated;
            }
            if (matchTrailing && !translated.endsWith(matchTrailing[0])) {
                translated = translated + matchTrailing[0];
            }

            if (parentHasMultiple) {
                // Wrap this fragment in a span so each fragment tracks its own original
                var wrapper = document.createElement('span');
                wrapper.setAttribute(ORIGINAL_ATTR, workingText);
                wrapper.textContent = translated;
                wrapper.setAttribute(TRANSLATED_ATTR, toLang);
                parent.replaceChild(wrapper, textNode);
            } else {
                // Single text child: store original on parent (existing behavior)
                if (!parentOriginal) {
                    parent.setAttribute(ORIGINAL_ATTR, workingText);
                }
                textNode.textContent = translated;
                parent.setAttribute(TRANSLATED_ATTR, toLang);
            }
        }
    }

    // Restore all original text before re-translating
    function restoreAllOriginals() {
        var els = document.querySelectorAll('[' + ORIGINAL_ATTR + ']');
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            var original = el.getAttribute(ORIGINAL_ATTR);

            // Check if any child element has its own data-cp-original
            // (wrapper spans from inline-fragment translation)
            var hasIndependentChildren = false;
            for (var k = 0; k < el.children.length; k++) {
                if (el.children[k].hasAttribute(ORIGINAL_ATTR)) {
                    hasIndependentChildren = true;
                    break;
                }
            }

            if (hasIndependentChildren) {
                // Children track their own originals — only clean up this element's markers
                el.removeAttribute(TRANSLATED_ATTR);
                continue;
            }

            if (el.childNodes.length === 1 && el.firstChild && el.firstChild.nodeType === Node.TEXT_NODE) {
                el.firstChild.textContent = original;
            } else {
                var children = el.childNodes;
                var restored = false;
                for (var j = 0; j < children.length; j++) {
                    if (children[j].nodeType === Node.TEXT_NODE && children[j].textContent.trim().length > 0) {
                        children[j].textContent = original;
                        restored = true;
                        break;
                    }
                }
                if (!restored) {
                    el.textContent = original;
                }
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

        injectRTLCSS();
        if (lang === 'ar') {
            document.body.classList.add('lang-ar');
        } else {
            document.body.classList.remove('lang-ar');
        }

        restoreAllOriginals();

        if (lang !== 'es') {
            translateElement(document.body, lang);
            fixBrandSpacing(document.body);
        }

        document.documentElement.lang = lang;
        updateLanguageIndicator(lang);

        if (lang === 'es') {
            fixBrandSpacing(document.body);
        }

        // Notify listeners (e.g. vanilla-gallery) to re-render
        if (typeof CustomEvent !== 'undefined') {
            window.dispatchEvent(new CustomEvent('cplangchange', {detail: {lang: lang}}));
        }
    }

    // ---- Language indicator ----

    function updateLanguageIndicator(lang) {
        var indicator = document.getElementById('cp-lang-indicator');
        if (indicator) {
            indicator.textContent = lang.toUpperCase();
        }
    }

    // ---- RTL Arabic Support ----
    
    function injectRTLCSS() {
        if (document.getElementById('cp-rtl-style')) return;
        var style = document.createElement('style');
        style.id = 'cp-rtl-style';
        style.type = 'text/css';
        style.innerHTML = `
            .lang-ar p, .lang-ar h1, .lang-ar h2, .lang-ar h3, .lang-ar h4, .lang-ar h5, .lang-ar h6, .lang-ar li, .lang-ar a, .lang-ar span {
                text-align: right !important;
                direction: rtl !important;
            }
            .lang-ar [style*="text-align: center"], 
            .lang-ar [style*="text-align:center"] {
                text-align: center !important;
            }
            .lang-ar [id$="_r_comp-lzg0bwm6"] p,
            .lang-ar [id$="_r_comp-lzg0bwm6"] span {
                text-align: left !important;
                direction: ltr !important;
            }
            .lang-ar .slider-value,
            .lang-ar .cart-item-price,
            .lang-ar .cart-item-unit-price,
            .lang-ar .avo-cart-qty-input,
            .lang-ar .license-key-code,
            .lang-ar .invoice-amount,
            .lang-ar code,
            .lang-ar [id*="total"],
            .lang-ar [id*="price"],
            .lang-ar [id*="amount"],
            .lang-ar [id*="value"],
            .lang-ar [id*="balance"],
            .lang-ar [class*="price"],
            .lang-ar [class*="value"],
            .lang-ar [class*="qty"],
            .lang-ar [class*="total"],
            .lang-ar [class*="amount"],
            .lang-ar [data-hook*="total"],
            .lang-ar [data-hook*="subtotal"],
            .lang-ar td[data-label*="Fecha"],
            .lang-ar td[data-label*="Inicio"],
            .lang-ar td[data-label*="Expiracion"], .lang-ar td[data-label*="Expiración"],
            .lang-ar td[data-label*="Monto"],
            .lang-ar td[data-label*="Creditos"],
            .lang-ar td[data-label*="Terminal"],
            .lang-ar td[data-label*="Factura"],
            .lang-ar td[data-label*="Budget"],
            .lang-ar td[data-label*="Presupuesto"] {
                direction: ltr !important;
                unicode-bidi: isolate !important;
            }
        `;
        document.head.appendChild(style);
    }

    // ---- Brand spacing fix ----
    // After translation, text nodes adjacent to brand-name <span> elements
    // may lose spacing because the original DOM whitespace gets trimmed.
    // This ensures proper spacing around Coffee Pie®, Commanders™, etc.

    var BRAND_NAMES = ['Coffee Pie®', 'Commanders™', 'Sentinels™', 'Rangers™'];

    function fixBrandSpacing(root) {
        if (!root) return;

        // Walk all text-bearing leaf elements looking for brand names
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
        var el;
        while ((el = walker.nextNode())) {
            // Only process simple text-bearing elements (leaves)
            if (el.children.length > 0) continue;
            if (el.getAttribute && el.getAttribute(ORIGINAL_ATTR)) {
                // Skip wrapper spans with their own original — handle in second pass
                continue;
            }
            if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;

            var text = (el.textContent || '').trim();
            if (!text) continue;

            // Check if this element's text is a brand name
            var isBrand = false;
            for (var b = 0; b < BRAND_NAMES.length; b++) {
                if (text === BRAND_NAMES[b]) {
                    isBrand = true;
                    break;
                }
            }
            if (!isBrand) continue;

            // Fix previous sibling text node (or translated wrapper): ensure it ends with a space
            var prev = el.previousSibling;
            while (prev && prev.nodeType !== Node.TEXT_NODE && !(prev.nodeType === Node.ELEMENT_NODE && prev.hasAttribute(ORIGINAL_ATTR))) {
                prev = prev.previousSibling;
            }
            if (prev && prev.textContent.length > 0) {
                if (!prev.textContent.endsWith(' ') && !prev.textContent.endsWith('\u00A0') && !prev.textContent.endsWith('\n')) {
                    prev.textContent = prev.textContent + ' ';
                }
            }

            // Fix next sibling text node (or translated wrapper): ensure it starts with a space
            var next = el.nextSibling;
            while (next && next.nodeType !== Node.TEXT_NODE && !(next.nodeType === Node.ELEMENT_NODE && next.hasAttribute(ORIGINAL_ATTR))) {
                next = next.nextSibling;
            }
            if (next && next.textContent.length > 0) {
                if (!next.textContent.startsWith(' ') && !next.textContent.startsWith('\u00A0') && !next.textContent.startsWith('\n')) {
                    next.textContent = ' ' + next.textContent;
                }
            }
        }
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
            applyLanguage(currentLang);
        });
    }

    window.CoffeePieLang = {
        set: setLanguage,
        get: getLanguage,
        translate: translateText,
        refresh: function () { applyLanguage(currentLang); },
        supported: SUPPORTED,
        enforceLTRNumbers: enforceLTRNumbers
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
