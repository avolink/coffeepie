# Panel backend en el VPS — puesta en marcha

Estado antes de esta guía: **el backend nunca se desplegó en producción**. Las
pruebas que funcionaron hace semanas iban contra `localhost:8000`, porque el
frontend cae ahí solo cuando se sirve desde localhost:

```js
// coffeepie_website/public/js/cp-panel-auth.js
var API = isLocal ? 'http://localhost:8000' : 'https://api.coffeepie.co';
```

En producción `api.coffeepie.co` tiene dos fallos encadenados: redirige sobre sí
mismo, y detrás no hay nada escuchando. Esta guía arregla los dos.

No es Docker: es un servicio **systemd** con uvicorn, y por eso `docker ps` no
enseñaba nada. La unidad ya existe en `deploy/coffeepie-panel.service`.

---

## 0. El bucle de redirección (primero, es de un minuto)

`nginx.forcessl.conf` contiene un `return 301` incondicional y **se incluye en
los dos vhosts**:

```
nginx.conf:10       include …/nginx.forcessl.conf*;   ← correcto (puerto 80)
nginx.ssl.conf:17   include …/nginx.forcessl.conf*;   ← el bucle (ya es HTTPS)
```

Una petición HTTPS entra, el vhost SSL la manda a HTTPS otra vez, y así hasta
que el navegador se rinde.

Se puede borrar la línea 17, pero Hestia regenera los vhosts cuando se toca el
dominio y volvería. Es más robusto hacer la propia regla consciente del esquema,
así da igual desde cuántos sitios se incluya:

```bash
cat > /home/admin/conf/web/api.coffeepie.co/nginx.forcessl.conf <<'EOF'
# Sólo redirige si AÚN NO estamos en HTTPS. La versión incondicional se incluía
# también desde nginx.ssl.conf y provocaba un bucle 301 infinito.
if ($scheme != "https") { return 301 https://$host$request_uri; }
EOF
nginx -t && systemctl reload nginx
```

Comprobación — debe dar 404 o 502, **cualquier cosa menos 301**:

```bash
curl -sI https://api.coffeepie.co/health | head -1
```

Un 502 en este punto es buena señal: significa que nginx ya no da vueltas y está
intentando hablar con un backend que todavía no existe.

---

## 1. Python y dependencias

```bash
cd /home/admin/coffeepie/coffeepie_backend/panel_backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

`cryptography` y `psycopg[binary]` traen ruedas precompiladas; si alguna
intentara compilar, faltan cabeceras:
`apt-get install -y python3-dev build-essential libpq-dev`.

La ruta del venv tiene que ser exactamente ésa: la unidad systemd apunta a
`/home/admin/coffeepie/coffeepie_backend/panel_backend/.venv/bin/uvicorn`.

---

## 2. El `.env`

```bash
cp .env.example .env
chmod 600 .env          # contiene la clave que descifra contraseñas de nodos
nano .env
```

Lo que hay que rellenar:

| Variable | De dónde sale |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `DATABASE_URL` | Supabase → Project Settings → Database → Connection string |
| `NODE_CRED_ENC_KEY` | **ver el aviso de abajo** |

`AUTH_PROVIDER`, `QA_LOCAL_AUTH` y `LEDGER_BACKEND` ya los fija la unidad
systemd (`supabase`, `false`, `postgres`), así que no hace falta ponerlos aquí.

### ⚠ NODE_CRED_ENC_KEY: la clave que descifra tiene que ser la que cifró

`node.root_password_enc` guarda la contraseña root de Proxmox cifrada con Fernet.
Cuando registraste el nodo `206.62.137.22` desde la GUI, se cifró con la clave
que tuviera **esa** instancia — muy probablemente la de QA que viene por defecto
en `app/auth/node_credentials.py`, si estabas en localhost sin definir nada.

Si producción arranca con una clave nueva, el registro que ya está en Supabase
queda indescifrable y la conexión a Proxmox falla con un error que no dice eso.

Dos salidas:
- poner en producción la MISMA clave con la que se registró, o
- generar una nueva y **volver a registrar el nodo** desde la GUI:
  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

Lo que no funciona es clave nueva + credenciales viejas.

### CORS

El valor por defecto cubre `coffeepie.co`, `www.coffeepie.co`, el prototipo de
Firebase y los puertos locales 5000 y 8080 — **no el 5002**, que es el que usas
para desarrollo. Si vas a pegarle desde ahí:

```ini
CORS_ORIGINS=https://coffeepie.co,https://www.coffeepie.co,http://localhost:5002
```

---

## 3. Migraciones

Cinco ficheros en `supabase/migrations/` (`0001_init_schema` … `0005_ads`).
Se aplican desde el editor SQL de Supabase, en orden. Si el panel ya lee y
escribe nodos desde la GUI, es que ya están puestas; si dudas, `0001` es
idempotente (`CREATE TABLE IF NOT EXISTS`).

---

## 4. Arrancar el servicio

```bash
cp deploy/coffeepie-panel.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now coffeepie-panel
systemctl status coffeepie-panel --no-pager
```

Escucha en `127.0.0.1:8000` — nunca en `0.0.0.0`, para que sólo se llegue por
nginx con TLS.

```bash
curl -s localhost:8000/health          # ojo: /health, NO /healthz
journalctl -u coffeepie-panel -n 40 --no-pager
```

---

## 5. nginx: `api.coffeepie.co` → `127.0.0.1:8000`

En Hestia: Web → api.coffeepie.co → Editar → **Nginx Additional directives**.

```nginx
location / {
    proxy_pass         http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_set_header   Authorization     $http_authorization;

    # WebSocket: stream_routes.py hace de relé hasta el vncwebsocket de Proxmox.
    # Sin estas dos cabeceras el panel funciona pero el streaming muere al abrir
    # la máquina, y el error aparece lejos de aquí.
    proxy_set_header   Upgrade    $http_upgrade;
    proxy_set_header   Connection "upgrade";

    # Una sesión de streaming está minutos sin mandar nada; el defecto de 60 s
    # la cortaría.
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

`nginx -t && systemctl reload nginx`, y entonces:

```bash
curl -s https://api.coffeepie.co/health
```

---

## 6. Probar la cadena, un eslabón cada vez

Cada paso aísla un fallo distinto; si uno falla, no sigas al siguiente.

```bash
# 1. ¿responde la API por HTTPS?
curl -s https://api.coffeepie.co/health

# 2. ¿verifica el token de Supabase? (401 = correcto sin token)
curl -s -o /dev/null -w '%{http_code}\n' https://api.coffeepie.co/v1/vms/me

# 3. ¿ve el nodo registrado? (con el token de la sesión del navegador)
curl -s -H "Authorization: Bearer $TOKEN" https://api.coffeepie.co/v1/nodes
```

Y desde el VPS, que el hipervisor esté alcanzable de verdad:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://206.62.137.22:8006/api2/json/version
```

`200` o `401` significan que Proxmox contesta (401 = vivo, pide credenciales).
Si da timeout, el problema es de red o de firewall y no tiene nada que ver con
el panel.

Después ya sí: crear una máquina desde la GUI y mirar
`journalctl -u coffeepie-panel -f` mientras lo hace. Ahí se ve la autenticación
contra Proxmox y el clonado de la plantilla.

---

## Cuando algo falla

| Síntoma | Dónde mirar |
|---|---|
| 301 en bucle | volver al paso 0; `nginx.ssl.conf` sigue incluyendo el forcessl incondicional |
| 502 Bad Gateway | el servicio no está arriba: `systemctl status coffeepie-panel` |
| 401 en todo, con sesión válida | `SUPABASE_URL` mal, o el token es de otro proyecto |
| Proxmox rechaza credenciales | `NODE_CRED_ENC_KEY` no es la que cifró — ver el aviso del paso 2 |
| El panel carga pero el streaming no abre | faltan `Upgrade`/`Connection` en nginx (paso 5) |
| CORS bloqueado en el navegador | añadir el origen a `CORS_ORIGINS` y reiniciar el servicio |
