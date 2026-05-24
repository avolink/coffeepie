
/**
 * Project Coffee Pie - Cart Functionality
 */

const CART_STORAGE_KEY = 'coffee_pie_cart';

function getCart() {
    try {
        const cartStr = localStorage.getItem(CART_STORAGE_KEY);
        console.log('[Cart] Raw storage:', cartStr);
        return cartStr ? JSON.parse(cartStr) : [];
    } catch (e) {
        console.error('Cart read error:', e);
        return [];
    }
}

function saveCart(cart) {
    console.log('[Cart] Saving:', cart);
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
    updateCartUI();
    if (window.location.pathname.includes('carrito') || window.location.pathname.includes('cart')) {
        renderCartPage();
    }
}

function parsePrice(priceStr) {
    if (!priceStr) return 0;
    try {
        // Surgical cleaning for $1.200.000,00
        let clean = priceStr.toString().replace(/[$\s]/g, '');

        // If it has both . and , assume . is thousands and , is decimal
        if (clean.includes('.') && clean.includes(',')) {
            clean = clean.split('.').join('').replace(',', '.');
        } else if (clean.includes(',')) {
            // Check if it looks like a thousand separator (3 digits after)
            const parts = clean.split(',');
            if (parts[parts.length - 1].length === 3) {
                clean = clean.split(',').join('');
            } else {
                clean = clean.replace(',', '.');
            }
        } else if (clean.includes('.')) {
            // Check if it looks like thousand separator
            const parts = clean.split('.');
            if (parts[parts.length - 1].length === 3) {
                clean = clean.split('.').join('');
            }
        }

        const num = parseFloat(clean.replace(/[^0-9.]/g, ''));
        console.log(`[Cart] Parsed "${priceStr}" -> ${num}`);
        return isNaN(num) ? 0 : num;
    } catch (e) {
        return 0;
    }
}

function updateCartUI() {
    const cart = getCart();
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

    const squarishCartPaths = `
        <path d="M197.9 55.9L169.9 127.4 64.5 127.4 27.6 29.8 0 29.8 0.2 16.7 36.5 16.7 73.4 114.3 160.9 114.3 183 55.9"></path>
        <circle cx="143.8" cy="153" r="13"></circle>
        <circle cx="90.8" cy="153" r="13"></circle>
    `;

    document.querySelectorAll('a[href*="carrito"], a[href*="cart-page"], [data-hook="cart-icon-button"]').forEach(link => {
        link.setAttribute('aria-label', `Carrito con ${totalItems} ítems`);
        
        // Ensure the SVG uses the squarish paths
        const svg = link.querySelector('svg');
        if (svg) {
            // Keep the text (badge) if it exists, replace paths
            const badge = svg.querySelector('text[data-hook="items-count"]');
            const currentBadgeText = badge ? badge.textContent : totalItems;
            
            svg.innerHTML = `
                ${squarishCartPaths}
                <text data-hook="items-count" class="uxskpx M846Y_" text-anchor="middle" x="116" y="35" dy=".48em">${totalItems}</text>
            `;
        }

        const badge = link.querySelector('span, text[data-hook="items-count"]');
        if (badge) badge.textContent = totalItems;
    });
    if (window.CoffeePieLang && typeof window.CoffeePieLang.refresh === 'function') {
        window.CoffeePieLang.refresh();
    }
}

function initCartPage() {
    if (window.location.pathname.includes('carrito') || window.location.pathname.includes('cart')) {
        let attempts = 0;
        const tryRender = () => {
            const hook = document.querySelector('[data-hook="CartAppDataHook.root"]');
            if (hook) {
                renderCartPage();
            } else if (attempts < 15) {
                attempts++;
                setTimeout(tryRender, 200);
            } else {
                renderCartPage(); // fallback
            }
        };
        tryRender();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('a[href*="cart-page"]').forEach(l => l.href = '/carrito.html');
    updateCartUI();
    initCartPage();
});

function renderCartPage() {
    const cart = getCart();
    console.log('[Cart] Rendering page with', cart.length, 'items');

    let container = document.getElementById('custom-cart-root');
    if (!container) {
        // Check specifically for Avo Cart Container
        const selectors = ['[data-hook="CartAppDataHook.root"]', '#PAGES_CONTAINER', '[data-main-content-parent="true"]', 'main', '#site-root > div'];
        let bestTarget = null;
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetWidth > 100 && !['BODY', 'HTML'].includes(el.tagName)) {
                bestTarget = el;
                break;
            }
        }

        if (bestTarget) {
            console.log('[Cart] Hijacking target:', bestTarget.tagName, bestTarget.id || bestTarget.className);
            // Hide all existing children so the sample product goes away
            let hideChildren = true;
            if (bestTarget.dataset.hook === 'CartAppDataHook.root') {
                // if we hit the cart container directly, it's safer to just hide its children
                bestTarget.style.display = 'block';
            }

            Array.from(bestTarget.children).forEach(child => {
                if (child.tagName !== 'SCRIPT' && child.tagName !== 'STYLE' && child.id !== 'custom-cart-root') {
                    child.style.setProperty('display', 'none', 'important');
                }
            });
            const root = document.createElement('div');
            root.id = 'custom-cart-root';
            bestTarget.prepend(root);
            container = root;
        } else {
            console.log('[Cart] No target found, using fixed overlay');
            const wrap = document.createElement('div');
            wrap.id = 'custom-cart-root';
            wrap.style.cssText = 'position:relative; max-width:1000px; margin:150px auto; background:#111; color:white; padding:40px; border-radius:12px; z-index:9999; box-shadow:0 0 100px rgba(0,0,0,0.8);';
            document.body.appendChild(wrap);
            container = wrap;
        }
    }

    if (!container) return;

    if (cart.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:100px 20px; font-family: Arial, Helvetica, sans-serif; background:#fff; min-height: 60vh;">
                <h2 style="font-size:2rem; color:#000; font-weight:400;">Mi carrito</h2>
                <p style="margin:20px 0; color:#666; font-size:1.1rem;">Tu carrito está vacío.</p>
                <a href="/tienda" style="display:inline-block; padding: 12px 30px; background:#000; color:#fff; text-decoration:none; border-radius:30px; margin-top: 20px;">Sigue comprando</a>
            </div>
        `;
        return;
    }

    let itemsHtml = '';
    let total = 0;

    cart.forEach((item, index) => {
        const p = parsePrice(item.price);
        total += p * item.quantity;
        
        let productUrl = '/tienda.html';
        
        // First try URL-based matching
        if (item.url && item.url !== 'tienda' && item.url !== 'tienda.html') {
            if (item.url.startsWith('http://') || item.url.startsWith('https://')) {
                productUrl = item.url;
            } else if (item.url.startsWith('/')) {
                productUrl = item.url;
            } else if (item.url.startsWith('productos/')) {
                productUrl = '/' + item.url;
            } else if (item.url.includes('/')) {
                productUrl = '/' + item.url;
            } else {
                productUrl = '/productos/' + item.url;
            }
        } 
        // Then try name-based matching as fallback
        else if (item.name) {
            const nameLower = item.name.toLowerCase();
            if (nameLower.includes('commander') && nameLower.includes('basic')) {
                productUrl = '/productos/terminal-codec-commander-basic-by-coffee-pie';
            } else if (nameLower.includes('commander') && nameLower.includes('core')) {
                productUrl = '/productos/terminal-codec-commander-core-by-coffee-pie';
            } else if (nameLower.includes('commander') && nameLower.includes('pro')) {
                productUrl = '/productos/terminal-codec-commander-pro-by-coffee-pie';
            } else if (nameLower.includes('framework') && nameLower.includes('usb-c')) {
                productUrl = '/productos/usb-c-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('usb-a')) {
                productUrl = '/productos/usb-a-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('hdmi')) {
                productUrl = '/productos/hdmi-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('displayport')) {
                productUrl = '/productos/displayport-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('audio')) {
                productUrl = '/productos/audio-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('sd')) {
                productUrl = '/productos/sd-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('microsd')) {
                productUrl = '/productos/micro-sd-expansion-card-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('storage') && nameLower.includes('1tb')) {
                productUrl = '/productos/storage-expansion-card-1tb-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('storage') && nameLower.includes('250')) {
                productUrl = '/productos/storage-expansion-card-250gb-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('touchpad')) {
                productUrl = '/productos/touchpad-module-by-framework';
            } else if (nameLower.includes('framework') && nameLower.includes('numpad')) {
                productUrl = '/productos/numpad-module-for-commander-by-framework';
            } else if (nameLower.includes('tp-link') && nameLower.includes('wifi')) {
                productUrl = '/productos/wifi-adapter-by-tp-link';
            } else if (nameLower.includes('tp-link') && nameLower.includes('ethernet')) {
                productUrl = '/productos/ethernet-rj45-adapter-by-tp-link';
            } else if (nameLower.includes('ugreen') && nameLower.includes('wifi') && nameLower.includes('bluetooth')) {
                productUrl = '/productos/wifi-and-bluetooth-adapter-by-ugreen';
            } else if (nameLower.includes('lofree')) {
                productUrl = '/productos/custom-keycaps-set-for-commander-by-lofree';
            } else if (nameLower.includes('womier')) {
                productUrl = '/productos/custom-keycaps-set-for-commander-by-womier';
            } else if (nameLower.includes('cherry') && nameLower.includes('stabilizers')) {
                productUrl = '/productos/low-profile-stabilizers-set-for-commander-by-cherry';
            } else if (nameLower.includes('keycaps') && nameLower.includes('low')) {
                productUrl = '/productos/low-profile-keycaps-set-for-commander';
            } else if (nameLower.includes('powerowl')) {
                productUrl = '/productos/hot-swappable-battery-for-commander-by-powerowl';
            } else if (nameLower.includes('keychron')) {
                productUrl = '/productos/optomechanical-switches-for-commander-by-keychron';
            } else if (nameLower.includes('razer')) {
                productUrl = '/productos/optomechanical-switches-for-commander-by-razer';
            } else if (nameLower.includes('xicom')) {
                productUrl = '/productos/rj45-to-sfp-optical-fiber-converter-by-xicom';
            } else if (nameLower.includes('tpe')) {
                productUrl = '/productos/tpe-optomechanical-switches-by-coffee-pie';
            } else if (nameLower.includes('commander') && nameLower.includes('base')) {
                productUrl = '/productos/commander-base-heatsink';
            } else if (nameLower.includes('commander') && nameLower.includes('cover')) {
                productUrl = '/productos/commander-keyboard-cover';
            } else if (nameLower.includes('commander') && nameLower.includes('back') && nameLower.includes('io')) {
                productUrl = '/productos/commander-back-io-panel';
            } else if (nameLower.includes('commander') && nameLower.includes('keyboard') && nameLower.includes('module')) {
                productUrl = '/productos/commander-keyboard-module-w-micro';
            }
        }
        
        itemsHtml += `
            <div class="cart-item-row">
                <div class="cart-item-info">
                    <a href="${productUrl}"><img src="${item.image}" class="cart-item-image" onerror="this.src='/assets/avo/media/557674_3c3a2d29a9434c33a754d6cac7b98b98.png';"></a>
                    <div class="cart-item-details">
                        <h3 class="cart-item-title"><a href="${productUrl}">${item.name}</a></h3>
                        <p class="cart-item-unit-price">$ ${p.toLocaleString('es-CO')},00</p>
                        <p class="cart-item-variant">${item.variant || 'Selección estándar'}</p>
                    </div>
                </div>
                <div class="cart-item-actions">
                    <div class="cart-item-controls-wrapper">
                        <div class="cart-item-controls">
                            <button type="button" onclick="updateQty(${index}, -1, event)" class="qty-btn">-</button>
                            <input type="number" class="avo-cart-qty-input" value="${item.quantity}" min="1" onchange="setQty(${index}, this.value, event)">
                            <button type="button" onclick="updateQty(${index}, 1, event)" class="qty-btn">+</button>
                        </div>
                        <button type="button" onclick="removeFromCart(${index}, event)" class="cart-item-remove" title="Eliminar ítem">
                            &#10005;
                        </button>
                    </div>
                    <div class="cart-item-price">
                        $ ${(p * item.quantity).toLocaleString('es-CO')},00
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = `
        <style>
        .avo-cart-qty-input::-webkit-outer-spin-button,
        .avo-cart-qty-input::-webkit-inner-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        .cart-page-container {
            max-width: 1100px;
            margin: 40px auto;
            padding: 0 30px;
            font-family: Arial, Helvetica, sans-serif;
            color: #000;
            display: flex;
            gap: 80px;
            background: #fff;
            align-items: flex-start;
        }
        .cart-items-section {
            flex: 1;
        }
        .cart-summary-section {
            width: 380px;
        }
        .cart-item-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #e0e0e0;
            padding: 20px 0;
            gap: 20px;
        }
        .cart-item-info {
            display: flex;
            align-items: center;
            gap: 20px;
            flex: 1;
        }
        .cart-item-image {
            width: 100px;
            height: 100px;
            object-fit: contain;
            border: 1px solid #eee;
        }
        .cart-item-details {
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .cart-item-title {
            margin: 0 0 8px 0;
            font-size: 1.1rem;
            font-weight: 400;
            color: #000;
        }
        .cart-item-title a {
            color: #000;
            text-decoration: none;
        }
        .cart-item-title a:hover {
            text-decoration: underline;
        }
        .cart-item-image {
            width: 100px;
            height: 100px;
            object-fit: contain;
            border: 1px solid #eee;
        }
        .cart-item-info a {
            display: block;
        }
        .cart-item-unit-price {
            margin: 0 0 5px 0;
            font-size: 0.9rem;
            color: #000;
        }
        .cart-item-variant {
            margin: 0;
            font-size: 0.85rem;
            color: #666;
        }
        .cart-item-actions {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .cart-item-controls-wrapper {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .cart-item-controls {
            display: flex;
            align-items: center;
            border: 1px solid #b3b3b3;
            border-radius: 2px;
        }
        .qty-btn {
            background: none;
            border: none;
            padding: 6px 14px;
            cursor: pointer;
            font-size: 1.2rem;
            outline: none;
            color: #333;
        }
        .avo-cart-qty-input {
            width: 40px;
            text-align: center;
            border: none;
            font-size: 1rem;
            outline: none;
            background: transparent;
            -moz-appearance: textfield;
        }
        .cart-item-price {
            min-width: 130px;
            text-align: right;
            font-size: 1rem;
            font-weight: 400;
        }
        .cart-item-remove {
            background: none;
            border: none;
            cursor: pointer;
            color: #999;
            padding: 0 10px;
            font-size: 1.5rem;
        }
        .cart-promo-notes {
            margin-top: 25px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            color: #333;
            font-size: 1rem;
        }
        .promo-note-btn {
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
        }

        /* Responsive Styles */
        @media (max-width: 900px) {
            .cart-page-container {
                flex-direction: column;
                gap: 40px;
                padding: 0 15px;
                margin: 20px auto;
            }
            .cart-items-section, .cart-summary-section {
                width: 100%;
            }
            .cart-item-row {
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }
            .cart-item-info {
                width: 100%;
                align-items: flex-start;
            }
            .cart-item-actions {
                width: 100%;
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }
            .cart-item-controls-wrapper {
                width: 100%;
                justify-content: space-between;
                flex-wrap: nowrap;
            }
            .cart-item-price {
                min-width: unset;
                text-align: right;
                width: 100%;
            }
        }
        </style>
        <div class="cart-page-container">
            
            <div class="cart-items-section">
                <h1 style="font-size:2rem; font-weight:400; margin-bottom:40px;">Mi carrito</h1>
                <div style="border-top:1px solid #e0e0e0;">
                    ${itemsHtml}
                </div>
                
                <div class="cart-promo-notes">
                    <div class="promo-note-btn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>
                        <span>Ingresar código promocional</span>
                    </div>
                    <div class="promo-note-btn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                        <span>Agregar una nota</span>
                    </div>
                </div>
            </div>

            <div class="cart-summary-section">
                <h2 style="font-size:1.5rem; font-weight:400; margin-bottom:35px;">Resumen del pedido</h2>
                
                <div style="border-top:1px solid #e0e0e0; padding-top:25px; margin-bottom:25px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:15px; font-size:1.05rem;">
                        <span>Subtotal</span>
                        <span>$ ${total.toLocaleString('es-CO')},00</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:1.05rem;">
                        <span>Envío</span>
                        <span>GRATIS</span>
                    </div>
                    <div style="margin-bottom:0;">
                        <a href="#" style="color:#000; text-decoration:underline; font-size:1rem;">Antioquia, Colombia</a>
                    </div>
                </div>
                
                <div style="border-top:1px solid #e0e0e0; padding-top:20px; margin-bottom:30px;">
                    <div style="display:flex; justify-content:space-between; font-size:1.4rem; font-weight:400;">
                        <span>Total</span>
                        <span>$ ${total.toLocaleString('es-CO')},00</span>
                    </div>
                </div>
                
                <button onclick="window.location.href='/pago-seguro'" style="width:100%; padding:18px; background:#000; color:#fff; border:none; border-radius:30px; font-size:1.1rem; cursor:pointer; margin-bottom:15px; font-weight:normal; letter-spacing:0.5px;">
                    Pago Seguro
                </button>
                
                <div style="text-align:center; font-size:0.95rem; color:#555; display:flex; justify-content:center; align-items:center; gap:6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                    <span>Pago seguro</span>
                </div>
            </div>
            
        </div>
    `;

    updateAvoTotals(total);
    if (window.CoffeePieLang && typeof window.CoffeePieLang.refresh === 'function') {
        window.CoffeePieLang.refresh();
    }
}

function updateAvoTotals(total) {
    const s = `$ ${total.toLocaleString()},00`;
    document.querySelectorAll('[data-hook*="total"], [data-hook*="subtotal"]').forEach(el => el.innerText = s);
}

window.updateQty = (index, delta, event) => {
    if (event) { event.preventDefault(); event.stopPropagation(); }
    const c = getCart();

    // try to use the current visual input value if available before math
    let currentQty = c[index].quantity;
    if (event && event.currentTarget) {
        const input = event.currentTarget.parentElement.querySelector('input');
        if (input) {
            let val = parseInt(input.value, 10);
            if (!isNaN(val) && val > 0) currentQty = val;
        }
    }

    currentQty += delta;
    if (currentQty <= 0) {
        c.splice(index, 1);
    } else {
        c[index].quantity = currentQty;
    }
    saveCart(c);
};

window.setQty = (index, value, event) => {
    if (event) { event.preventDefault(); event.stopPropagation(); }
    const c = getCart();
    let val = parseInt(value, 10);
    if (isNaN(val) || val <= 0) val = 1;
    c[index].quantity = val;
    saveCart(c);
};

window.removeFromCart = (index, event) => {
    if (event) { event.preventDefault(); event.stopPropagation(); }
    const c = getCart();
    c.splice(index, 1);
    saveCart(c);
};

function showFeedback(name) {
    let t = document.querySelector('.cart-toast');
    if (!t) {
        t = document.createElement('div');
        t.className = 'cart-toast';
        document.body.appendChild(t);
    }
    t.innerText = `${name} agregado`;
    t.style.cssText = 'position:fixed; top:20px; right:20px; background:#c18b44; color:white; padding:20px 40px; border-radius:5px; z-index:999999; font-weight:bold; font-size:1.2rem; box-shadow:0 10px 40px rgba(0,0,0,0.5); pointer-events:none;';
    t.style.display = 'block';
    t.style.opacity = '1';
    setTimeout(() => {
        t.style.transition = 'opacity 0.6s';
        t.style.opacity = '0';
        setTimeout(() => t.style.display = 'none', 600);
    }, 2500);
}

document.addEventListener('click', (e) => {
    const plusBtn = e.target.closest('button[aria-label="Agregar uno"]');
    const minusBtn = e.target.closest('button[aria-label="Eliminar uno"]');
    
    if (plusBtn || minusBtn) {
        e.preventDefault();
        e.stopImmediatePropagation();
        e.stopPropagation();
        
        // Find the quantity input - look in the quantity container
        const qtyContainer = document.querySelector('.avoui-product-quantity-container, [class*="product-quantity"]');
        const quantityInput = qtyContainer?.querySelector('input[type="number"]');
        const minusButton = qtyContainer?.querySelector('button[aria-label="Eliminar uno"]');
        
        if (quantityInput) {
            let currentQty = parseInt(quantityInput.value, 10) || 1;
            
            if (plusBtn) {
                currentQty++;
            } else if (minusBtn && currentQty > 1) {
                currentQty--;
            }
            
            quantityInput.value = currentQty;
            
            // Enable/disable minus button based on quantity
            if (minusButton) {
                minusButton.disabled = currentQty <= 1;
            }
        }
        return;
    }
});

// Function to update minus button state on page load
function initQuantityButtons() {
    const qtyContainer = document.querySelector('.avoui-product-quantity-container, [class*="product-quantity"]');
    if (!qtyContainer) return;
    
    const quantityInput = qtyContainer.querySelector('input[type="number"]');
    const minusButton = qtyContainer.querySelector('button[aria-label="Eliminar uno"]');
    const plusButton = qtyContainer.querySelector('button[aria-label="Agregar uno"]');
    
    if (quantityInput && minusButton) {
        const currentQty = parseInt(quantityInput.value, 10) || 1;
        minusButton.disabled = currentQty <= 1;
        
        // Listen for input changes to keep buttons in sync
        quantityInput.addEventListener('input', () => {
            const qty = parseInt(quantityInput.value, 10) || 1;
            minusButton.disabled = qty <= 1;
        });
    }
}

// Run on DOMContentLoaded and when page is fully loaded
document.addEventListener('DOMContentLoaded', initQuantityButtons);
window.addEventListener('load', initQuantityButtons);

// Ensure quantity input has min=1
document.addEventListener('DOMContentLoaded', () => {
    const quantityInput = document.querySelector('.avoui-product-quantity-container input[type="number"], [class*="product-quantity"] input[type="number"]');
    if (quantityInput) {
        quantityInput.min = '1';
    }
});

document.addEventListener('click', (e) => {
    const btn = e.target.closest('button[aria-label*="Agregar"], button[aria-label*="carrito"], button[aria-label*="Add"], button.sBQRG_k, button[class*="addToCart"], button[data-hook*="add-to-cart"]');
    // Don't trigger for quantity +/- buttons - they are handled separately
    if (btn && (btn.getAttribute('aria-label') === 'Agregar uno' || btn.getAttribute('aria-label') === 'Eliminar uno')) {
        return;
    }
    if (btn) {
        console.log('[Cart] Add to cart button clicked:', btn.getAttribute('aria-label'));
        e.preventDefault();
        e.stopPropagation();

        let container = btn.closest('[data-hook="product-item-root"]');
        if (!container) {
            // Try to find container by looking for quantity controls nearby
            container = btn.closest('[class*="product"]') || btn.closest('.avoui-product-quantity-container')?.parentElement;
        }
        if (!container || container.tagName === 'BODY') {
            container = btn.parentElement;
            while (container && !container.querySelector('.JPDEZd') && !container.querySelector('h1') && container.tagName !== 'BODY') {
                container = container.parentElement;
            }
        }

        console.log('[Cart] Button clicked, container:', container ? container.tagName : 'none');

        // Try multiple selectors for product name
        let nameEl = container?.querySelector('.JPDEZd p');
        if (!nameEl) {
            nameEl = container?.querySelector('h1') || document.querySelector('h1');
        }
        // Fallback: get from JSON-LD schema
        if (!nameEl) {
            const jsonLd = document.querySelector('script[type="application/ld+json"]');
            if (jsonLd) {
                try {
                    const data = JSON.parse(jsonLd.textContent);
                    if (data.name) {
                        nameEl = { innerText: { trim: () => data.name } };
                    }
                } catch (e) {}
            }
        }

        // Try multiple selectors for price
        let priceEl = [...(container?.querySelectorAll('span') || [])].find(s => s.innerText.includes('$'));
        if (!priceEl) {
            priceEl = [...document.querySelectorAll('span')].find(s => s.innerText.includes('$'));
        }
        // Fallback: get from JSON-LD schema
        if (!priceEl) {
            const jsonLd = document.querySelector('script[type="application/ld+json"]');
            if (jsonLd) {
                try {
                    const data = JSON.parse(jsonLd.textContent);
                    const offers = data.Offers || data.offers;
                    if (offers) {
                        const priceValue = offers.price || (Array.isArray(offers) ? offers[0]?.price : null);
                        if (priceValue) {
                            priceEl = { innerText: { trim: () => '$ ' + parseInt(priceValue).toLocaleString('es-CO') + ',00' } };
                        }
                    }
                } catch (e) {}
            }
        }

        if (nameEl && priceEl) {
            let imgSrc = '';
            
            // 1. Try meta og:image (most reliable for product pages)
            const ogImage = document.querySelector('meta[property="og:image"]');
            if (ogImage && ogImage.content && !ogImage.content.toLowerCase().includes('logo')) {
                imgSrc = ogImage.content;
            }
            
            // 2. Fallbacks
            const logoPatterns = ['Logo', 'logo', '3c3a2d29a9434c33a754d6cac7b98b98', '557674_3c3a2d29'];
            if (!imgSrc && container) {
                const productImgSelectors = [
                    container.querySelector('[data-hook="gallery-item-image-img"]'),
                    container.querySelector('wow-image img'),
                    ...Array.from(container.querySelectorAll('img'))
                ].filter(Boolean);

                const bestImg = productImgSelectors.find(img => {
                    const s = img.src || img.getAttribute('src') || '';
                    if (!s || s.includes('data:image') || s.length < 10) return false;
                    return !logoPatterns.some(pattern => s.includes(pattern));
                });
                if (bestImg) imgSrc = bestImg.src || bestImg.getAttribute('src');
            }
            
            // 3. Fallback: look for product image anywhere on page
            if (!imgSrc) {
                const allImages = Array.from(document.querySelectorAll('img'));
                const bestImg = allImages.find(img => {
                    const s = img.src || img.getAttribute('src') || '';
                    if (!s || s.includes('data:image') || s.length < 10) return false;
                    return !logoPatterns.some(pattern => s.includes(pattern));
                });
                if (bestImg) imgSrc = bestImg.src || bestImg.getAttribute('src');
            }

            let pageUrl = window.location.pathname.replace(/^\//, '').replace(/\.html$/, '');
            
            // Try to get URL from canonical link as backup
            const canonicalLink = document.querySelector('link[rel="canonical"]');
            if (canonicalLink) {
                const canonicalHref = canonicalLink.getAttribute('href');
                if (canonicalHref) {
                    try {
                        const urlObj = new URL(canonicalHref);
                        pageUrl = urlObj.pathname.replace(/^\//, '').replace(/\.html$/, '');
                    } catch (e) {
                        pageUrl = canonicalHref.replace(/^\//, '').replace(/\.html$/, '');
                    }
                }
            }
            
            // Try data attributes on container
            if (!pageUrl || pageUrl === 'tienda') {
                const productLink = container?.querySelector('a[data-hook="product-link"], a[class*="product"], a[href*="productos"]');
                if (productLink) {
                    const href = productLink.getAttribute('href');
                    if (href) {
                        try {
                            const urlObj = new URL(href, window.location.origin);
                            pageUrl = urlObj.pathname.replace(/^\//, '').replace(/\.html$/, '');
                        } catch (e) {
                            pageUrl = href.replace(/^\//, '').replace(/\.html$/, '');
                        }
                    }
                }
            }
            
            // Try data-slug attribute
            if (!pageUrl || pageUrl === 'tienda') {
                const slug = container?.getAttribute('data-slug');
                if (slug) {
                    pageUrl = 'productos/' + slug;
                }
            }
            
            console.log('[Cart] Captured URL for product:', pageUrl);
            
            let selectedVariant = "Selección estándar";
            let finalPrice = priceEl.innerText.trim();
            const currentRadio = document.querySelector('input[type="radio"][data-hook="selectable-container-input"]:checked');
            if (currentRadio) {
                selectedVariant = currentRadio.getAttribute('aria-label') || "Selección estándar";
                
                // Get the wrapper of the selected radio to find its specific price
                const wrapper = currentRadio.closest('[class*="SelectableContainercomponent"][class*="__wrapper"]') || currentRadio.closest('[class*="SelectableContainercomponent"]') || currentRadio.parentElement.parentElement;
                
                // Find the price inside this wrapper
                if (wrapper) {
                    const variantPriceEl = [...wrapper.querySelectorAll('span, p, div')].find(s => s.innerText && s.innerText.includes('$'));
                    if (variantPriceEl) {
                        finalPrice = variantPriceEl.innerText.trim();
                    }
                }
            }
            const prod = {
                name: nameEl.innerText.trim(),
                price: finalPrice,
                image: imgSrc,
                url: pageUrl || 'tienda',
                variant: selectedVariant
            };
            
            // Find quantity input - look in the quantity container on the page
            let quantityInput = document.querySelector('.avoui-product-quantity-container input[type="number"], [class*="product-quantity"] input[type="number"]');
            if (!quantityInput) {
                // Try to find any visible number input that's related to product quantity
                const allInputs = document.querySelectorAll('input[type="number"]');
                for (const input of allInputs) {
                    if (input.offsetParent !== null && input.min === '1') {
                        quantityInput = input;
                        break;
                    }
                }
            }
            
            let qtyToAdd = 1;
            if (quantityInput) {
                qtyToAdd = parseInt(quantityInput.value, 10) || 1;
                console.log('[Cart] Quantity input found, value:', qtyToAdd);
            } else {
                console.log('[Cart] Quantity input NOT found, defaulting to 1');
            }
            
            console.log('[Cart] Adding product with URL:', prod.url, 'quantity:', qtyToAdd);
            const cart = getCart();
            const ex = cart.find(i => i.name === prod.name && (i.variant || 'Selección estándar') === (prod.variant || 'Selección estándar'));
            if (ex) ex.quantity += qtyToAdd; else cart.push({ ...prod, quantity: qtyToAdd });
            saveCart(cart);
            showFeedback(prod.name);
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('a[href*="cart-page"]').forEach(l => l.href = '/carrito.html');
    updateCartUI();
});

function initProductSelectors() {
    const radioInputs = document.querySelectorAll('input[type="radio"][data-hook="selectable-container-input"]');
    if (radioInputs.length === 0) return;

    let defaultSelected = false;
    
    radioInputs.forEach(input => {
        // Enclosure recuadro: increase clickable area to the entire box
        const wrapper = input.closest('[class*="SelectableContainercomponent"][class*="__wrapper"]') || input.closest('[class*="SelectableContainercomponent"]') || input.parentElement.parentElement || input.parentElement;
        const customCircle = wrapper.querySelector('.avoui-selectable-container-input__custom-input') || wrapper.querySelector('span[class*="customInput"]');
        
        // Add cursor pointer to wrapper so it looks clickable
        if (wrapper && wrapper.style) {
            wrapper.style.cursor = 'pointer';
        }

        if (customCircle && !document.getElementById('custom-radio-styles')) {
            const style = document.createElement('style');
            style.id = 'custom-radio-styles';
            style.textContent = `
                .avoui-selectable-container-input__custom-input {
                    position: relative;
                }
                .avoui-selectable-container-input__custom-input.is-selected::after {
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    width: 8px;
                    height: 8px;
                    background-color: black;
                    border-radius: 50%;
                }
            `;
            document.head.appendChild(style);
        }

        const handleSelect = (e) => {
            radioInputs.forEach(otherInput => {
                otherInput.checked = false;
                const otherWrapper = otherInput.closest('[class*="SelectableContainercomponent"][class*="__wrapper"]') || otherInput.closest('[class*="SelectableContainercomponent"]') || otherInput.parentElement.parentElement || otherInput.parentElement;
                const otherCircle = otherWrapper?.querySelector('.avoui-selectable-container-input__custom-input') || otherWrapper?.querySelector('span[class*="customInput"]');
                if (otherCircle) {
                    otherCircle.classList.remove('is-selected');
                }
            });
            input.checked = true;
            if (customCircle) {
                customCircle.classList.add('is-selected');
            }
        };

        wrapper.addEventListener('click', handleSelect);
        
        if (input.getAttribute('aria-label') === 'Deposito reembolsable' && !defaultSelected) {
            handleSelect();
            defaultSelected = true;
        }
    });
    
    if (!defaultSelected && radioInputs.length > 0) {
        radioInputs[0].checked = true;
        const fallbackCircle = (radioInputs[0].closest('.SelectableContainerInputcomponent1622204446__root') || radioInputs[0].parentElement).querySelector('span[class*="customInput"]');
        if (fallbackCircle) fallbackCircle.classList.add('is-selected');
    }
}

document.addEventListener('DOMContentLoaded', initProductSelectors);
window.addEventListener('load', initProductSelectors);

/**
 * ============================================================
 * Product Accordion / Collapsible Sections
 * ============================================================
 * Handles expand/collapse for "Información del Producto",
 * "Dimensiones", etc. on product pages.
 *
 * Avo DOM structure (per repeater item):
 *   [role="listitem"]
 *     ├── .inner-box (decorative)
 *     ├── .has-click-trigger  (clickable header)
 *     │     ├── inner-box
 *     │     ├── [data-testid="richTextElement"] → h2 title
 *     │     ├── [data-semantic-classname="button"] → minus SVG
 *     │     └── [data-semantic-classname="button"] → plus SVG
 *     ├── [data-testid="richTextElement"] (content text)
 *     └── hidden placeholder divs
 */
function initProductAccordions() {
    var triggers = document.querySelectorAll('.has-click-trigger');
    if (triggers.length === 0) return;

    console.log('[Accordion] Found', triggers.length, 'trigger(s)');

    triggers.forEach(function (trigger, idx) {
        // Find the two button containers inside the trigger
        var buttons = trigger.querySelectorAll('[data-semantic-classname="button"]');

        if (buttons.length < 2) {
            console.warn('[Accordion] Trigger', idx, '- need 2 buttons, found', buttons.length);
            return;
        }

        var minusBtnContainer = buttons[0];
        var plusBtnContainer = buttons[1];

        var titleEl = trigger.querySelector('h2');
        var title = titleEl ? titleEl.textContent.trim() : '(section ' + idx + ')';

        // Find content in the parent listitem
        var listItem = trigger.closest('[role="listitem"]');
        if (!listItem) {
            console.warn('[Accordion] No listitem parent for:', title);
            return;
        }

        var contentElements = [];
        var children = listItem.children;
        var pastTrigger = false;

        for (var i = 0; i < children.length; i++) {
            var child = children[i];

            if (child === trigger) {
                pastTrigger = true;
                continue;
            }
            if (!pastTrigger) continue;

            // Skip hidden placeholder divs
            if (child.style.visibility === 'hidden') continue;

            // Content: has data-testid="richTextElement" on itself OR contains it
            if (child.getAttribute('data-testid') === 'richTextElement' ||
                (child.querySelector && child.querySelector('[data-testid="richTextElement"]'))) {
                contentElements.push(child);
            }
        }

        if (contentElements.length === 0) {
            console.warn('[Accordion] No content found for:', title);
            return;
        }

        // Determine initial state: plus button hidden = expanded
        var plusStyle = window.getComputedStyle(plusBtnContainer);
        var isExpanded = (plusStyle.display === 'none' || plusStyle.visibility === 'hidden');

        console.log('[Accordion]', title, '- initial:', isExpanded ? 'EXPANDED' : 'COLLAPSED');

        // Apply initial state
        accordionApplyState(minusBtnContainer, plusBtnContainer, contentElements, isExpanded);

        // Attach click handler
        trigger.style.cursor = 'pointer';
        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            isExpanded = !isExpanded;
            accordionApplyState(minusBtnContainer, plusBtnContainer, contentElements, isExpanded);
            console.log('[Accordion]', title, '→', isExpanded ? 'EXPANDED' : 'COLLAPSED');
        });
    });
}

function accordionApplyState(minusBtn, plusBtn, contentEls, expanded) {
    if (expanded) {
        // Show minus (collapse icon), force visible to override Avo SSR styles
        minusBtn.style.cssText = 'display: block !important; visibility: visible !important;';
        plusBtn.style.cssText = 'display: none !important; visibility: hidden !important;';
        contentEls.forEach(function (el) {
            el.style.cssText = 'transition: max-height 0.3s ease, opacity 0.3s ease; max-height: 2000px; opacity: 1; overflow: visible;';
        });
    } else {
        // Show plus (expand icon), force visible to override Avo SSR styles
        minusBtn.style.cssText = 'display: none !important; visibility: hidden !important;';
        plusBtn.style.cssText = 'display: block !important; visibility: visible !important;';
        contentEls.forEach(function (el) {
            el.style.cssText = 'transition: max-height 0.3s ease, opacity 0.3s ease; max-height: 0; opacity: 0; overflow: hidden;';
        });
    }
}

// Run accordion init after DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProductAccordions);
} else {
    initProductAccordions();
}
// Also run on load as a safety net
window.addEventListener('load', initProductAccordions);
