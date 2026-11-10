# Estado funcional BeatPass

## Implementado en API; preparado para PostgreSQL (validación remota pendiente)

Registro con correo verificado, inicio de sesión, roles de cliente/organizador/administración, solicitudes y revisiones de organizador, perfil, recuperación, invitaciones administrativas, creación y revisión de eventos, portadas, publicación aprobada, catálogo y detalles reales, inventario por zonas, carrito, reservas temporales, pedidos y boletos de prueba.

## Disponible en entorno restringido de pruebas

Mercado Pago Sandbox se activa manualmente con variables `PAYMENT_MODE=mercadopago_sandbox`, `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `PUBLIC_API_URL`, `PUBLIC_FRONTEND_URL`. No cobra dinero real; el webhook debe confirmarse con el proveedor. Demo checkout se deshabilita en despliegue, salvo configuración administrativa explícita; no emitir boletos oficiales.

## Funciones pendientes de próximas fases

Pagos reales con conciliación y reembolsos, QR oficiales con control de acceso y revocación, selección de asientos, transferencias, reventa, listas de espera, favoritos, notificaciones, equipos de organizadores, estadísticas, MFA, sistema de copias de seguridad, almacenamiento de objetos, pruebas de concurrencia PostgreSQL y requisitos legales/comerciales.
