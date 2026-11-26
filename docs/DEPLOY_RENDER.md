# BeatPass — Despliegue en Render

El frontend y la API se despliegan desde GitHub con `render.yaml`. Este archivo, `backend/` y `.github/` deben estar en la raíz del repositorio; no dentro de una carpeta adicional.

## Preparación

1. Crear repositorio privado; comprobar que no contiene `.env`, `.db`, secretos ni `backend/instance/`.
2. Importar Blueprint `render.yaml` en Render. Configurar las variables marcadas `sync: false` en el panel.
3. En la API establecer `PUBLIC_FRONTEND_URL=https://<web>.onrender.com` y `PUBLIC_API_URL=https://<api>.onrender.com`. `ALLOWED_ORIGINS` puede ampliar la lista, pero `backend/config.py` ya autoriza los dominios públicos del proyecto (`github.io` y `*.onrender.com` propios), así que la web de Render puede llamar a la API sin bloqueo CORS.
4. La API sirve también la web generada en `/`: el build ejecuta `tools/build_static.py`, que inyecta `API_BASE_URL` y retira los eventos de ejemplo. Así frontend y backend comparten origen y no dependen de CORS. El servicio web estático se mantiene para el dominio `beatpass-1.onrender.com`.
5. Crear dominio remitente y verificarlo en Resend; asignar `MAIL_FROM` al dominio verificado y `RESEND_API_KEY` a la clave secreta. La recuperación de contraseña y las verificaciones opcionales para invitaciones administrativas se envían por HTTPS. El registro público no envía correos obligatorios.
6. Mantener `PAYMENT_MODE=disabled` hasta validar el flujo real de Sandbox; los QR no son entradas de acceso.

## Administrador inicial para QA

`render.yaml` declara el correo `pruebas@beatpass.com`, NO una contraseña. Para aprovisionar la cuenta, introducir `BEATPASS_BOOTSTRAP_ADMIN_PASSWORD` como secreto de Render, establecer temporalmente `BEATPASS_BOOTSTRAP_ADMIN_ENABLED=true` y volver a desplegar. El comando crea un usuario nuevo con roles `cliente` y `administracion`, contraseña con hash Argon2id y correo marcado como verificado mediante aprovisionamiento privilegiado. No modifica cuentas existentes.

**Inmediatamente después** poner `BEATPASS_BOOTSTRAP_ADMIN_ENABLED=false`, eliminar la variable de contraseña y volver a desplegar. Como el correo de QA no existe, no puede recibir enlaces reales de recuperación; utiliza una cuenta administradora con buzón verificable antes de producción. La contraseña compartida anteriormente debe reemplazarse antes de abrir la web a terceros.

## Consideraciones antes de producción

- Render Postgres Free expira después de 30 días y carece de copias de seguridad; no utilizarlo para datos de clientes permanentes.
- Las portadas se guardan en PostgreSQL; planificar almacenamiento de objetos al aumentar volumen.
- FastAPI debe servir HTTPS a través de Render; cookies y CORS se verifican desde las direcciones reales.
- La reserva de inventario, Mercado Pago TEST y los boletos demo no equivalen a ventas definitivas ni a entradas válidas.
- Programar `python -m backend.cli expire-holds` como Cron Job de Render para liberar reservas vencidas; la limpieza perezosa ya se ejecuta en cada lectura de cupos.
