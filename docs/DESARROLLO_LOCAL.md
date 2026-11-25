# Desarrollo local de BeatPass

## Por qué aparece `405 (Method not allowed)` al registrarse

El frontend llama a la API con la ruta relativa `/api/...` (`js/core/config.js`).
Si la web se abre con un servidor puramente estático —por ejemplo Live Server o
Live Preview en `http://127.0.0.1:5500`—, el `POST /api/auth/register` llega a
ese servidor y no a FastAPI. Live Server solo sirve archivos y responde
`405 Method not allowed`: no es un error del backend.

`js/core/config.js` ya resuelve el caso de los servidores estáticos conocidos
(`:5500`, `:8001` y `file://`): apunta directamente a `http://<host>:8010/api`.
La API acepta esos orígenes en `APP_ENV=local`, así que el registro funciona sin
proxy. Solo hay que arrancar la API en el puerto 8010.

## Opción recomendada: servidor local con proxy

```powershell
# Terminal 1: API
$env:APP_ENV='local'
python -m uvicorn backend.main:app --reload --port 8010

# Terminal 2: web + /api en el mismo origen
python tools/serve_local.py
```

Abre `http://127.0.0.1:8080/index.html`.

`tools/serve_local.py` sirve la raíz del proyecto y reenvía `/api` a la API.
No expone `backend/`, `tests/`, `tools/`, `migrations/` ni carpetas de Git.
Opciones útiles:

```powershell
python tools/serve_local.py --port 5500
python tools/serve_local.py --api http://127.0.0.1:8000
```

## Opción Live Server / Live Preview

1. Arranca la API con `APP_ENV=local` en el puerto **8010**.
2. Abre la página con Live Server (`http://127.0.0.1:5500`).

Si la API está en otro puerto, abre la web con el parámetro `?api=`:

```
http://127.0.0.1:5500/pages/register.html?api=http://127.0.0.1:8000/api
```

El parámetro se conserva solo en esa página; para un cambio global define
`window.BEATPASS_API_BASE_URL` antes de cargar `js/core/config.js`.

Con `APP_ENV=local` la API acepta cualquier origen `http://localhost:<puerto>`,
`http://127.0.0.1:<puerto>` y `null` (archivos abiertos con `file://`). En el
despliegue solo se acepta lo indicado en `ALLOWED_ORIGINS`.

## Comprobaciones rápidas

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
Invoke-WebRequest http://127.0.0.1:8080/index.html -UseBasicParsing
python -m pytest -q
```

La base local vive en `backend/instance/beatpass_v2.db` (ignorada por Git).
Para empezar de cero, detén la API, borra ese archivo y vuelve a arrancarla.

## Cuenta de administración local

```powershell
$env:APP_ENV='local'
python -m backend.cli create-admin --email admin@beatpass.local
```

El comando pide la contraseña de forma interactiva y no la guarda en el código.
