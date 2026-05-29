/**
 * Coffee Pie - Vanilla JS Product Gallery
 * Replaces Wix Pro Gallery with clean vanilla rendering
 */
(function() {
    'use strict';

    // Only run on tienda page
    if (!window.location.pathname.includes('tienda')) return;

    var GALLERY_ID = 'coffeepie-vanilla-gallery';
    var DATA_URL = '/data/productos.json';
    var LOADED = false;

    function init() {
        if (LOADED) return;
        
        // Find the Wix gallery section
        var wixGallery = document.querySelector('[data-hook="product-list"]');
        if (!wixGallery) {
            // Retry if Wix hasn't rendered yet
            setTimeout(init, 300);
            return;
        }

        // Hide Wix gallery
        var wixSection = wixGallery.closest('section');
        if (wixSection) {
            wixSection.style.display = 'none';
        }

        // Find insertion point - parent of the hidden section
        var parent = wixSection ? wixSection.parentElement : wixGallery.parentElement;
        if (!parent) return;

        // Check if gallery already exists
        if (document.getElementById(GALLERY_ID)) return;
        LOADED = true;

        // Create gallery container
        var gallery = document.createElement('div');
        gallery.id = GALLERY_ID;
        gallery.innerHTML = '<div class="vg-loading">Cargando productos...</div>';
        parent.appendChild(gallery);

        // Load product data
        fetch(DATA_URL)
            .then(function(r) { return r.json(); })
            .then(renderGallery)
            .catch(function(err) {
                console.error('[VanillaGallery] Failed to load products:', err);
                gallery.innerHTML = '<div class="vg-error">Error al cargar productos. <a href="/tienda">Recargar</a></div>';
            });
    }

    function renderGallery(products) {
        var gallery = document.getElementById(GALLERY_ID);
        if (!gallery) return;

        if (!products || !products.length) {
            gallery.innerHTML = '<div class="vg-empty">No hay productos disponibles.</div>';
            return;
        }

        var html = '<h1 class="vg-title">Tienda</h1><div class="vg-grid">';
        
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
                '<button class="vg-add-btn" data-name="' + p.name + '" data-price="' + p.price + '" data-image="' + imgSrc + '" data-url="' + p.url + '">Agregar al carrito</button>' +
            '</div>';
        });

        html += '</div>';
        gallery.innerHTML = html;

        // Bind add-to-cart buttons
        bindCartButtons();
    }

    function bindCartButtons() {
        var buttons = document.querySelectorAll('#' + GALLERY_ID + ' .vg-add-btn');
        buttons.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                var name = btn.getAttribute('data-name');
                var price = btn.getAttribute('data-price');
                var image = btn.getAttribute('data-image');
                var url = btn.getAttribute('data-url');

                // Use existing cart.js if available
                if (typeof getCart === 'function' && typeof saveCart === 'function') {
                    var cart = getCart();
                    var existing = cart.find(function(i) { return i.name === name; });
                    if (existing) {
                        existing.quantity++;
                    } else {
                        cart.push({
                            name: name,
                            price: price,
                            image: image,
                            url: url.replace('/productos/', ''),
                            quantity: 1
                        });
                    }
                    saveCart(cart);
                    
                    // Visual feedback
                    btn.textContent = '✓ Agregado';
                    btn.classList.add('vg-added');
                    setTimeout(function() {
                        btn.textContent = 'Agregar al carrito';
                        btn.classList.remove('vg-added');
                    }, 1500);
                }
            });
        });
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(init, 500); });
    } else {
        setTimeout(init, 500);
    }
    
    // Also try on load for slow Wix render
    window.addEventListener('load', function() { setTimeout(init, 1000); });
})();
