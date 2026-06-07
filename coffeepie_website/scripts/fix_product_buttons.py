import os
import glob
import re

html_dir = "/home/avolink/DEV/coffeepie/coffeepie_website/public/productos"
html_files = glob.glob(os.path.join(html_dir, "*.html"))

pattern = re.compile(r"document\.getElementById\('add-to-cart-btn'\)\.addEventListener\('click', function\(\) \{\s*var btn = this;\s*btn\.classList\.add\('cp-product__add-btn--added'\);\s*btn\.querySelector\('span'\)\.textContent = 'Agregado!';\s*setTimeout\(function\(\) \{\s*btn\.classList\.remove\('cp-product__add-btn--added'\);\s*btn\.querySelector\('span'\)\.textContent = 'Agregar al Carrito';\s*\}, 2000\);\s*\}\);", re.MULTILINE)

count = 0
for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content, num_subs = pattern.subn('', content)
    
    if num_subs > 0:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        count += 1

print(f"Fixed {count} files.")
