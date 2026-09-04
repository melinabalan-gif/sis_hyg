# Wireframes textuales V1

**Estado:** borrador funcional; las referencias visuales históricas no son especificaciones pixel-perfect ni fuente de datos.

## 1. Sistema de navegación

Escritorio usa barra lateral con: Mis obras, Auditorías, Desvíos, Documentación,
Personas, Contratistas, Maquinarias, Informes, Normativa y Configuración. Móvil usa
barra inferior para Obras, Auditoría activa, Pendientes y Más. Toda vista muestra
organización, obra/scope activo, estado de conexión y usuario.

Banner permanente en desarrollo/UAT:

```text
┌────────────────────────────────────────────────────────────┐
│ PROTOTIPO · DATOS 100 % SINTÉTICOS · SIN VALIDEZ OPERATIVA │
└────────────────────────────────────────────────────────────┘
```

## 2. Pantallas comunes

### Login y MFA

```text
┌─ H&S Gestión ─────────────────────┐
│ Correo [________________________] │
│ Contraseña [____________________] │
│ [Ingresar]                        │
│                                   │
│ Paso 2: Código TOTP [______]      │
│ [Verificar] [Usar código respaldo]│
└───────────────────────────────────┘
```

Estados: credenciales inválidas no reveladoras, bloqueo temporal, MFA requerido,
sesión expirada y recuperación administrada. Nunca recordar contraseña offline.

### Mis obras / dashboard

```text
┌─ Mis obras ────────────── [Buscar] [Filtros] ───────────────┐
│ Obra Sintética Norte       Etapas: Estructura + Instalación │
│ Docs: 2 vencidos · Desvíos: 3/1 vencido · Máquinas: 1 obs. │
│ Última auditoría: 12 días                     [Abrir]       │
├─────────────────────────────────────────────────────────────┤
│ Obra Sintética Río         Sin alertas no equivale a legal  │
└─────────────────────────────────────────────────────────────┘
```

Sin semáforo “óptimo”. Cada cifra es enlace a su consulta de detalle. Estados:
loading skeleton, vacío por falta de scope, error reintentable y sin conexión con
timestamp del último snapshot.

## 3. Gestión de obra en escritorio

### Detalle de obra

Cabecera: código/nombre sintético, jurisdicción, responsables y acciones según
permiso. Tabs: Resumen, Información, Etapas, Contratistas, Personas, Documentos,
Maquinarias, Auditorías, Desvíos e Histórico.

Resumen dispone tarjetas reconciliables y paneles de próximos vencimientos,
desvíos prioritarios, etapas activas y última auditoría. Cada panel muestra
“actualizado a” y no emite conclusiones legales.

### Etapas

Timeline con múltiples carriles para simultaneidad. Formulario: catálogo, inicio,
fin opcional, sector/notas y ETag. Solapamiento permitido; rangos invertidos o
duplicados incompatibles se marcan inline.

### Contratistas y personas

Tabla filtrable con intervalos de asignación. Drawer de persona enmascara
identificador y muestra “ver dato protegido” sólo con permiso y confirmación de
propósito. Historial nunca se reemplaza al cambiar de contratista/obra.

### Documentos y vencimientos

```text
[Faltantes 4] [Pendientes 2] [Rechazados 1] [Por vencer 3] [Vencidos 2]
Sujeto | Tipo | Revisión | Vigencia derivada | Versión | Vence | Acciones
```

Upload muestra progreso → cuarentena → análisis → disponible/rechazado. La ficha
lista todas las versiones, hash, MIME real y revisiones. Reemplazar archivo crea
otra versión.

### Maquinarias

Tarjetas/tabla con tipo, identificador sintético, contratista, obra, operador,
documentos e inspección. Un cambio de estado abre modal con transición, motivo y
evidencia; `FUERA_DE_SERVICIO` es inequívoco y no depende sólo del color.

## 4. Auditoría móvil

### Preparar auditoría/paquete

```text
Obra Sintética Norte       Online ●
Checklist v3 · 48 controles
Datos incluidos: mínimos y enmascarados
Vence: 7 días desde descarga
[Definir contraseña offline] [Descargar paquete]
```

Muestra almacenamiento requerido/disponible, dispositivo, caducidad y opción de
revocar/purgar. Advierte que olvidar la contraseña exige purgar y descargar otra vez.

### Auditoría activa

```text
← EPP                         Offline ◌ · guardado local
Progreso 12/48  [████░░░░]

¿Se observa uso del EPP requerido?
[Cumple] [No cumple]
[No aplica] [No verificado]
Motivo/observación [________________]
[Foto] [Crear desvío]

[Anterior]                         [Siguiente]
```

Botones mínimos de 44 px, texto además de color y confirmación háptica/visual.
`NO_CUMPLE` abre sheet de desvío o permite enlazar uno existente; motivos aparecen
obligatorios donde corresponde. Header muestra `guardado local`, `sincronizando`,
`confirmado` o `conflicto`, nunca un único “guardado” ambiguo.

### Asistencia y pendientes

Lista de personas enmascaradas con toggle presente/ausente y contratista. Los
pendientes anteriores se pueden consultar sin galerías históricas offline.

### Resumen/finalización

Agrupa incompletos, no cumple sin desvío, motivos faltantes, uploads pendientes y
conflictos. El botón Finalizar queda deshabilitado con explicación accionable.

### Centro de sincronización

```text
Mutaciones: 17 confirmadas · 2 pendientes · 1 conflicto
Fotos: 4 confirmadas/purgadas · 1 pendiente cifrada
[Reintentar] [Ver conflicto] [Purgar paquete]
```

Conflicto compara valor del servidor, cambio local, timestamps/actores y permite a
RHS aceptar/reformular mediante una nueva mutación auditada; no ofrece LWW.

## 5. Desvíos, informes y normativa

### Desvío

Timeline append-only: creación, asignaciones, correcciones, evidencias,
verificaciones y transiciones. CTA varía por rol: Corregir, Enviar a verificación,
Verificar/Rechazar. Si el actor está segregado, se explica por qué no puede cerrar.

### Informe y conformidad

Vista previa identifica snapshot, plantilla, versión, hash y alcance
completo/redactado. Conformidad solicita nombre, rol, consentimiento y trazo, con
texto visible: “No constituye firma digital certificada”.

### Consola normativa

Tres paneles: fuentes/versiones, editor DSL validado y simulador con casos
sintéticos. El estado `PENDIENTE_VALIDACION_NORMATIVA` es textual y bloquea
publicación. Historial muestra creador y aprobador diferentes.

## 6. Estados transversales obligatorios

Cada pantalla debe diseñar y probar:

- carga inicial y revalidación sin borrar contenido útil;
- colección vacía por datos o por falta de scope, sin confundir ambas;
- validación por campo y resumen accesible;
- `401` con reautenticación conservando trabajo local seguro;
- `403/404` no revelador;
- `409/412/423` con pasos de resolución;
- API/servicio degradado y reintento con idempotencia;
- offline, paquete por vencer/vencido, dispositivo revocado y poco espacio;
- éxito confirmado por servidor frente a guardado sólo local;
- accesibilidad: teclado, foco, lector, contraste y texto independiente del color.

