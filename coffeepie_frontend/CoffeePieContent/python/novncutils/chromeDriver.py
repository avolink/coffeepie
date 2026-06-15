import os
import logging
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import urllib3
import time

logging.getLogger('webdriver_manager').setLevel(logging.WARNING)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#PROXMOX_URL = "https://100.110.125.54:8006" servidor en tecno parque
#PROXMOX_IP = "100.110.125.54"

PROXMOX_URL = "https://100.73.239.98:8006" 
PROXMOX_IP = "100.73.239.98"
# Cambia esto si tu FastAPI no está corriendo localmente
host = os.environ.get("API_HOST", "127.0.0.1")
#API_ENDPOINT = f"http://{host}:8000/console-url"
API_ENDPOINT = "https://3e33-181-132-118-30.ngrok-free.app/console-url"
#API_ENDPOINT = "http://127.0.0.1:8000/console-url"

def get_console_data(node, vmid, vmname):
    """Consulta el endpoint FastAPI para obtener la URL de la consola y los tokens"""
    params = {"node": node, "vmid": vmid, "vmname": vmname}
    response = requests.get(API_ENDPOINT, params=params)
    response.raise_for_status()
    data = response.json()
    return data["console_url"], data["ticket"], data["csrf_token"]



def wait_for_novnc_ready(driver, timeout=5):
    """
    Waits until the noVNC canvas is present and the status bar
    shows 'Connected' — only then we maximize.
    """
    try:
        # Step 1: Wait for the noVNC canvas element to appear in the DOM
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "noVNC_canvas"))
        )
        print("noVNC canvas found, waiting for connection...")

        # Step 2: Wait until the status text contains 'Connected'
        WebDriverWait(driver, timeout).until(
            lambda d: "Connected" in (
                d.find_element(By.ID, "noVNC_status").text
                if len(d.find_elements(By.ID, "noVNC_status")) > 0
                else ""
            )
        )
        print("noVNC connected.")
        return True

    except Exception as e:
        print(f"Timeout or error waiting for noVNC: {e}")
        # Fallback: just wait a fixed time if selectors don't match
        time.sleep(5)
        return False




def open_console_with_tokens(console_url, ticket, csrf_token):
    """Abre una sesión visible del navegador con cookies de autenticación"""
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-component-extensions-with-background-pages")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--ozone-platform=wayland")   # ← add this
    chrome_options.add_argument("--enable-features=UseOzonePlatform")  #
    #chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1,1")
    chrome_options.add_argument("--window-position=0,0")

  # Find the real Chrome binary (not a snap stub)
    chrome_candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/local/bin/google-chrome",
        "/usr/bin/chromium",                # arm64 Debian/Armbian
         "/usr/bin/chromium-browser",        # arm64 alternate name
    ]
    for candidate in chrome_candidates:
        if os.path.exists(candidate):
            chrome_options.binary_location = candidate
            print(f"Using Chrome binary at: {candidate}")
            break
    else:
        print("No explicit Chrome binary found — letting Selenium resolve it.")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Chrome initialized successfully.")
   
    except Exception as e:
        print(f"Error initializing Chrome: {e}")
        
        traceback.print_exc()
        raise
    
   # driver.minimize_window()

    # Agrega cookies a la sesión
    driver.get(PROXMOX_URL)  # Abrimos dominio base antes de setear cookies
    driver.add_cookie({
        "name": "PVEAuthCookie",
        "value": ticket,
        "path": "/",
        "domain": PROXMOX_IP,
        "httpOnly": True,
        "secure": False
    })
    driver.add_cookie({
        "name": "CSRFPreventionToken",
        "value": csrf_token,
        "path": "/",
        "domain": PROXMOX_IP,
        "httpOnly": False,
        "secure": False
    })

    # Accede a la URL completa de la consola
    driver.get("https://" + console_url)
    #driver.maximize_window()
    # Wait for console to be ready, THEN maximize
    wait_for_novnc_ready(driver)
    driver.set_window_size(1920, 1080)   # maximize via size — no window manager needed
    print("Console ready and window maximized.")
    print("Consola noVNC abierta para el usuario.")
    try:
        driver.execute_script("""
            document.body.requestFullscreen().catch(() => {});
        """)
        while True:
            driver.title
            time.sleep(1)
    except:
        print("Navegador cerrado por el usuario.")
    finally:
        driver.quit()