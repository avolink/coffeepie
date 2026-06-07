document.addEventListener('DOMContentLoaded', () => {
    const style = document.createElement('style');
    style.textContent = `
        .custom-subscribe-container {
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
        }
        .custom-checkbox-label-new {
            display: flex !important;
            align-items: center !important;
            cursor: pointer !important;
            font-size: 14px !important;
            color: #ffffff !important;
            white-space: nowrap !important;
        }
        .custom-subscribe-checkbox-new {
            width: 18px !important;
            height: 18px !important;
            margin-right: 8px !important;
            cursor: pointer !important;
            accent-color: #6B4E3D !important;
        }
        .custom-subscribe-btn {
            width: 32px !important;
            height: 32px !important;
            border-radius: 50% !important;
            background-color: #ffffff !important;
            border: 1px solid #cccccc !important;
            cursor: pointer !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            color: #6B4E3D !important;
            transition: all 0.2s ease !important;
            flex-shrink: 0 !important;
        }
        .custom-subscribe-btn:hover {
            background-color: #6B4E3D !important;
            color: #ffffff !important;
        }
    `;
    document.head.appendChild(style);

    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mainNav = document.querySelector('.main-nav');

    if (mobileMenuBtn && mainNav) {
        mobileMenuBtn.addEventListener('click', () => {
            mainNav.classList.toggle('active');
            const icon = mobileMenuBtn.querySelector('i');
            if (mainNav.classList.contains('active')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-times');
            } else {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });
    }

    const SUBSCRIPTION_EMAIL = 'info@coffeepie.co';
    const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

    function sanitizeEmail(email) {
        const sanitized = email.trim();
        if (!emailRegex.test(sanitized)) {
            return null;
        }
        return sanitized;
    }

    function handleSubscriptionSubmit(event) {
        const form = event.target.closest('form[aria-label="Subscription"]');
        if (!form) return;

        const subscribeCheckbox = form.querySelector('.custom-subscribe-checkbox-new');
        const emailInput = form.querySelector('input[type="email"]');

        if (!subscribeCheckbox || !emailInput) return;

        if (!subscribeCheckbox.checked) {
            alert('Por favor, marca la casilla de suscripción.');
            event.preventDefault();
            return;
        }

        const email = emailInput.value;
        const sanitizedEmail = sanitizeEmail(email);

        if (!sanitizedEmail) {
            alert('Por favor, ingresa un correo electrónico válido.');
            event.preventDefault();
            return;
        }

        event.preventDefault();

        const subject = encodeURIComponent('Suscripción - Coffee Pie');
        const body = encodeURIComponent(`Hola,\n\nMe gustaría suscribirme a las novedades y promociones de Coffee Pie.\n\nMi correo electrónico es: ${sanitizedEmail}\n\nSaludos`);
        
        window.location.href = `mailto:${SUBSCRIPTION_EMAIL}?subject=${subject}&body=${body}`;

        subscribeCheckbox.checked = false;
        emailInput.value = '';
    }

    document.querySelectorAll('form[aria-label="Subscription"]').forEach(form => {
        form.addEventListener('submit', handleSubscriptionSubmit);
        
        const subscribeBtn = document.getElementById('subscribe-btn');
        if (subscribeBtn) {
            subscribeBtn.addEventListener('click', handleSubscriptionSubmit);
        }

        const emailInput = form.querySelector('input[type="email"]');
        if (emailInput) {
            emailInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSubscriptionSubmit(new Event('submit', { bubbles: true }));
                }
            });
        }
    });
});
