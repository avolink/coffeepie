
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

    document.querySelectorAll('a[href*="carrito"], a[href*="cart-page"], [data-hook="cart-icon-button"]').forEach(link => {
        link.setAttribute('aria-label', `Carrito con ${totalItems} ítems`);
        const badge = link.querySelector('span, text[data-hook="items-count"]');
        if (badge) badge.textContent = totalItems;
    });
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
        itemsHtml += `
            <div class="cart-item-row">
                <div class="cart-item-info">
                    <img src="${item.image}" class="cart-item-image" onerror="this.src='/assets/557674_3c3a2d29a9434c33a754d6cac7b98b98.png';">
                    <div class="cart-item-details">
                        <h3 class="cart-item-title">${item.name}</h3>
                        <p class="cart-item-unit-price">$ ${p.toLocaleString('es-CO')},00</p>
                        <p class="cart-item-variant">Selección estándar</p>
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
                
                <button onclick="alert('Checkout en mantenimiento')" style="width:100%; padding:18px; background:#000; color:#fff; border:none; border-radius:30px; font-size:1.1rem; cursor:pointer; margin-bottom:15px; font-weight:normal; letter-spacing:0.5px;">
                    Solicitar (Request)
                </button>
                
                <div style="text-align:center; font-size:0.95rem; color:#555; display:flex; justify-content:center; align-items:center; gap:6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                    <span>Pago seguro</span>
                </div>
            </div>
            
        </div>
    `;

    updateAvoTotals(total);
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
    const btn = e.target.closest('button[aria-label="Agregar al carrito"], button.sBQRG_k');
    if (btn) {
        e.preventDefault();
        e.stopPropagation();

        let container = btn.closest('[data-hook="product-item-root"]');
        if (!container) {
            container = btn.parentElement;
            while (container && !container.querySelector('.JPDEZd') && container.tagName !== 'BODY') {
                container = container.parentElement;
            }
        }

        const nameEl = container?.querySelector('.JPDEZd p') || container?.querySelector('h1') || document.querySelector('h1');
        let priceEl = [...(container?.querySelectorAll('span') || [])].find(s => s.innerText.includes('$'));

        if (nameEl && priceEl) {
            let imgSrc = '';
            if (container) {
                let imgs = Array.from(container.querySelectorAll('wow-image img'));
                if (imgs.length === 0) imgs = Array.from(container.querySelectorAll('img'));

                const bestImg = imgs.find(img => {
                    const s = img.src || img.getAttribute('src') || '';
                    return s && !s.includes('data:image') && s.length > 10;
                });
                if (bestImg) imgSrc = bestImg.src || bestImg.getAttribute('src');
            }

            const prod = {
                name: nameEl.innerText.trim(),
                price: priceEl.innerText.trim(),
                image: imgSrc
            };
            const cart = getCart();
            const ex = cart.find(i => i.name === prod.name);
            if (ex) ex.quantity++; else cart.push({ ...prod, quantity: 1 });
            saveCart(cart);
            showFeedback(prod.name);
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('a[href*="cart-page"]').forEach(l => l.href = '/carrito.html');
    updateCartUI();
});
