# Blueprint de producto — H&S Gestión V1

**Estado:** aprobado como dirección de implementación por la persona solicitante
el 2026-09-02; continúan pendientes las aprobaciones nominales y gates indicados
en las secciones 8 y 10  
**Fuente canónica:** `PLAN_PRIMERA_VERSION.md` del paquete de traspaso  
**Regla de precedencia:** ante contradicciones con artefactos anteriores, prevalece el plan V1. Este documento no autoriza el uso de datos reales ni la activación de reglas jurídicas.

## 1. Resumen ejecutivo

H&S Gestión V1 es una aplicación interna, responsive y utilizable como PWA para gestionar el circuito operativo de Higiene y Seguridad de obras civiles:

`obra → legajos/vencimientos → maquinaria → auditoría online/offline → desvío → corrección → verificación independiente → cierre → PDF → dashboard`

La obra es el agregado operativo principal. Contratistas, personas, documentos, maquinarias, auditorías, controles y desvíos se relacionan con ella mediante asignaciones e historial temporal. El producto busca disminuir trabajo administrativo, anticipar vencimientos y preservar evidencia verificable sin reemplazar el criterio profesional H&S ni declarar cumplimiento legal.

La primera versión es un piloto funcional para una organización activa, preparado en el modelo para múltiples organizaciones. Debe poder operar con hasta tres obras, veinticinco usuarios internos y aproximadamente 200 GB de almacenamiento. Todo desarrollo, demostración y UAT usa datos sintéticos hasta cumplir el gate previo a datos reales.

## 2. Problema y resultado esperado

### Problema

El proceso actual depende de planillas, legajos impresos y memoria operativa. Eso dificulta:

- conocer documentación faltante, rechazada o próxima a vencer;
- reconstruir quién revisó, corrigió o verificó una situación;
- continuar una auditoría interrumpida o trabajar sin conectividad;
- relacionar personas, contratistas, maquinarias y hallazgos con una obra y su etapa;
- seguir desvíos entre visitas;
- obtener una visión ejecutiva basada en hechos verificables.

### Job-to-be-done

> Necesito saber rápidamente si la operación H&S de una obra está controlada, qué vence, qué desvíos siguen abiertos y qué evidencia existe, sin depender de carpetas, planillas y memoria.

### Resultado verificable de V1

Un equipo interno puede, usando datos sintéticos:

1. crear usuarios con MFA, roles y alcance por obra;
2. configurar una obra, etapas simultáneas, contratistas, personas, documentos y maquinarias;
3. preparar un paquete offline, auditar en modo avión y sincronizar sin pérdida ni duplicación;
4. registrar un desvío, aportar corrección y lograr que otra persona lo verifique;
5. cerrar la auditoría mediante un Responsable H&S distinto de su autor;
6. generar un PDF versionado y reproducible desde el snapshot;
7. reconciliar dashboard, detalles e históricos.

## 3. Actores

| Actor | Objetivo principal | Límite de V1 |
|---|---|---|
| Administrador | Gestionar usuarios, roles, alcances, configuración y plantillas | No obtiene acceso implícito a datos operativos fuera de su alcance |
| Técnico H&S | Mantener obras asignadas, contratistas, personas, documentos y maquinarias | No cierra auditorías ni verifica sus propios desvíos |
| Auditor | Crear, continuar y finalizar auditorías; registrar controles y desvíos | No cierra la auditoría ni verifica/cierra desvíos propios |
| Responsable H&S | Revisar auditorías y verificar/cerrar desvíos ajenos | Debe ser distinto del autor para el cierre final |
| Editor normativo | Crear fuentes y versiones de reglas | No publica su propia versión |
| Aprobador normativo | Publicar versiones creadas por otra persona | Rol funcionalmente deshabilitado hasta contar con validador H&S/legal |
| Contratista | Entidad gestionada | No se autentica ni tiene portal en V1 |

Los permisos detallados y la separación de funciones están en `rbac-y-journeys.md`.

## 4. Alcance de V1

### Incluido

- una organización operativa y modelo con `organization_id` para aislamiento futuro;
- hasta tres obras y veinticinco usuarios internos;
- obras con varias etapas activas e historial temporal;
- contratistas y personas como entidades con asignaciones temporales;
- documentos versionados, revisión y vigencia derivada;
- maquinaria, operadores, documentos, inspecciones y estado operativo;
- auditorías online con autosave, snapshot de checklist y control optimista;
- PWA y paquete offline de una obra seleccionada, cifrado y válido durante siete días;
- desvíos, evidencia, corrección y verificación independiente;
- auditoría finalizada inmutable y cierre por otro usuario autorizado;
- PDF parametrizado, versionado y con conformidad simple, no firma digital certificada;
- dashboard de hechos operativos y resultado no jurídico;
- API REST `/api/v1`, OpenAPI, errores Problem Details, ETag e idempotencia;
- cuentas internas, cookies seguras, MFA TOTP obligatorio y recuperación administrada;
- almacenamiento privado S3-compatible, cuarentena, validación de archivo y antivirus;
- motor normativo determinístico y versionado con reglas sintéticas activables;
- inventario de fuentes reales sólo como referencias pendientes de validación e inactivas;
- audit log append-only para acciones sensibles;
- despliegue en una VM Linux dentro de Hyper-V y un único ambiente permanente de producción.

### Fuera de V1

- firma digital certificada;
- IA, OCR o decisiones automáticas de cumplimiento;
- portal o login de contratistas;
- notificaciones multicanal;
- migración Excel generalizada;
- analítica avanzada;
- más de una organización operando en producción;
- activación de reglas jurídicas reales sin validación profesional;
- declaraciones de “cumplimiento legal”.

### Resolución de contradicciones previas

Estas decisiones ya están resueltas por el plan V1 y no deben reabrirse sin un ADR aprobado:

- offline completo es parte de V1, no una mejora parcial posterior;
- el informe PDF es parte del circuito obligatorio de V1;
- el motor normativo completo entra en V1, pero se valida con reglas sintéticas y mantiene inactivo todo corpus real;
- la UAT de V1 usa hasta tres obras sintéticas; un piloto con datos reales es posterior al gate específico;
- los documentos usan asociaciones explícitas por sujeto, no una FK polimórfica genérica;
- revisión documental y vigencia son dimensiones separadas;
- personas y maquinarias se vinculan temporalmente con contratistas y obras.

## 5. Principios y restricciones

### Dominio

- La obra es el agregado principal de operación.
- Una obra puede tener varias etapas activas.
- Maestros admiten baja lógica; auditorías, versiones, evidencias, reportes y logs históricos no se sobrescriben.
- `NO_CUMPLE` crea o enlaza un desvío.
- `NO_APLICA` y `NO_VERIFICADO` requieren motivo.
- El creador de un desvío no puede verificarlo ni cerrarlo.
- El Responsable H&S que cierra una auditoría debe ser distinto de su autor.
- Toda auditoría fotografía las versiones de controles y referencias normativas utilizadas.

### Seguridad y privacidad

- Denegación por defecto y mínimo privilegio por organización y obra.
- UUID y timestamps UTC; presentación en zona horaria argentina.
- DNI/CUIL, si se habilitan, se conservan recuperables mediante cifrado autenticado
  de sobre; revelar el valor exige scope, `pii.view`, propósito y audit log.
- La comparación/unicidad exacta usa un HMAC keyed, normalizado y separado. Es
  pseudonimización no reversible, no anonimización, no se expone y no admite
  búsqueda parcial.
- Contraseñas usan Argon2id salado; archivos, snapshots e informes usan SHA-256
  sólo como huella de integridad. Ninguno sustituye el cifrado de PII ni RLS.
- Archivos privados además validan MIME real, tamaño, cuarentena y antivirus.
- No se incorporan secretos al repositorio.
- Ningún seed, fixture, captura, log o demo contiene datos personales reales.
- Los dispositivos no administrados reciben datos mínimos y enmascarados; nunca documentos completos ni galerías históricas.

### Offline

- Una auditoría activa tiene un solo editor y una sola instalación de dispositivo.
- El paquete dura siete días y exige autenticación online al vencer.
- IndexedDB se cifra con AES-GCM y una clave derivada de contraseña offline independiente.
- Fotos y mutaciones usan UUID e idempotency keys; las fotos se purgan tras una sincronización confirmada.
- El servidor es autoridad para maestros.
- No se aplica “último cambio gana”; conflictos residuales pasan a revisión humana.
- La sincronización se inicia en primer plano al recuperar conexión y no depende de Background Sync.

### Normativa

- La DSL es JSON, determinística y limitada a operadores permitidos.
- Una evaluación sólo devuelve `APLICA`, `NO_APLICA` o `INDETERMINADO`.
- Ninguna evaluación afirma cumplimiento legal.
- Fuente, jurisdicción, versión, vigencia, aplicabilidad y aprobación independiente son obligatorias para publicar.
- Mientras no exista validador H&S/legal, las reglas jurídicas permanecen inactivas y marcadas `PENDIENTE_VALIDACION_NORMATIVA`.

## 6. Supuestos y dependencias

| Supuesto o dependencia | Tratamiento en V1 | Estado |
|---|---|---|
| Una organización activa | Se prepara aislamiento para varias, pero sólo una opera | **ACEPTADO_POR_SOLICITANTE; APROBADOR_NOMINAL_PENDIENTE** |
| Límite de tres obras y veinticinco usuarios | Dimensionamiento y UAT se diseñan para esos máximos | **ACEPTADO_POR_SOLICITANTE; APROBADOR_NOMINAL_PENDIENTE** |
| Aproximadamente 200 GB de datos | La opción A conserva una VM de 1 TB cifrado para crecimiento, snapshots y operación | **OPCION_A_APROBADA; HOST_PENDIENTE** |
| Hyper-V disponible en el servidor | Producción usa una VM Ubuntu Server LTS | **PENDIENTE_VERIFICACION_INFRAESTRUCTURA** |
| Dominio y DNS disponibles | Necesarios para HTTPS público | **PENDIENTE_DATOS_DEL_SERVIDOR** |
| GitHub/GHCR privados disponibles | CI publica imágenes inmutables desde tags firmados | **PENDIENTE_APROBACION_REPOSITORIO** |
| Un único ambiente permanente | CI usa stacks efímeros; se acepta riesgo residual sin staging | **PENDIENTE_APROBACION_OPERACIONES** |
| Validador H&S/legal no disponible inicialmente | Corpus jurídico real permanece inactivo | Confirmado por alcance; falta nombrar responsable futuro |
| Backup externo no disponible inicialmente | Se prohíben datos reales | Bloqueo explícito, no degradable |

## 7. Dataset completamente sintético

### 7.1 Reglas de generación

El dataset de desarrollo y UAT se genera desde código versionado y debe ser:

- **determinístico:** misma versión de seed y mismo reloj de referencia producen los mismos casos;
- **reiniciable:** una base vacía puede poblarse sin pasos manuales;
- **obviamente ficticio:** nombres incluyen “Sintética/o” o “Demo”; correos usan `example.invalid`;
- **sin copia ni transformación de fuentes reales:** no se transcriben nombres, identificadores, teléfonos, direcciones, firmas, observaciones, fotos ni metadatos de documentos reales;
- **sin archivos personales:** adjuntos de prueba se generan localmente con texto ficticio y marcas de agua `DATOS SINTETICOS`;
- **temporalmente estable:** fechas relativas se calculan contra `SEED_REFERENCE_INSTANT`, no contra la fecha actual;
- **seguro para logs y screenshots:** los valores visibles siguen siendo sintéticos aun cuando fallen redacciones.

El PDF sensible del paquete de traspaso no es una fuente de seed y no debe copiarse, abrirse desde scripts, indexarse ni ingresar al repositorio canónico.

### 7.2 Reloj y convenciones

- `SEED_REFERENCE_INSTANT`: `2026-01-15T15:00:00Z`.
- Zona de presentación: `America/Argentina/Buenos_Aires`.
- UUID: namespace exclusivo de fixtures; nunca se reutilizan IDs productivos.
- Identificadores personales visibles: tokens no válidos como `PERSONA-DEMO-001`; no se generan DNI/CUIL plausibles.
- Correos: `rol+NN@example.invalid`.
- Archivos: PDF/PNG/TXT generados para tests, sin firmas ni logos de terceros.
- Normativa activa: sólo reglas con claves `SYN-*` y fuente `FUENTE_SINTETICA_DE_PRUEBA`.

### 7.3 Inventario mínimo

| Entidad | Cantidad base | Casos obligatorios |
|---|---:|---|
| Organization | 2 | una activa y una organización señuelo para probar aislamiento; la segunda nunca opera en UAT |
| Users | 10 | todos los roles, usuario multirol, usuario sin scope, sesión revocada, MFA pendiente |
| Worksites | 4 | tres de la organización activa y una señuelo; etapas simultáneas e historial |
| Contractors | 6 | asignaciones activas, futuras y finalizadas |
| People | 18 | cambios temporales de contratista/obra y una persona sin asignación vigente |
| Document types/requirements | 10/14 | obligatorios, opcionales, por etapa y por sujeto |
| Documents/versions | 28/36 | faltante, pendiente, aprobado, rechazado, vigente, por vencer y vencido; nunca sobrescribir versión |
| Machines | 8 | los tres estados operativos, cambio de obra y operador sin habilitación vigente |
| Audits | 7 | borrador, en curso, finalizada y cerrada; una interrumpida y una con snapshot histórico |
| Audit controls | 40 o más | todos los resultados, motivos obligatorios y controles no aplicables |
| Findings | 12 | criticidades diversas, vencidos, en corrección, pendientes de verificación y cerrados por tercero |
| Evidence/corrections | 18/8 | varias versiones, archivo en cuarentena y evidencia rechazada |
| Offline packages | 5 | vigente, vencido, revocado, conflicto y sincronización idempotente repetida |
| Report templates/reports | 2/4 | generación exitosa, reintento, versión completa y redactada |
| Regulatory rules | 8 | sólo sintéticas: aplicable, no aplicable, indeterminada, retirada y autoaprobación rechazada |
| Audit log events | 60 o más | auth, permisos, estados, archivos, exportaciones y rechazos de autorización |

### 7.4 Escenarios de aceptación incluidos

1. Un usuario de otra organización intenta descubrir una obra mediante UUID conocido y recibe una respuesta no reveladora.
2. Un Técnico H&S completa el alta de una obra sin planillas externas.
3. Una nueva versión documental conserva la anterior y recalcula vigencia.
4. Un archivo con MIME inconsistente permanece en cuarentena y no puede descargarse.
5. Una auditoría se reanuda después de cerrar el navegador sin duplicar controles.
6. Un paquete válido completa una auditoría en modo avión y sincroniza dos veces sin duplicación.
7. Un paquete vencido o dispositivo revocado no puede reabrirse ni sincronizar sin reautenticación/revisión.
8. Dos cambios concurrentes producen conflicto explícito, no “último cambio gana”.
9. El autor de un desvío intenta cerrarlo y recibe `409` o `403` según corresponda.
10. Una auditoría cerrada y su PDF no pueden alterarse; regenerar crea una nueva versión trazable.
11. Una regla sin fuente, versión o aprobación independiente no puede activarse.
12. Los totales del dashboard reconcilian con las consultas de detalle.

### 7.5 Control automático de privacidad del dataset

CI debe bloquear:

- correos fuera de dominios reservados de prueba;
- identificadores personales con formato productivo en seeds, fixtures o snapshots;
- archivos binarios no declarados en un inventario sintético;
- referencias al nombre o hash de fuentes sensibles del paquete de traspaso;
- secretos, tokens o credenciales reales;
- logs y screenshots que no lleven la marca de entorno sintético.

Los falsos positivos se resuelven mediante revisión y excepción versionada; nunca desactivando el control global.

## 8. Gate previo a datos reales

No se pueden importar ni capturar datos reales hasta que exista evidencia de todos estos puntos:

- backup cifrado fuera del servidor;
- restore completo probado y documentado;
- política aprobada de privacidad, retención y eliminación;
- matriz de acceso y exportación aprobada;
- gestión y rotación de claves definida;
- hardening final y revisión de seguridad;
- capacitación de usuarios;
- responsable de tratamiento/custodia identificado;
- consentimiento, base legal y textos contractuales revisados por quien corresponda.

Este gate no admite una excepción informal.

## 9. Métricas de producto

- tiempo por auditoría;
- tiempo de preparación y revisión documental;
- vencimientos detectados anticipadamente;
- tiempo de cierre y cantidad de desvíos vencidos;
- uso semanal y frecuencia móvil/offline;
- errores, reintentos y conflictos de sincronización;
- consistencia entre dashboard y consultas de detalle;
- intención de pago y feedback cualitativo.

Las definiciones, experimentos y umbrales se especifican en `negocio-y-validacion.md`.

## 10. Aprobaciones y gates pendientes para cerrar Hito 0

La aceptación explícita del blueprint y de la opción A por la persona solicitante
queda registrada con fecha 2026-09-02. Como no se informó nombre ni rol
organizacional, no se atribuye esa decisión a responsables nominales ni sustituye
las validaciones independientes de seguridad/privacidad y H&S/legal.

| Decisión | Aprobador requerido | Estado |
|---|---|---|
| Alcance y límites cuantitativos de V1 | Product owner | **ACEPTADO_POR_SOLICITANTE; APROBADOR_NOMINAL_PENDIENTE** |
| Roles, permisos y separación de funciones | Responsable H&S + seguridad | **PENDIENTE** |
| Dataset sintético y prohibición de datos reales | Product owner + privacidad | **PENDIENTE** |
| Estrategia de aislamiento RLS para futura multitenencia | Arquitectura + seguridad | **ACEPTADA_POR_SOLICITANTE; VALIDACION_NOMINAL_PENDIENTE** |
| Modelo de PII: cifrado recuperable, HMAC pseudónimo y retención | Privacidad + seguridad | **ACEPTADO_CON_ACLARACION; CUSTODIO_Y_VALIDACION_FORMAL_PENDIENTES** |
| Criticidad configurable y versionada | Product owner + Responsable H&S | **ACEPTADA_POR_SOLICITANTE; VALIDACION_NOMINAL_PENDIENTE** |
| VM, capacidad, ambiente único y operación | Infraestructura/operaciones | **OPCION_A_APROBADA; APROVISIONAMIENTO_Y_OWNER_PENDIENTES** |
| Gate de backup/restore antes de datos reales | Operaciones + seguridad + privacidad | **PENDIENTE** |
| Estado inactivo del corpus normativo real | Responsable H&S/legal | **PENDIENTE** |

El documento puede implementarse como blueprint mientras está en revisión, pero el gate de Hito 0 sólo se considera aprobado cuando estas decisiones tienen responsable, fecha y evidencia de aceptación.
