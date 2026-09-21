#!/usr/bin/env python3
"""
Wix Page Cleaner Utility
Removes Wix framework JS, massive state payloads, and extracts inline CSS
while preserving the pixel-perfect HTML structure.
"""
import sys
import os
import re
from bs4 import BeautifulSoup

def clean_wix_file(filepath):
    print(f"Cleaning: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found.")
        sys.exit(1)
        
    # Backup original
    backup_path = filepath + '.wix.bak'
    if not os.path.exists(backup_path):
        os.rename(filepath, backup_path)
        print(f"Created backup at {backup_path}")
    else:
        print(f"Backup already exists at {backup_path}")

    # Read from backup
    with open(backup_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # 1. Extract massive inline <style> tags to a separate CSS file
    # Only target styles > 10KB to avoid removing small component styles
    styles = []
    for style in soup.find_all('style'):
        if style.string and len(style.string) > 10000:
            styles.append(style)
            
    if styles:
        basename = os.path.basename(filepath).replace('.html', '')
        css_filename = f"{basename}-wix.css"
        css_filepath = os.path.join(os.path.dirname(filepath), 'css', css_filename)
        
        os.makedirs(os.path.dirname(css_filepath), exist_ok=True)
        with open(css_filepath, 'w', encoding='utf-8') as f:
            for style in styles:
                f.write(style.string)
                style.decompose()
        print(f"Extracted massive inline styles to css/{css_filename}")
        
        # Inject the new CSS link
        link = soup.new_tag('link', rel='stylesheet', href=f'/css/{css_filename}')
        soup.head.append(link)

    # 2. Remove Wix specific framework scripts
    scripts_removed = 0
    for script in soup.find_all('script'):
        src = script.get('src', '')
        content = script.string or ''
        
        # Keep our custom/Vanilla JS files
        if re.search(r'(header|footer|cart|main|lang|translate|firebase-init)\.js', src):
            continue
            
        # Keep minimal inline vanilla JS (e.g. DOMContentLoaded for basic UI)
        if 'document.addEventListener' in content and ('videoContainer' in content or 'setupCycling' in content):
            continue
            
        script.decompose()
        scripts_removed += 1
        
    print(f"Removed {scripts_removed} script tags (Wix bundles and JSON state blobs).")

    # 3. Remove Wix iframes (used for internal metrics/pixels)
    for iframe in soup.find_all('wix-iframe'):
        iframe.decompose()

    # 4. Replace Wix Header/Footer with dynamic Vanilla JS placeholders
    header = soup.find(id='SITE_HEADER')
    if header:
        ph = soup.new_tag('div', id='reusable-header-placeholder')
        scr = soup.new_tag('script', src='/header.js')
        header.replace_with(ph)
        ph.insert_after(scr)
        print("Replaced SITE_HEADER with reusable-header-placeholder")

    footer = soup.find(id='SITE_FOOTER')
    if footer:
        pf = soup.new_tag('div', id='reusable-footer-placeholder')
        scr = soup.new_tag('script', src='/footer.js')
        footer.replace_with(pf)
        pf.insert_after(scr)
        print("Replaced SITE_FOOTER with reusable-footer-placeholder")

    # Write the cleaned HTML
    new_html = str(soup)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_html)
        
    original_size = os.path.getsize(backup_path)
    new_size = os.path.getsize(filepath)
    print(f"Cleaned file written to {filepath}")
    print(f"Size reduction: {original_size/1024:.1f} KB -> {new_size/1024:.1f} KB ({(1 - new_size/original_size)*100:.1f}% reduction)\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 wix_cleaner.py <path_to_html_file>")
        sys.exit(1)
        
    for path in sys.argv[1:]:
        clean_wix_file(path)
