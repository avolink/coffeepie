# Coffee Pie® — asistente virtual

Chatbot público del sitio. Responde preguntas de orientación usando **sólo**
contenido publicado en coffeepie.co, y cuando no puede, ofrece soporte humano.
Sustituye al `toast` con el correo que salía al pulsar los botones "?" y
"Soporte Técnico".

Cumple además algo que el sitio ya vende: la página de precios promete
"Soporte: Chatbot Básico" en la capa gratuita y "Asistente IA Avanzado" en los
planes de pago.

---

## Por qué es un contenedor aparte

El `panel_backend` guarda credenciales de Proxmox, la clave de servicio de
Supabase y la capacidad de crear, redimensionar y borrar máquinas de clientes.
Un endpoint público que mete texto de visitantes en un modelo de lenguaje no
tiene nada que hacer dentro de ese proceso.

Este servicio **no importa nada privado**: no hay cliente de base de datos, ni
de hipervisor, ni secreto de identidad. Su única fuente de información es un
JSON estático generado del sitio público. No existe camino de código entre un
mensaje de chat y el plano de control, así que ningún prompt puede convencerlo
de recorrerlo. Hay un test que lo verifica (`test/no-private-imports.test.js`) y
falla si alguien añade un import que rompa la propiedad.

Las defensas están en capas, porque un modelo pequeño auto-alojado se salta las
instrucciones mucho más que Claude:

| Capa | Qué hace |
|---|---|
| Pre-filtro | Extracción de prompt, jailbreak, pesca de credenciales, datos de otros usuarios → misma respuesta neutra que un fallo normal |
| Contexto | El modelo sólo ve fragmentos públicos recuperados + la pregunta. Sin herramientas, sin red |
| Regla 1 | "Responde SOLO desde el CONTEXTO; si no está, di exactamente …" |
| Post-filtro | Si la respuesta menciona infraestructura o el propio modelo, se descarta |
| Lista blanca | Cada enlace se reescribe; los de fuera pierden el enlace y queda la etiqueta |

El pre-filtro es **más estrecho** que el de un sitio corporativo cerrado, a
propósito: Coffee Pie publica su API, su hardware y su código, así que "qué
stack usan", "dónde está el repo" o "cómo funciona QFDM" son preguntas normales
de cliente y bloquearlas rompería el producto.

---

## Desplegar

```bash
cd coffeepie_chat
cp .env.example .env          # elige el modelo (ver la sección siguiente)
npm install
npm run kb                    # genera data/chat-kb.json del sitio público
docker compose up -d --build
```

Después pega `deploy/nginx-chat.conf` en las "Nginx Additional directives" del
dominio **coffeepie.co** en Hestia (no en api.coffeepie.co: ese vhost responde
301 hacia sí mismo hoy, y colgarlo del sitio principal deja además el endpoint
en el mismo origen, sin CORS). Comprobación:

```bash
curl -s https://coffeepie.co/v1/chat/health
```

Debe responder `{"ok":true,"kb":57,"model":"on","provider":"openai"}`.
Si dice `"model":"kb-only"` el asistente funciona igual, pero contestando con
texto literal de la base de conocimiento en vez de conversar.

---

## El modelo: qué cabe en la RTX 5000

La Quadro RTX 5000 del servidor del SENA tiene **16 GB**. Los pesos son sólo una
parte: hay que dejar sitio para la caché KV del contexto y el propio runtime.

| Modelo | Pesos Q4_K_M | ¿Cabe con contexto? |
|---|---|---|
| gemma3:12b | ~8,1 GB | Sí, holgado (el que usa panelesa hoy) |
| **qwen2.5:14b-instruct** | **~9,0 GB** | **Sí, ~6 GB libres — recomendado** |
| mistral-small:24b | ~14,3 GB | Entra a presión; casi sin contexto |
| gemma3:27b | ~17 GB | No |
| qwen2.5:32b | ~20 GB | No |

Recomendado **qwen2.5:14b-instruct-q4_K_M**: es el salto de potencia que cabe
sin apreturas, y su ventaja concreta aquí no es "escribe más bonito" sino que
**obedece mejor la regla 1**. Con un modelo pequeño el fallo típico no es una
frase fea, es inventarse un precio; el 14B se inventa bastante menos.

> **La GPU es compartida.** El chatbot de panelesa.com corre en la misma
> tarjeta. 8,1 + 9,0 = 17,1 GB no caben, así que Ollama descargaría un modelo
> para cargar el otro en cada petición alterna y los dos sitios se volverían
> lentos. Hay que elegir: **mover los dos sitios al mismo modelo**, o dejar
> `CHAT_MODEL=gemma3:12b` aquí y no tocar panelesa. Un modelo distinto por sitio
> es la única opción que no funciona.

```bash
# en el contenedor del modelo: Proxmox del SENA → `pct enter 110` (hostname "LLM",
# antes "panelesa-llm" — sirve a los dos sitios, por eso el nombre neutro)
ollama pull qwen2.5:14b-instruct-q4_K_M
# y si se mueven los dos sitios, en el .env de panelesa:
#   CHAT_MODEL=qwen2.5:14b-instruct-q4_K_M
```

---

## El túnel desde el SENA — ya existe, no hagas otro

**Coffee Pie y panelesa comparten VPS.** `coffeepie.co`, `api.coffeepie.co`,
`panelesa.com` y `api.panelesa.com` resuelven todos a **209.74.89.188**, el
mismo HestiaCP donde ya vive `/home/admin/coffeepie`. El túnel inverso desde la
caja del SENA termina en esa máquina y está vivo:

```bash
curl -s https://api.panelesa.com/v1/chat/health
# {"ok":true,"kb":174,"model":"on","provider":"openai"}   ← "on" = Ollama alcanzable
```

Así que **no hay que abrir un segundo túnel**. Lo único que hay que resolver es
que el contenedor nuevo llegue al puerto donde el túnel ya escucha.

El túnel (`vps-tunnel.service` dentro del LXC) se ata a `172.18.0.1:11434`, que
es el gateway de compose de *panelesa*, y esa IP está fijada en dos sitios: el
`permitlisten` de la llave en el VPS y una regla del firewall de HestiaCP. Este
proyecto vive en su propia red (`172.19.0.0/16`), así que **hace falta una cosa,
exactamente una**:

### La regla de firewall (obligatoria, no opcional)

HestiaCP tiene `-P INPUT DROP`, así que descarta el tráfico contenedor→host. La
regla que ya existe está limitada a la subred de panelesa:

```
-s 172.18.0.0/16 -d 172.18.0.1 -p tcp --dport 11434 -j ACCEPT
```

Nuestro contenedor sale desde `172.19.0.0/16`, así que **no la cumple** y sus
paquetes se descartan en silencio. Hay que añadir la equivalente:

```bash
# en el VPS. Por subred, no por nombre de bridge: el nombre cambia al recrear
# la red. Persistirla con v-add-firewall-rule, comentario SIN espacios.
v-add-firewall-rule ACCEPT 172.19.0.0/16 11434 TCP coffeepie-chat-llm
```

Sin esto la sonda falla con conexión rechazada/timeout y el asistente responde
sólo desde la base de conocimiento — que es exactamente el síntoma silencioso
que `tools/chat-probe.mjs` existe para desenmascarar:

```bash
docker compose exec chat node tools/chat-probe.mjs
```

No hace falta tocar el túnel ni el `permitlisten`: el bind sigue siendo
`172.18.0.1` y nosotros sólo pedimos permiso para llegar a él.

### Las trampas ya pagadas en panelesa

Todas dan el mismo síntoma —el bot sigue vivo pero deja de parafrasear—, porque
la ruta se traga los fallos del modelo a propósito:

1. **`GatewayPorts clientspecified` va ARRIBA de sshd_config.** Añadido con `>>`
   cae dentro del `Match User` que HestiaCP escribe al final y queda inactivo.
2. **`permitlisten` debe nombrar la MISMA IP que el `-R`**, o sshd deniega.
3. **`docker compose down` borra el bridge y mata el túnel.** Hay que reiniciar
   `vps-tunnel` en el LXC después. Un `up -d --build` sin `down` es seguro — y
   es el que usa la sección de despliegue por ese motivo.
4. **El firewall**: lo de arriba.

### Si cambias de modelo

`OLLAMA_KEEP_ALIVE=-1` es obligatorio en el LXC. Sin él Ollama descarga el
modelo a los 5 minutos y el siguiente visitante paga 10–20 s de recarga.

Referencia de rendimiento con `gemma3:12b` en esa tarjeta: ~40 tok/s de
generación, ~2 s por respuesta. Un 14B irá algo más lento; si la sonda se acerca
a los 30 s de `CHAT_TIMEOUT_MS`, vuelve al 12B.

Y como la GPU es una sola para los dos sitios, el modelo que elijas aquí afecta
a panelesa — vuelve a la sección anterior si te la saltaste.

Y como la ruta se traga los fallos del modelo a propósito, comprueba el camino
completo desde donde el servicio corre de verdad:

```bash
docker compose exec chat node tools/chat-probe.mjs
```

Imprime configuración, alcance, latencia, tokens y, si falla, las palabras
exactas del proveedor.

---

## La base de conocimiento

`data/chat-kb.json` se genera del sitio **público** con `npm run kb`. Fuentes:

- un resumen curado de qué es el servicio, escrito a mano en el generador;
- las constantes reales del frontend (`js/cp-machines.js`): qué incluye un
  Slice, la tarifa por minuto y **el catálogo de sistemas operativos** — que no
  aparece en ninguna página de marketing pero es de lo que más se pregunta;
- las páginas de marketing y legales, troceadas por `<h2>`;
- `/chat.json`, el menú guiado.

Las páginas de la aplicación con sesión (panel, machines, stream, cart,
secure-payment) están **excluidas por lista blanca**: su texto es cromado de
interfaz, describe el plano de control y no ayuda a nadie que pregunte qué es
esto. Añadir una página es un acto consciente.

```bash
npm run kb        # tras editar copy público o chat.json
npm test          # incluye la invariante de imports
node tools/kb-eval.mjs   # ¿las preguntas reales caen en la entrada correcta?
```

**Después de regenerar hay que reconstruir el contenedor**, o seguirá
respondiendo con el sitio viejo.

---

## Límites conocidos

Cosas que hoy no hace, dichas para que nadie las descubra en producción:

- **El menú guiado sólo está en español.** Las *respuestas* sí llegan en el
  idioma del visitante (la ruta se lo impone al modelo) y el cromado del panel
  está en español e inglés, pero los botones de `/chat.json` no. Con 12 idiomas
  en el sitio, es la deuda más visible.
- **En modo `kb-only` las respuestas salen en español** aunque preguntes en
  inglés: sin modelo no hay quien traduzca, y la base de conocimiento es el
  texto del sitio. Sólo pasa si el modelo está caído.
- **El recuperador es de bolsa de palabras.** Una pregunta como "cuál es la
  capital de Mongolia" puntúa igual que "how much does it cost" (2,5), porque
  "capital" es raro y "precio" es común. No hay umbral que las separe; lo que
  las separa es la regla 1 del prompt. El coste es una llamada al modelo
  desperdiciada, no una respuesta equivocada. Está medido en `tools/kb-eval.mjs`
  para que se note si algún día sube.
- **No conoce nada de la cuenta del visitante.** Es anónimo a propósito: no ve
  sesión, ni saldo, ni máquinas. Para eso está el Panel y el enlace a soporte.
