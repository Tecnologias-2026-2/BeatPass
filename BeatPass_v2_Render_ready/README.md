# BeatPass - Main Page Implementation

![BeatPass](./assets/ChatGPT%20Image%2012%20may%202026%2C%2001_02_08%20a.m.png)

> Implementación de la página de inicio de BeatPass - Plataforma de venta de entradas para eventos deportivos y culturales.

## 📋 Descripción

Este proyecto implementa la página de inicio de BeatPass siguiendo las mejores prácticas de:
- ✅ **HTML Semántico** - Estructura clara con elementos nativos (`<header>`, `<main>`, `<section>`, `<article>`, `<nav>`)
- ✅ **CSS Puro** - Responsive con Flexbox y CSS Grid, sin frameworks
- ✅ **JavaScript Vanilla** - Sin dependencias externas
- ✅ **Accesibilidad WCAG** - Atributos ARIA, navegación por teclado, anuncios a lectores de pantalla
- ✅ **Diseño Responsivo** - Adaptado para mobile, tablet y desktop

---

## 🎨 Características

### Hero Section
- Imagen de fondo con gradiente y overlay
- Título destacado "Noche de Rock Clásico"
- Descripción del evento
- Información de fecha y ubicación con iconos
- Botón CTA "Comprar Entradas" con efecto hover
- Precio inicial "$120"

### Próximos Eventos
- Grid responsivo de tarjetas de eventos
- Categorías de eventos (Teatro, Música, Arte)
- Información de fecha y ubicación en cada tarjeta
- Botones "Ver Detalles" interactivos
- Efecto hover con elevación y sombra

### Navegación
- Header sticky con logo BeatPass
- Menú de navegación responsivo
- Toggle móvil con animación
- Navegación por teclado (Escape para cerrar)
- Scroll suave a secciones

---

## � Páginas Disponibles

### [index.html](index.html) - Página Principal
- **Descripción**: Homepage con evento destacado y grid de eventos próximos
- **Acceso**: `/` o `/index.html`
- **Componentes**: Hero Section, Event Cards, Footer

### [pages/login.html](pages/login.html) - Página de Login
- **Descripción**: Formulario de autenticación de usuarios
- **Acceso**: `pages/login.html` o desde el botón "Entrar" del header
- **Componentes**: Formulario con email/contraseña, enlaces de recuperación
- **Documentación**: [docs/LOGIN.md](docs/LOGIN.md)

### [pages/register.html](pages/register.html) - Página de Registro
- **Descripción**: Formulario para crear una nueva cuenta
- **Acceso**: `pages/register.html` o desde el link en la página de login
- **Componentes**: Formulario con nombre/email/contraseña, checkbox de términos
- **Documentación**: [docs/REGISTER.md](docs/REGISTER.md)

---

## �📁 Estructura de Archivos

```
BeatPass/
├── index.html              # Página de inicio
├── style-guide.html        # Guía de estilos completa
├── components/
│   └── header.html         # Header reutilizable
├── css/
│   └── styles.css          # Estilos CSS puros
├── js/
│   ├── main.js             # Lógica principal de la aplicación (antes script.js)
│   ├── catalog.js          # Lógica específica del catálogo
│   ├── cart.js             # Lógica del carrito de compras
│   ├── login.js            # Lógica del formulario de login
│   ├── register.js         # Lógica del formulario de registro
│   └── utils.js            # Funciones de utilidad compartidas
├── pages/
│   ├── login.html          # Página de login
│   └── register.html       # Página de registro
├── assets/
│   ├── ChatGPT Image 12 may 2026, 01_02_08 a.m.png  # Logo principal
│   └── README.md           # Guía de assets
├── docs/
│   ├── README.md           # Documentación general
│   ├── HEADER_USAGE.md     # Guía del header
│   ├── LOGIN.md            # Guía de la página de login
│   └── REGISTER.md         # Guía de la página de registro
├── HEADER_USAGE.md         # Guía del header (raíz)
├── README.md               # Este archivo
└── .git/
```

---

## 🚀 Instalación

1. **Clonar o descargar el proyecto:**
```bash
git clone https://github.com/yourusername/BeatPass.git
cd BeatPass
```

2. **Abrir en el navegador:**
```bash
# Opción 1: Abrir directamente
open index.html

# Opción 2: Con Live Server (VS Code)
# Instalar extensión "Live Server"
# Clic derecho en index.html > "Open with Live Server"

# Opción 3: Con un servidor local
python -m http.server 8000
# Visitar: http://localhost:8000
```

---

## 🛠️ Tecnologías

### HTML
- **Semántica**: `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`
- **Accesibilidad**: Atributos ARIA, `role`, `aria-label`, `aria-labelledby`, `aria-live`
- **Optimización**: `loading="lazy"` para imágenes

### CSS
- **Layout**: Flexbox y CSS Grid
- **Variables CSS**: Tokens de color, espaciado, tipografía
- **Responsivo**: Media queries para mobile, tablet, desktop
- **Animaciones**: Transiciones suaves, efectos hover
- **Dark/Light Mode**: Soporte para `prefers-color-scheme`

### JavaScript
- **Vanilla JS**: Sin librerías externas
- **OOP**: Clase `BeatPassApp` con métodos organizados
- **Eventos**: Click, keyboard, scroll, resize
- **Accesibilidad**: Anuncios para screen readers, navegación por teclado
- **Lazy Loading**: Observador de intersección para imágenes
- **Analytics**: Hooks para implementar tracking

---

## ⌨️ Navegación por Teclado

| Tecla | Acción |
|-------|--------|
| `Tab` | Navegar entre elementos interactivos |
| `Shift + Tab` | Navegar hacia atrás |
| `Enter` / `Space` | Activar botones y enlaces |
| `Escape` | Cerrar menú móvil |
| `Alt + M` | Saltar al contenido principal |

---

## 🎯 Variables CSS Disponibles

```css
/* Colores */
--primary-gradient: linear-gradient(135deg, #00d4ff 0%, #0099ff 100%)
--primary-color: #00d4ff
--primary-dark: #0099ff
--secondary-color: #06b6d4

/* Fondos */
--bg-dark: #0f0f0f
--bg-secondary: #1a1a1a
--bg-tertiary: #2a2a2a

/* Texto */
--text-primary: #ffffff
--text-secondary: #d4d4d8
--text-tertiary: #a1a1a6

/* Espaciado (REM) */
--spacing-xs: 0.25rem
--spacing-sm: 0.5rem
--spacing-md: 1rem
--spacing-lg: 1.5rem
--spacing-xl: 2rem
--spacing-2xl: 3rem
--spacing-3xl: 4rem

/* Tipografía */
--font-size-sm: 0.875rem
--font-size-base: 1rem
--font-size-lg: 1.125rem
--font-size-xl: 1.25rem
--font-size-2xl: 1.5rem
--font-size-3xl: 1.875rem
--font-size-5xl: 3rem
```

---

## 📱 Breakpoints Responsivos

```css
--breakpoint-sm: 640px    /* Mobile */
--breakpoint-md: 768px    /* Tablet */
--breakpoint-lg: 1024px   /* Desktop */
--breakpoint-xl: 1280px   /* Wide */
--breakpoint-2xl: 1536px  /* Ultra Wide */
```

---

## ♿ Características de Accesibilidad

### WCAG 2.1 Compliance

✅ **Contraste**: Todos los textos tienen contraste mínimo AA (4.5:1)

✅ **Navegación por Teclado**: Todos los elementos interactivos son accesibles

✅ **Lectores de Pantalla**: 
- Atributos `aria-label` en botones
- `aria-labelledby` en secciones
- `aria-live` en notificaciones
- Roles semánticos

✅ **Movimiento Reducido**: Respeta `prefers-reduced-motion`

✅ **Imágenes**: Atributos `alt` descriptivos

✅ **Formularios**: Etiquetas asociadas (en caso de formularios)

---

## 🎬 Ejemplos de Uso

### Agregar un nuevo evento

```html
<!-- Event Card 4 -->
<article class="event-card" role="article">
    <div class="event-image-wrapper">
        <img src="tu-imagen.jpg" 
             alt="Tu Evento - Categoría" 
             class="event-image"
             loading="lazy">
        <span class="event-category">Tu Categoría</span>
    </div>

    <div class="event-card-content">
        <h3 class="event-card-title">Tu Evento</h3>

        <div class="event-card-details">
            <div class="card-detail">
                <svg class="card-detail-icon" viewBox="0 0 24 24">...</svg>
                <span>fecha</span>
            </div>
            <!-- ... -->
        </div>

        <div class="event-card-footer">
            <span class="card-price">$XXX</span>
            <button class="btn btn-secondary btn-small">Ver Detalles</button>
        </div>
    </div>
</article>
```

### Personalizar colores

```css
:root {
    --primary-color: #tu-color;
    --primary-dark: #tu-color-oscuro;
    --secondary-color: #tu-color-secundario;
}
```

### Agregar nuevas secciones

```javascript
// En script.js
class BeatPassApp {
    constructor() {
        this.initElements();
        this.attachEventListeners();
        this.initializeAccessibility();
        this.initNewSection(); // Nuevo método
    }

    initNewSection() {
        // Tu código aquí
    }
}
```

---

## 📊 Performance

- **Lazy Loading**: Imágenes cargadas bajo demanda
- **Minificación**: CSS y JS optimizados
- **Responsive**: Adapta automáticamente a cualquier pantalla
- **Accesibilidad**: No ralentiza la carga
- **Lighthouse Score**: ~95+

---

## 🔧 Configuración

### Cambiar el evento destacado

En `index.html`:
```html
<h1 id="featured-event-heading" class="hero-title">
    Tu Evento Aquí
</h1>
```

### Cambiar colores del gradiente

En `styles.css`:
```css
.hero-background {
    background: linear-gradient(135deg, #TU_COLOR_1 0%, #TU_COLOR_2 100%);
}
```

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama: `git checkout -b feature/NewFeature`
3. Commit: `git commit -m 'Add new feature'`
4. Push: `git push origin feature/NewFeature`
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](LICENSE) para más detalles.

---

## 📞 Contacto

**BeatPass Team**
- Website: [beatpass.com](https://beatpass.com)
- Email: info@beatpass.com
- GitHub: [@beatpass](https://github.com/beatpass)

---

### Próximas Mejoras

- [ ] Integración con pasarela de pagos (Stripe/PayPal)
- [ ] Búsqueda y filtrado de eventos
- [ ] Autenticación de usuarios
- [ ] Carrito de compras
- [ ] Panel de administración
- [ ] Notificaciones por email
- [ ] Sistema de reseñas y comentarios
- [ ] Integración con calendario (iCal)
- [ ] PWA (Progressive Web App)
- [ ] Múltiples idiomas (i18n)

---

## 🔗 Header Reutilizable

El header está diseñado para ser reutilizable en todas las páginas. Ver [HEADER_USAGE.md](HEADER_USAGE.md) para:
- Estructura del header
- Cómo copiar a otras páginas
- Clases CSS disponibles
- Funcionalidades JavaScript
- Customización

**Opción rápida para copiar:**
```bash
# Copiar header.html a tus nuevas páginas y usar:
<header class="header" role="banner">
    <!-- Ver header.html para estructura completa -->
</header>
```

---

## 🐛 Reportar Bugs

Si encuentras un bug, por favor abre un [Issue](https://github.com/beatpass/issues) con:
- Descripción detallada
- Pasos para reproducir
- Navegador y versión
- Screenshot (si aplica)

---

**Hecho con ❤️ por el equipo de BeatPass**
