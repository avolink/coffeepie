/**
 * Coffee Pie - Vanilla JS Product Gallery
 * Replaces Avo Pro Gallery with clean vanilla rendering
 */
(function() {
    'use strict';

    if (!window.location.pathname.includes('tienda')) return;

    var GALLERY_ID = 'coffeepie-vanilla-gallery';
    var DATA_URL = '/data/productos.json';
    var LOADED = false;
    var allProducts = [];
    var currentFilter = 'todos';
    var currentSort = 'default';

    // ---- Translation helper ----
    function t(text) {
        var lang = window.CoffeePieLang;
        if (!lang || !lang.translate) return text;
        var translated = lang.translate(text, lang.get());
        return translated || text;
    }

    var FILTERS = [
        { key: 'todos',          label: 'Todos' },
        { key: 'commanders',     label: 'Codec Terminal' },
        { key: 'teclas-suiches', label: 'Teclas y Suiches' },
        { key: 'expansion',      label: 'Tarjetas Expansión' },
        { key: 'adaptadores',    label: 'Adaptadores' },
        { key: 'modulos',        label: 'Módulos' },
        { key: 'accesorios',     label: 'Accesorios' }
    ];

    var SORTS = [
        { key: 'default',     label: 'Destacados' },
        { key: 'price-asc',   label: 'Menor precio' },
        { key: 'price-desc',  label: 'Mayor precio' }
    ];

    function parsePriceNum(priceStr) {
        if (!priceStr) return 0;
        var clean = priceStr.replace(/[$\s.]/g, '').replace(',', '.');
        return parseFloat(clean) || 0;
    }

    function init() {
        if (LOADED) return;
        var avoGallery = document.querySelector('[data-hook="product-list"]');
        if (!avoGallery) { setTimeout(init, 300); return; }

        var avoSection = avoGallery.closest('section');
        if (avoSection) avoSection.style.display = 'none';

        var parent = avoSection ? avoSection.parentElement : avoGallery.parentElement;
        if (!parent) return;
        if (document.getElementById(GALLERY_ID)) return;
        LOADED = true;

        var gallery = document.createElement('div');
        gallery.id = GALLERY_ID;
        gallery.innerHTML = '<div class="vg-loading">' + t('Cargando productos...') + '</div>';
        parent.appendChild(gallery);

        fetch(DATA_URL)
            .then(function(r) { return r.json(); })
            .then(function(products) {
                allProducts = products;
                renderFilterBar();
                renderGrid(getFilteredProducts());
            })
            .catch(function(err) {
                console.error('[VanillaGallery] Failed:', err);
                gallery.innerHTML = '<div class="vg-error">' + t('Error al cargar productos.') + ' <a href="/tienda">' + t('Recargar') + '</a></div>';
            });
    }

    function getFilteredProducts() {
        var filtered = currentFilter === 'todos' 
            ? allProducts.slice() 
            : allProducts.filter(function(p) { return p.category === currentFilter; });

        if (currentSort === 'price-asc') {
            filtered.sort(function(a, b) { return parsePriceNum(a.price) - parsePriceNum(b.price); });
        } else if (currentSort === 'price-desc') {
            filtered.sort(function(a, b) { return parsePriceNum(b.price) - parsePriceNum(a.price); });
        }
        return filtered;
    }

    function renderFilterBar() {
        var gallery = document.getElementById(GALLERY_ID);
        if (!gallery) return;

        var filterBtns = FILTERS.map(function(f) {
            var active = f.key === currentFilter ? ' vg-filter-active' : '';
            return '<button class="vg-filter-btn' + active + '" data-filter="' + f.key + '">' + t(f.label) + '</button>';
        }).join('');

        var sortOpts = SORTS.map(function(s) {
            var sel = s.key === currentSort ? ' selected' : '';
            return '<option value="' + s.key + '"' + sel + '>' + t(s.label) + '</option>';
        }).join('');

        gallery.innerHTML = 
            '<h1 class="vg-title">' + t('Tienda') + '</h1>' +
            '<div class="vg-toolbar">' +
                '<div class="vg-filters">' + filterBtns + '</div>' +
                '<select class="vg-sort">' + sortOpts + '</select>' +
            '</div>' +
            '<div class="vg-grid"></div>' +
            '<div class="vg-count"></div>';

        // Bind filter clicks
        gallery.querySelectorAll('.vg-filter-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                currentFilter = btn.getAttribute('data-filter');
                refreshGrid();
            });
        });

        // Bind sort change
        var sortSelect = gallery.querySelector('.vg-sort');
        if (sortSelect) {
            sortSelect.addEventListener('change', function() {
                currentSort = sortSelect.value;
                refreshGrid();
            });
        }
    }

    function refreshGrid() {
        var products = getFilteredProducts();
        renderFilterBar(); // re-render to update active states and translations
        renderGrid(products);
    }

    function renderGrid(products) {
        var grid = document.querySelector('#' + GALLERY_ID + ' .vg-grid');
        var count = document.querySelector('#' + GALLERY_ID + ' .vg-count');
        if (!grid) return;

        if (!products.length) {
            grid.innerHTML = '<div class="vg-empty">' + t('No se encontraron productos.') + '</div>';
            if (count) count.textContent = '';
            return;
        }

        var html = '';
        products.forEach(function(p) {
            var imgSrc = p.image || '/assets/avo/media/557674_3c3a2d29a9434c33a754d6cac7b98b98.png';
            html += '<div class="vg-card">' +
                '<a href="' + p.url + '" class="vg-card-link">' +
                    '<div class="vg-image-wrap">' +
                        '<img src="' + imgSrc + '" alt="' + p.name + '" class="vg-image" loading="lazy" onerror="this.src=\'/assets/avo/media/557674_3c3a2d29a9434c33a754d6cac7b98b98.png\'">' +
                    '</div>' +
                    '<div class="vg-info">' +
                        '<h3 class="vg-name">' + p.name + '</h3>' +
                        '<span class="vg-price">' + p.price + '</span>' +
                    '</div>' +
                '</a>' +
                '<button class="vg-add-btn" data-name="' + p.name + '" data-price="' + p.price + '" data-image="' + imgSrc + '" data-url="' + p.url + '">' + t('Agregar al carrito') + '</button>' +
            '</div>';
        });

        grid.innerHTML = html;
        if (count) count.textContent = products.length + ' producto' + (products.length !== 1 ? 's' : '');

        bindCartButtons();
    }

    function bindCartButtons() {
        document.querySelectorAll('#' + GALLERY_ID + ' .vg-add-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var name = btn.getAttribute('data-name');
                var price = btn.getAttribute('data-price');
                var image = btn.getAttribute('data-image');
                var url = btn.getAttribute('data-url');

                if (typeof getCart === 'function' && typeof saveCart === 'function') {
                    var cart = getCart();
                    var existing = cart.find(function(i) { return i.name === name; });
                    if (existing) { existing.quantity++; }
                    else { cart.push({ name: name, price: price, image: image, url: url.replace('/productos/', ''), quantity: 1 }); }
                    saveCart(cart);
                    btn.textContent = t('✓ Agregado');
                    btn.classList.add('vg-added');
                    setTimeout(function() {
                        btn.textContent = t('Agregar al carrito');
                        btn.classList.remove('vg-added');
                    }, 1500);
                }
            });
        });
    }

    // Listen for language changes to re-render filter bar
    window.addEventListener('cplangchange', function() {
        var gallery = document.getElementById(GALLERY_ID);
        if (gallery && gallery.querySelector('.vg-filters')) {
            refreshGrid();
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(init, 500); });
    } else {
        setTimeout(init, 500);
    }
    window.addEventListener('load', function() { setTimeout(init, 1000); });
})();
