// Coffee Pie Ads API - Login for advertisers
// Desktop: inline with header. Mobile: injected as last item in hamburger menu.
(function() {
    'use strict';

    var ORCHESTRATOR_URL = 'https://orquestador.coffeepie.co';
    var baseUrl = ORCHESTRATOR_URL + '/uds/rest';
    var labels = { es: 'Acceder al Panel', en: 'Dashboard' };
    var currentLang = 'es';

    function getLang() {
        var c = document.cookie.match(/(?:^|;\s*)uds_lang=([^;]*)/);
        if (c) return c[1]==='en'?'en':'es';
        return (document.documentElement.lang||'').startsWith('en')?'en':'es';
    }

    function postLogin(user, pass, cb) {
        var x=new XMLHttpRequest(); x.open('POST',baseUrl+'/auth/login',true);
        x.setRequestHeader('Content-Type','application/x-www-form-urlencoded'); x.withCredentials=true;
        x.onreadystatechange=function(){if(x.readyState===4){try{var r=JSON.parse(x.responseText);if(Array.isArray(r))r=r[0];cb(r);}catch(e){cb({error:'Connection error'});}}};
        x.send('username='+encodeURIComponent(user)+'&password='+encodeURIComponent(pass)+'&auth_id=1');
    }

    function init() {
        currentLang = getLang();

        var ss = document.createElement('style'); ss.textContent = ''
            + '.cp-desk-link{ color:#fff; font-family:Arial,Helvetica,sans-serif; font-size:14px; text-decoration:none; white-space:nowrap; }'
            + '.cp-desk-link:hover{ color:#c18b44; }'
            + '.cp-menu-item .cp-item-label{ font-size:16px; color:#fff; font-family:helvetica-w01-light,helvetica-w02-light,sans-serif; display:inline; padding:10px 0; }'
            + '.cp-modal-bg{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:99999999; justify-content:center; align-items:center; }'
            + '.cp-modal-bg.show{ display:flex; }'
            + '.cp-modal{ background:#1a1a1a; padding:50px 40px; border-radius:16px; width:400px; text-align:center; border:1px solid #333; }'
            + '.cp-modal h2{ color:#c18b44; margin-bottom:10px; font-family:Arial,sans-serif; }'
            + '.cp-modal p{ color:#888; margin-bottom:25px; font-size:14px; font-family:Arial,sans-serif; }'
            + '.cp-modal input{ width:100%; padding:14px; margin-bottom:15px; background:#222; border:1px solid #444; border-radius:8px; color:#fff; font-size:16px; box-sizing:border-box; }'
            + '.cp-modal input:focus{ border-color:#c18b44; outline:none; }'
            + '.cp-modal .cp-btn{ width:100%; padding:14px; background:#c18b44; color:#111; border:none; border-radius:8px; font-size:16px; font-weight:bold; cursor:pointer; margin-top:10px; }'
            + '.cp-modal .cp-btn:hover{ background:#d49b56; }'
            + '.cp-modal .cp-link{ color:#888; text-decoration:underline; cursor:pointer; font-size:13px; margin-top:15px; display:block; }'
            + '.cp-modal .cp-error{ color:#ff6666; font-size:13px; margin-top:10px; display:none; }';
        document.head.appendChild(ss);

        // Desktop link
        var desk = document.createElement('a');
        desk.className = 'cp-desk-link';
        desk.textContent = labels[currentLang]; desk.href = '#';
        desk.style.position = 'fixed';
        document.body.appendChild(desk);

        // Modal
        var mod = document.createElement('div'); mod.className = 'cp-modal-bg';
        mod.innerHTML = '<div class="cp-modal"><h2>Coffee Pie Ads</h2><p>Accede al Panel de Anunciantes</p><input type="text" class="cp-user" placeholder="Usuario"><input type="password" class="cp-pass" placeholder="Contraseña"><div class="cp-error"></div><button class="cp-btn cp-submit">Iniciar Sesión</button><span class="cp-link cp-close">Cancelar</span></div>';
        document.body.appendChild(mod);

        var uEl = mod.querySelector('.cp-user'), pEl = mod.querySelector('.cp-pass');
        var err  = mod.querySelector('.cp-error'), sub = mod.querySelector('.cp-submit'), cls = mod.querySelector('.cp-close');

        function doLogin() {
            var u=uEl.value.trim(), p=pEl.value;
            if(!u||!p){err.style.display='block';err.textContent='Ingresa usuario y contraseña';return;}
            err.style.display='none';sub.textContent='Entrando...';sub.disabled=true;
            postLogin(u,p,function(r){sub.textContent='Iniciar Sesión';sub.disabled=false;
                if(r.result==='ok'&&r.auth){window.location.href=ORCHESTRATOR_URL+'/uds/page/advertiser/';}
                else{err.style.display='block';err.textContent='Credenciales inválidas';}});
        }

        function openModal(e) { e.preventDefault(); mod.classList.add('show'); uEl.focus(); }
        desk.onclick = openModal;
        cls.onclick = function() { mod.classList.remove('show'); };
        mod.onclick = function(e) { if(e.target===mod) mod.classList.remove('show'); };
        sub.onclick = doLogin;
        pEl.onkeydown = function(e) { if(e.key==='Enter') doLogin(); };

        // Language
        document.addEventListener('click',function(e){
            var b=e.target.closest('.avoui-language-menu__option');
            if(b){var t=(b.querySelector('.J6PIw1')||{}).textContent||''; currentLang=(t==='EN')?'en':'es';
                desk.textContent=labels[currentLang];
                var m=document.querySelector('.cp-menu-item .cp-item-label');
                if(m) m.textContent=labels[currentLang];}
        });

        // Hamburger menu item injection
        function injectMenu() {
            console.log('[CP] injectMenu() called');
            if (document.querySelector('.cp-menu-item')) {
                console.log('[CP] already injected, ok');
                return;
            }

            var nav = document.querySelector('.avoui-vertical-menu');
            console.log('[CP] nav found:', !!nav);
            if (!nav) return;

            // Find the <ul> inside the nav
            var ul = nav.querySelector('ul') || nav.querySelector('[role]') || nav;
            console.log('[CP] ul found:', !!ul, 'tag:', ul.tagName);
            if (!ul) return;

            // Find API/MCP item to insert after
            var items = ul.querySelectorAll('.avoui-vertical-menu__item');
            console.log('[CP] menu items found:', items.length);
            var apiItem = null;
            for (var i = 0; i < items.length; i++) {
                var lbl = items[i].querySelector('.avoui-vertical-menu__item-label');
                if (lbl && /API\/MCP/i.test(lbl.textContent)) { apiItem = items[i]; break; }
            }
            console.log('[CP] API/MCP item found:', !!apiItem);

            // Create <li> matching Avo vertical menu item structure
            var li = document.createElement('li');
            li.className = 'cp-menu-item u4cNtA YLBS9j OZVMSN avoui-vertical-menu__item';
            li.setAttribute('style',
                'display:block !important;' +
                'visibility:visible !important;' +
                'opacity:1 !important;' +
                'cursor:pointer;' +
                'width:100%;' +
                'list-style:none;' +
                'box-sizing:border-box;' +
                'position:relative;' +
                'text-align:left;' +
                'border:1px solid rgba(255,255,255,0.15);' +
                'margin:0;' +
                'background:transparent;'
            );

            var itemWrap = document.createElement('div');
            itemWrap.setAttribute('data-testid', 'itemWrapper');
            itemWrap.className = 'fEGEM_';

            var linkWrap = document.createElement('span');
            linkWrap.setAttribute('data-testid', 'linkWrapper');
            linkWrap.className = 'kGvnrc';

            var label = document.createElement('span');
            label.className = 'cp-item-label xfxJ27 avoui-vertical-menu__item-label';
            label.setAttribute('style',
                'display:inline-block !important;' +
                'color:#ffffff !important;' +
                'font-size:16px !important;' +
                'font-family:helvetica-w01-light,helvetica-w02-light,sans-serif !important;' +
                'padding:12px 20px !important;' +
                'line-height:1.5;' +
                'white-space:nowrap;' +
                'text-decoration:none;'
            );
            label.textContent = labels[currentLang];

            linkWrap.appendChild(label);
            itemWrap.appendChild(linkWrap);
            li.appendChild(itemWrap);
            li.addEventListener('click', function(e) { e.preventDefault(); openModal(e); });

            // Insert after API/MCP into the <ul>, or append to end
            if (apiItem && apiItem.nextSibling) {
                ul.insertBefore(li, apiItem.nextSibling);
            } else {
                ul.appendChild(li);
            }
            console.log('[CP] item inserted. visible in DOM:', !!document.querySelector('.cp-menu-item'));
            // Debug: log computed styles
            var cs = getComputedStyle(li);
            console.log('[CP] computed:', {
                display: cs.display,
                visibility: cs.visibility,
                opacity: cs.opacity,
                width: cs.width,
                height: cs.height,
                color: cs.color,
                fontSize: cs.fontSize,
                offsetParent: !!li.offsetParent
            });
        }

        // Position desktop link 300px left of language selector
        function position() {
            var lang = document.querySelector('.avoui-language-menu__option');
            if (lang) {
                var r = lang.getBoundingClientRect();
                var x = r.left - 300; if (x < 10) x = 10;
                desk.style.left = x + 'px';
                desk.style.top = (r.top + 2) + 'px';
                desk.style.display = 'block';
            }
            injectMenu();
        }

        position();
        setTimeout(position, 800);
        setTimeout(position, 2500);
        window.addEventListener('resize', function(){setTimeout(position,100);});

        // MutationObserver: re-inject if Avo React removes our menu item
        var obs = new MutationObserver(function(mutations) {
            var cp = document.querySelector('.cp-menu-item');
            if (!cp) injectMenu();
        });
        obs.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
