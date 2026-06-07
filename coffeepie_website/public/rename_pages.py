import os
import re
import json

public_dir = '/home/avolink/DEV/coffeepie/coffeepie_website/public'
root_dir = '/home/avolink/DEV/coffeepie/coffeepie_website'

rename_map = {
    'accesibilidad': 'accessibility',
    'acerca-de': 'about',
    'carrito': 'cart',
    'dispositivos-certificados': 'certified-devices',
    'fabricantes': 'manufacturers',
    'pago-seguro': 'secure-payment',
    'panel': 'panel',
    'politica-de-envios': 'shipping-policy',
    'politica-de-privacidad': 'privacy-policy',
    'politica-de-retornos': 'return-policy',
    'portal-inversionistas': 'investor-portal',
    'precios': 'pricing',
    'proveedores-nube': 'cloud-providers',
    'terminos-y-condiciones': 'terms-and-conditions',
    'tienda': 'store',
    'tutoriales': 'tutorials'
}

# 1. Rename files and directories
for old, new in rename_map.items():
    if old == new: continue
    
    old_html = os.path.join(public_dir, f"{old}.html")
    new_html = os.path.join(public_dir, f"{new}.html")
    if os.path.exists(old_html):
        print(f"Renaming {old}.html to {new}.html")
        os.rename(old_html, new_html)
        
    old_files = os.path.join(public_dir, f"{old}_files")
    new_files = os.path.join(public_dir, f"{new}_files")
    if os.path.exists(old_files):
        print(f"Renaming {old}_files to {new}_files")
        os.rename(old_files, new_files)

# 2. Update HTML/JS contents
print("Updating file contents...")
for root, dirs, files in os.walk(public_dir):
    for f in files:
        if f.endswith('.html') or f.endswith('.js') or f.endswith('.css'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            orig = content
            for old, new in rename_map.items():
                if old == new: continue
                # Replace _files references
                content = content.replace(f"{old}_files/", f"{new}_files/")
                # Replace exact html file references
                content = content.replace(f"{old}.html", f"{new}.html")
                # Replace href="/old"
                content = re.sub(fr'(href=["\'])/{old}(/?["\'])', fr'\1/{new}\2', content)
                content = re.sub(fr'(href=["\']){old}(/?["\'])', fr'\1{new}\2', content)
                # Replace window.location.href updates etc
                content = re.sub(fr'(["\'])/{old}(/?["\'])', fr'\1/{new}\2', content)
                
            if content != orig:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(content)
                print(f"Updated {f}")

# 3. Update firebase.json
print("Updating firebase.json...")
firebase_path = os.path.join(root_dir, 'firebase.json')
with open(firebase_path, 'r', encoding='utf-8') as f:
    fb_data = json.load(f)

new_rewrites = []
added_sources = set()

if 'rewrites' in fb_data['hosting']:
    for rewrite in fb_data['hosting']['rewrites']:
        src = rewrite['source']
        dest = rewrite.get('destination', '')
        
        # Check if it's one of our target rewrites
        matched_old = None
        for old, new in rename_map.items():
            if src == f"/{old}" or dest == f"/{old}.html":
                matched_old = old
                break
                
        if matched_old:
            new_val = rename_map[matched_old]
            # Keep original spanish slug pointing to new html
            new_rewrites.append({
                "source": f"/{matched_old}",
                "destination": f"/{new_val}.html"
            })
            added_sources.add(f"/{matched_old}")
            
            # Add english slug pointing to new html (if different)
            if old != new:
                new_rewrites.append({
                    "source": f"/{new_val}",
                    "destination": f"/{new_val}.html"
                })
                added_sources.add(f"/{new_val}")
        else:
            if src not in added_sources:
                new_rewrites.append(rewrite)
                added_sources.add(src)

fb_data['hosting']['rewrites'] = new_rewrites

# Update Redirects (e.g. /princing -> /pricing instead of /precios)
if 'redirects' in fb_data['hosting']:
    for redirect in fb_data['hosting']['redirects']:
        for old, new in rename_map.items():
            if old == new: continue
            if redirect['destination'] == f"/{old}":
                redirect['destination'] = f"/{new}"

with open(firebase_path, 'w', encoding='utf-8') as f:
    json.dump(fb_data, f, indent=4)

print("Updating .htaccess in public...")
# 4. Update .htaccess (public)
htaccess_public = os.path.join(public_dir, '.htaccess')
if os.path.exists(htaccess_public):
    with open(htaccess_public, 'r', encoding='utf-8') as f:
        ht = f.read()
    orig_ht = ht
    for old, new in rename_map.items():
        if old == new: continue
        # Redirection rules
        ht = re.sub(fr'/{old}(\s+\[R=)', fr'/{new}\1', ht)
        ht = re.sub(fr'\^{old}(/?\$) /{old}', fr'^{new}\1 /{new}', ht)
    if ht != orig_ht:
        with open(htaccess_public, 'w', encoding='utf-8') as f:
            f.write(ht)

print("Updating .htaccess in root...")
# 5. Update .htaccess (root)
htaccess_root = os.path.join(root_dir, '.htaccess')
if os.path.exists(htaccess_root):
    with open(htaccess_root, 'r', encoding='utf-8') as f:
        ht = f.read()
    orig_ht = ht
    
    # We want to add new rules or replace existing ones
    # Existing looks like: RewriteRule ^precios$ precios.html [L]
    for old, new in rename_map.items():
        if old == new: continue
        pattern = fr"RewriteRule \^{old}\$ {old}\.html \[L\]\n"
        replacement = f"RewriteRule ^{old}$ {new}.html [L]\nRewriteRule ^{new}$ {new}.html [L]\n"
        ht = re.sub(pattern, replacement, ht)
        # Update redirects
        ht = ht.replace(f" /{old}\n", f" /{new}\n")
        
    if ht != orig_ht:
        with open(htaccess_root, 'w', encoding='utf-8') as f:
            f.write(ht)

print("Done.")
