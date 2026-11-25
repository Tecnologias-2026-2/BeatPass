# Cambios del panel y del registro — BeatPass v2

## Publicación administrativa sin revisión propia

El administrador general entra a **Panel → Crear evento**, guarda un borrador y, desde **Mis eventos y borradores**, pulsa **Publicar ahora**. La API valida que la cuenta tenga rol `administracion` y que sea la propietaria del borrador. También comprueba fecha futura y que una revisión nueva no reinicie inventario con cupos vendidos o reservados. El evento queda público inmediatamente tras confirmar la operación.

Los organizadores normales **siguen enviando a revisión**. Para ellos el botón de publicación directa no aparece y la API responde 403 si intentan utilizarlo.

Ruta: `POST /api/organizers/events/{event_id}/publish` → `backend/events.py` → `EventRevision` y `TicketInventory`.

## Rechazados

En **Administración → Solicitudes y rechazados → Rechazados** aparecen cuentas de organizadores y eventos cuya última versión fue rechazada. **Volver a pendientes** no aprueba ni publica: devuelve la solicitud a la bandeja Pendientes para una nueva revisión. Se registra la recuperación en `audit_logs` y se limpian el motivo, la fecha y el revisor de la decisión anterior.

Rutas: `GET /api/admin/applications/rejected`, `POST /api/admin/applications/{id}/restore`, `GET /api/admin/events/rejected`, `POST /api/admin/events/reviews/{id}/restore`.

## Formulario con errores identificables

Al guardar, `js/pages/admin-events.js` comprueba campos obligatorios, mínimos (título 3, resumen 8, descripción 15, recinto y ciudad 2 caracteres), valores enteros de cupos y precios y rangos. Los campos inválidos reciben borde rojo y mensaje bajo el control; la corrección elimina el aviso. Los errores de validación 422 de FastAPI también se asocian al campo correspondiente. **La validación del servidor se mantiene como autoridad**.

## Registro inmediato

Registrar una cuenta `cliente` o solicitar ser `organizador` ya no exige verificar el correo: el usuario recibe un JWT de cliente y entra a Destacados. Los solicitantes de organizador no pueden administrar eventos hasta ser aprobados. Las contraseñas siguen guardándose mediante hash y se conserva el correo como dato no verificado (`email_verified_at = NULL`). La recuperación de contraseña sigue enviando un correo si existe un remitente configurado.

**Importante:** registrar una dirección no comprueba que la persona sea su propietaria. Para evitar elevar privilegios de cuentas sin comprobación de identidad, **aceptar invitaciones administrativas sigue requiriendo verificación explícita del correo** y contraseña correcta. Desde `pages/verify-email.html` se puede solicitar la verificación opcional. Antes de un lanzamiento real conviene reconsiderar esta política y aplicar controles antiabuso para evitar registros masivos y suplantaciones.

## Cómo probarlo

1. Con una cuenta normal crea una cuenta: debe entrar a Destacados sin correo obligatorio. Una solicitud de organizador debe seguir pendiente.
2. Como administrador crea un evento futuro, guarda el borrador y pulsa **Publicar ahora**. Debe aparecer en Catálogo sin revisión.
3. Como organizador crea un evento: debe poder **Enviar a revisión**, nunca **Publicar ahora**.
4. Rechaza un organizador y un evento desde Solicitudes. En **Rechazados**, devuélvelos a Pendientes; confirma que siguen sin rol/publicación hasta otra aprobación.
5. En Crear evento escribe un título de dos caracteres y pulsa Guardar: aparece el borde rojo y **Mínimo 3 caracteres**. Corrígelo: el aviso desaparece.

**Pruebas automatizadas:** `python -m pytest -q`. **Recursos compartidos:** `python tools/build_components.py --check`.

## GitHub y Render

El proyecto debe estar en la **raíz del repositorio**: `render.yaml`, `.github/`, `backend/`, `pages/`, `js/`, `components/`, `css/` y `assets/` en el primer nivel, no dentro de una carpeta adicional. No subas `backend/instance/`, `.env`, SQLite ni datos secretos.

Los cambios son archivos para importar a GitHub: no se han publicado ni desplegado automáticamente.
