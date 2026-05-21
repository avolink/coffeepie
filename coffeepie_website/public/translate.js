console.log('[CoffeePie] translate.js starting...');

var LANGUAGES = [
    { locale: 'EN-US', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="18" fill="#B22234"/><rect y="1.38" width="24" height="1.38" fill="#FFF"/><rect y="4.15" width="24" height="1.38" fill="#FFF"/><rect y="6.92" width="24" height="1.38" fill="#FFF"/><rect y="9.69" width="24" height="1.38" fill="#FFF"/><rect y="12.46" width="24" height="1.38" fill="#FFF"/><rect y="15.23" width="24" height="1.38" fill="#FFF"/><rect width="9.6" height="9.69" fill="#3C3B6E"/></svg>' },
    { locale: 'ES-CO', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="9" fill="#FCD116"/><rect y="9" width="24" height="4.5" fill="#003893"/><rect y="13.5" width="24" height="4.5" fill="#CE1126"/></svg>' },
    { locale: 'PT-BR', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="18" fill="#009B3A"/><polygon points="12,1.5 22.5,9 12,16.5 1.5,9" fill="#FEDF00"/><circle cx="12" cy="9" r="4.5" fill="#002776"/></svg>' },
    { locale: 'FR-CA', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="5" height="18" fill="#D52B1E"/><rect x="19" width="5" height="18" fill="#D52B1E"/><rect x="5" width="14" height="18" fill="#FFF"/></svg>' },
    { locale: 'DE-DE', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="6" fill="#000"/><rect y="6" width="24" height="6" fill="#DD0000"/><rect y="12" width="24" height="6" fill="#FFCE00"/></svg>' },
    { locale: 'RU-RU', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="6" fill="#FFF"/><rect y="6" width="24" height="6" fill="#0039A6"/><rect y="12" width="24" height="6" fill="#D52B1E"/></svg>' },
    { locale: 'HI-IN', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="6" fill="#FF9933"/><rect y="6" width="24" height="6" fill="#FFF"/><rect y="12" width="24" height="6" fill="#138808"/><circle cx="12" cy="9" r="2.5" fill="#000080"/></svg>' },
    { locale: 'JA-JP', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="18" fill="#FFF"/><circle cx="12" cy="9" r="5" fill="#BC002D"/></svg>' },
    { locale: 'ZH-CN', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="18" fill="#DE2910"/><polygon points="6,3 6.3,5.3 9,5.3 7,6.8 7.8,9 6,7.5 4.2,9 5,6.8 3,5.3 5.7,5.3" fill="#FFDE00"/></svg>' },
    { locale: 'KO-KR', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="18" fill="#FFF"/><circle cx="11" cy="9" r="4.5" fill="#CD2E3A"/><rect x="6.5" y="9" width="9" height="9" fill="#0047A0"/></svg>' },
    { locale: 'AR-SA', flag: '<svg class="language-flag" viewBox="0 0 24 18"><rect width="24" height="18" fill="#006C35"/><path d="M7 5 L17 13" stroke="#FFF" stroke-width="1.5"/><path d="M7 6.5 L17 14.5" stroke="#FFF" stroke-width="1.5"/></svg>' }
];

var DEFAULT_LOCALE = 'ES-CO';
var STORAGE_KEY = 'cp_lang';

function localeToLang(locale) {
    return (locale || '').split('-')[0].toLowerCase();
}

function findLangData(langCode) {
    for (var i = 0; i < LANGUAGES.length; i++) {
        if (localeToLang(LANGUAGES[i].locale) === langCode) return LANGUAGES[i];
    }
    return LANGUAGES[1];
}

function buildDropdownOptionsHTML(activeLocale) {
    var html = '';
    for (var i = 0; i < LANGUAGES.length; i++) {
        var l = LANGUAGES[i];
        var activeClass = l.locale === activeLocale ? ' cplang-active' : '';
        var currentAttr = l.locale === activeLocale ? ' aria-current="true"' : ' aria-current="false"';
        html += '<button aria-label="' + l.locale + '" class="cplang-option language-dropdown__option' + activeClass + '" type="button" role="option"' + currentAttr + '><div class="LEHGju">' + l.flag + '</div><div class="J6PIw1">' + l.locale + '</div></button>';
    }
    return html;
}

function buildDropdownToggleHTML(locale) {
    var data = findLangData(localeToLang(locale));
    return '<div class="LEHGju">' + data.flag + '</div><div class="J6PIw1">' + data.locale + '</div><span class="language-dropdown__arrow">&#9662;</span>';
}

function getSavedLang() {
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return saved;
    return localeToLang(DEFAULT_LOCALE);
}

function doLanguageSwitch(lang) {
    lang = lang || getSavedLang();
    localStorage.setItem(STORAGE_KEY, lang);
    syncAllLanguageSelectors(lang);
    if (window.CoffeePieLang && typeof window.CoffeePieLang.set === 'function') {
        window.CoffeePieLang.set(lang);
    }
}

function syncAllLanguageSelectors(lang) {
    var activeLocale = findLangData(lang).locale;

    document.querySelectorAll('.cplang-option').forEach(function (btn) {
        if (btn.getAttribute('aria-label') === activeLocale) {
            btn.setAttribute('aria-current', 'true');
            btn.classList.add('cplang-active');
        } else {
            btn.setAttribute('aria-current', 'false');
            btn.classList.remove('cplang-active');
        }
    });

    document.querySelectorAll('.language-dropdown__toggle').forEach(function (toggle) {
        toggle.innerHTML = buildDropdownToggleHTML(activeLocale);
        toggle.setAttribute('aria-label', activeLocale);
        toggle.setAttribute('aria-current', 'true');
        toggle.classList.add('cplang-active');
    });

    document.querySelectorAll('#panel-lang-select, #configLanguage, select[data-cp-lang-select]').forEach(function (select) {
        if (select.value !== lang) {
            select.value = lang;
        }
    });
}

function setupLangDropdown(container) {
    if (!container) return;
    var dropdown = container.querySelector('.language-dropdown');
    if (!dropdown) return;
    var toggle = dropdown.querySelector('.language-dropdown__toggle');
    var optionsContainer = dropdown.querySelector('.language-dropdown__options');
    if (!toggle || !optionsContainer) return;

    function openDropdown() {
        dropdown.classList.add('language-dropdown--open');
        toggle.setAttribute('aria-expanded', 'true');
        setTimeout(function () {
            document.addEventListener('click', handleOutsideClick, true);
        }, 0);
    }

    function closeDropdown() {
        dropdown.classList.remove('language-dropdown--open');
        toggle.setAttribute('aria-expanded', 'false');
        document.removeEventListener('click', handleOutsideClick, true);
    }

    function handleOutsideClick(e) {
        if (!dropdown.contains(e.target)) {
            closeDropdown();
        }
    }

    toggle.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (dropdown.classList.contains('language-dropdown--open')) {
            closeDropdown();
        } else {
            openDropdown();
        }
    });

    dropdown.addEventListener('click', function (e) {
        var option = e.target.closest('.cplang-option');
        if (option) {
            e.preventDefault();
            e.stopPropagation();
            var locale = option.getAttribute('aria-label');
            if (!locale) return;
            var lang = localeToLang(locale);
            doLanguageSwitch(lang);
            closeDropdown();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && dropdown.classList.contains('language-dropdown--open')) {
            closeDropdown();
            toggle.focus();
        }
    });
}

function buildSelectOptionsHTML(activeLocale) {
    var html = '';
    for (var i = 0; i < LANGUAGES.length; i++) {
        var l = LANGUAGES[i];
        var selected = l.locale === activeLocale ? ' selected' : '';
        html += '<option value="' + localeToLang(l.locale) + '"' + selected + '>' + localeToLang(l.locale).toUpperCase() + '</option>';
    }
    return html;
}

function populatePanelSelects() {
    var savedLang = getSavedLang();
    var activeData = findLangData(savedLang);
    var selects = document.querySelectorAll('#panel-lang-select, #configLanguage, select[data-cp-lang-select]');
    selects.forEach(function (select) {
        if (select.value !== localeToLang(activeData.locale)) {
            select.value = localeToLang(activeData.locale);
        }
        if (!select.dataset.cpLangListener) {
            select.addEventListener('change', function () {
                doLanguageSwitch(this.value);
            });
            select.dataset.cpLangListener = '1';
        }
    });
}

function populateHeaderDropdown() {
    var headerContainer = document.getElementById('cplang-header');
    if (!headerContainer) return;
    var optionsContainer = headerContainer.querySelector('.language-dropdown__options');
    if (!optionsContainer) return;
    if (optionsContainer.children.length > 0) return;

    var savedLang = getSavedLang();
    var activeData = findLangData(savedLang);
    optionsContainer.innerHTML = buildDropdownOptionsHTML(activeData.locale);

    var toggle = headerContainer.querySelector('.language-dropdown__toggle');
    if (toggle) {
        toggle.innerHTML = buildDropdownToggleHTML(activeData.locale);
        toggle.setAttribute('aria-label', activeData.locale);
    }

    setupLangDropdown(headerContainer);
    populatePanelSelects();
}

function setupHamburgerMenu() {
    console.log('[CoffeePie] Setting up hamburger menu...');
    try {
        if (!document.getElementById('custom-hamburger-style')) {
            var style = document.createElement('style');
            style.id = 'custom-hamburger-style';
            style.textContent = '[data-hook="hamburger-overlay-root"],[data-part="hamburger-overlay"],.avoui-hamburger-overlay,.avoui-hamburger-menu-container,[data-semantic-classname="hamburger-overlay"]{display:none!important;opacity:0!important;visibility:hidden!important;pointer-events:none!important}';
            document.head.appendChild(style);
        }

        var existingMenu = document.getElementById('custom-hamburger-menu');
        if (existingMenu) existingMenu.remove();

        var savedLang = getSavedLang();
        var activeData = findLangData(savedLang);
        var optionsHTML = buildDropdownOptionsHTML(activeData.locale);
        var toggleHTML = buildDropdownToggleHTML(activeData.locale);

        var menuHtml = '<div id="custom-hamburger-menu" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background-color:#5f6360;z-index:999999999;overflow-y:auto;">';
        menuHtml += '<div style="position:relative;width:100%;min-height:100%;box-sizing:border-box;font-family:Inter,Helvetica,Arial,sans-serif;display:flex;flex-direction:column;align-items:center;padding-top:80px;padding-bottom:40px;">';
        menuHtml += '<button id="close-hamburger-menu" style="position:absolute;top:30px;right:35px;background:transparent;border:none;cursor:pointer;color:white;padding:0;z-index:10;">';
        menuHtml += '<svg style="width:32px;height:32px;" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">';
        menuHtml += '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>';
        menuHtml += '<div id="cplang-hamburger" style="padding:0 20px 24px 20px;">';
        menuHtml += '<div class="language-dropdown">';
        menuHtml += '<button aria-label="' + activeData.locale + '" aria-current="true" class="cplang-active language-dropdown__toggle" type="button">';
        menuHtml += toggleHTML + '</button>';
        menuHtml += '<div class="language-dropdown__options" role="listbox">' + optionsHTML + '</div>';
        menuHtml += '</div></div>';
        menuHtml += '<div style="display:flex;flex-direction:column;align-items:center;gap:35px;">';
        menuHtml += '<a href="/" style="color:white;text-decoration:none;font-size:26px;font-weight:400;letter-spacing:0.5px;">INICIO</a>';
        menuHtml += '<a href="/precios" style="color:white;text-decoration:none;font-size:26px;font-weight:400;letter-spacing:0.5px;">PRECIOS</a>';
        menuHtml += '<a href="/tienda" style="color:white;text-decoration:none;font-size:26px;font-weight:400;letter-spacing:0.5px;">TIENDA</a>';
        menuHtml += '<a href="/tutoriales" style="color:white;text-decoration:none;font-size:26px;font-weight:400;letter-spacing:0.5px;">TUTORIALES</a>';
        menuHtml += '<a href="/acerca-de" style="color:white;text-decoration:none;font-size:26px;font-weight:400;letter-spacing:0.5px;">ACERCA DE</a>';
        menuHtml += '<a href="/api" style="color:white;text-decoration:none;font-size:26px;font-weight:400;letter-spacing:0.5px;">API/MCP</a>';
        menuHtml += '</div>';
        menuHtml += '<a href="/panel" style="display:inline-flex;align-items:center;gap:7px;color:white;text-decoration:none;font-size:14px;font-weight:600;margin-top:25px;padding:8px 22px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.35);border-radius:20px;letter-spacing:0.3px;">';
        menuHtml += '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
        menuHtml += '<span>Panel de Usuario</span></a>';
        menuHtml += '</div></div>';

        var div = document.createElement('div');
        div.innerHTML = menuHtml;
        document.body.appendChild(div.firstElementChild);

        var hamburgerLang = document.getElementById('cplang-hamburger');
        if (hamburgerLang) {
            setupLangDropdown(hamburgerLang);
        }

        console.log('[CoffeePie] Custom menu HTML injected');
    } catch (err) {
        console.error('[CoffeePie] setupHamburgerMenu error:', err);
    }
}

function handleHamburgerClick(e) {
    var isHamburger = e.target.closest('.avoui-hamburger-open-button') || e.target.closest('[data-semantic-classname="hamburger-open-button"]');
    if (isHamburger) {
        console.log('[CoffeePie] Hamburger button clicked');
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        var modal = document.getElementById('custom-hamburger-menu');
        if (modal) {
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
        return;
    }

    var isClose = e.target.closest('#close-hamburger-menu') || e.target.closest('#custom-hamburger-menu a');
    if (isClose) {
        console.log('[CoffeePie] Close button/link clicked');
        if (e.target.closest('#close-hamburger-menu')) e.preventDefault();
        e.stopPropagation();
        var modal = document.getElementById('custom-hamburger-menu');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }
}

function initSiteFixes() {
    console.log('[CoffeePie] Initializing site fixes...');
    setupHamburgerMenu();
    document.addEventListener('click', handleHamburgerClick, true);
    populateHeaderDropdown();
    populatePanelSelects();

    var savedLang = getSavedLang();
    if (savedLang && savedLang !== 'es') {
        doLanguageSwitch(savedLang);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSiteFixes);
} else {
    initSiteFixes();
}
console.log('[CoffeePie] translate.js script parsed');
