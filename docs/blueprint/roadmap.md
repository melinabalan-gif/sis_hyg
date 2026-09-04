# Backlog, dependencias y gates V1

## Priorización

- **P0:** necesario para el circuito aceptado o su seguridad/integridad.
- **P1:** mejora de uso incluida sólo si no compromete gates P0.
- **P2:** fuera de V1; se conserva como roadmap, no se implementa anticipadamente.

Cada historia hereda DoR/DoD de `../operations/calidad-y-operacion.md`.

## H0 — Blueprint y gobierno

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H0-01 P0 | Como equipo, tenemos alcance, exclusiones y dataset sintético inequívocos | plan V1 |
| H0-02 P0 | Como seguridad, aprobamos RBAC/SoD, PII, offline, threat model y riesgos | H0-01 |
| H0-03 P0 | Como desarrollo, contamos con context map, ERD, estados, API y wireframes sin decisiones implícitas | H0-01 |
| H0-04 P0 | Como owner, priorizamos historias/gates y registramos ADR/decisiones | H0-02/03 |
| H0-05 P0 | Como operaciones, disponemos de repo privado y Linux/Compose capaz de ejecutar CI/smoke | DEC-001/002 |

**Gate:** todos los documentos completos; aprobaciones producto, seguridad,
H&S/legal y operaciones; repo/entorno con evidencia; cero datos restringidos.

## H1 — Baseline reproducible

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H1-01 P0 | Locks Python/Node y runtimes/digests fijados; instalación frozen no cambia archivos | H0 gate |
| H1-02 P0 | API/web compilan con lint, formato, tipos y tests | H1-01 |
| H1-03 P0 | Alembic migra DB vacía y anterior; runtime no usa `create_all` | H1-01 |
| H1-04 P0 | Compose interno tiene healthchecks y migrador one-shot | H1-02/03 |
| H1-05 P0 | live responde sin DB; ready 200/503 según DB/schema | H1-04 |
| H1-06 P0 | portada marca datos 100 % sintéticos y no expone `/obras` hardcodeada | H1-02 |
| H1-07 P0 | CI ejecuta policy/api/web/migration/smoke desde checkout limpio | H1-01–06 |

**Gate:** CI/smoke verde, DB vacía migrada, servicios healthy y artefactos sin PII/secrets.

## H2 — Identidad, tenancy y audit log

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H2-01 P0 | ADM crea usuarios internos/roles/scopes sin autorregistro ni autoelevación | H1 |
| H2-02 P0 | Login Argon2id + TOTP/backups/sesiones/revocación/bloqueo pasa pruebas | H2-01 |
| H2-03 P0 | Middleware/repositorios aplican tenant, permiso y obra; PostgreSQL RLS está activa y forzada para el rol runtime | H2-01 |
| H2-04 P0 | Audit log append-only cubre auth, permisos y denegaciones sensibles | H2-02/03 |
| H2-05 P0 | Tests con segunda org señuelo prueban UUID conocido en cada endpoint | H2-03 |

**Gate:** usuario fuera de scope no descubre recursos y eventos sensibles son trazables.

## H3 — Obra, etapas, contratistas y personas

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H3-01 P0 | TEC CRUD/archiva obra sintética con jurisdicción y ETag | H2 |
| H3-02 P0 | Etapas temporales simultáneas conservan historial | H3-01 |
| H3-03 P0 | Contratistas y asignaciones temporales no duplican maestro | H3-01 |
| H3-04 P0 | Personas cifran el identificador recuperable y usan HMAC interno separado sólo para igualdad exacta; rotación, RLS y lecturas auditadas pasan pruebas | H3-03, DEC-004 |
| H3-05 P0 | Mis obras, filtros y detalle respetan scope y estados vacío/error | H3-01–04 |

**Gate:** alta integral de obra sintética sin planilla externa y aislamiento negativo verde.

## H4 — Documentos y maquinarias

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H4-01 P0 | Tipos/requisitos versionados por sujeto/etapa | H3 |
| H4-02 P0 | Upload→cuarentena→MIME/hash/AV→disponible es fail closed | H4-01 |
| H4-03 P0 | Nueva carga crea DocumentVersion; revisión y vigencia quedan separadas | H4-02 |
| H4-04 P0 | Faltantes/rechazados/próximos/vencidos reconcilian con detalle | H4-03 |
| H4-05 P0 | Máquinas, obra/operador temporal, documentos e inspección soportan transiciones válidas | H3/H4-03 |
| H4-06 P1 | carga manual asistida reduce pasos sin OCR/import Excel | H4-03 |

**Gate:** historia no se sobrescribe, descargas respetan scope y archivos hostiles no salen de cuarentena.

## H5 — Auditoría online

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H5-01 P0 | AUD crea/inicia con autor/editor/device y snapshot de checklist | H4 |
| H5-02 P0 | asistencia, etapas y pendientes previos quedan fotografiados | H5-01 |
| H5-03 P0 | controles exigen motivos y NO_CUMPLE crea/enlaza finding atómico | H5-01 |
| H5-04 P0 | autosave usa ETag/idempotencia y recupera interrupción | H5-03 |
| H5-05 P0 | finalizar valida completitud e inmoviliza snapshot | H5-02–04 |

**Gate:** cerrar/reabrir navegador no pierde ni duplica controles; concurrencia produce 412/423.

## H6 — Auditoría offline

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H6-01 P0 | PWA instala shell y cifra IndexedDB con contraseña independiente | H5 |
| H6-02 P0 | paquete mínimo por obra expira a 7 días y admite revocación | H6-01 |
| H6-03 P0 | modo avión captura asistencia, controles, fotos y findings cifrados | H6-02 |
| H6-04 P0 | sync batch idempotente aplica una vez y acusa cada mutación | H6-03 |
| H6-05 P0 | conflictos se revisan; no existe LWW; fotos se purgan tras acuse | H6-04 |
| H6-06 P0 | matriz Chrome Android/Safari iOS/Chrome-Edge completa evidencia | H6-01–05 |

**Gate:** recorrido modo avión y sincronización posterior sin pérdida/duplicación, incluyendo expiry/revocation/storage/conflict.

## H7 — Desvíos, cierre e informes

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H7-01 P0 | corrección/evidencia append-only y verificación por tercero | H5/H6 |
| H7-02 P0 | auto-verificación/autocierre y cierre de auditoría por autor son rechazados | H7-01 |
| H7-03 P0 | plantilla parametrizada allowlist genera PDF en worker | H7-01 |
| H7-04 P0 | reporte guarda snapshot/template/hash y variantes full/redacted | H7-03 |
| H7-05 P0 | conformidad guarda consentimiento/trazo y disclaimer no firma digital | H7-04 |
| H7-06 P0 | auditoría cerrada/evidencia/reporte son inmutables | H7-02–05 |

**Gate:** PDF reproducible desde snapshot y cierre imposible de alterar silenciosamente.

## H8 — Motor normativo

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H8-01 P0 | fuentes/jurisdicción/versiones/vigencias se inventarían trazablemente | H3 |
| H8-02 P0 | DSL allowlist produce tres resultados con trace determinístico | H8-01 |
| H8-03 P0 | simulador/casos límite y mapeo requisito-control funcionan con SYN-* | H8-02 |
| H8-04 P0 | creador no publica; corpus real pendiente no puede activarse | H8-03 |
| H8-05 P0 | nueva versión reevalúa abiertos sin mutar históricos | H8-04 |

**Gate:** suite sintética completa; cero reglas jurídicas reales activas.

## H9 — Dashboard, hardening y despliegue

| ID | Historia/aceptación | Dependencia |
|---|---|---|
| H9-01 P0 | dashboard reconcilia docs/findings/máquinas/última auditoría | H4/H7 |
| H9-02 P0 | ratio muestra CUMPLE/(CUMPLE+NO_CUMPLE), numerador/denominador y exclusiones | H5 |
| H9-03 P0 | HTTPS/rate limits/headers/secrets/logs/métricas/alertas pasan hardening | todos |
| H9-04 P0 | release desde tag firmado migra, health-gatea y hace rollback | H1/H9-03 |
| H9-05 P0 | UAT con 1 org/≤3 obras sintéticas recorre siete pasos | H9-01–04 |

**Gate:** DoD completa, E2E aprobado y owners firman salida. Datos reales continúan bloqueados hasta backup/restore y privacidad.

## P2 posterior

Firma digital certificada, IA/OCR, portal de contratistas, notificaciones
multicanal, migración Excel generalizada, analítica avanzada, multitenancy
productiva e integraciones. Cada elemento requiere discovery/ADR y no se adelanta.

## Plan de iteraciones sin calendario

Los hitos son secuenciales; dentro de cada uno se trabaja en cortes verticales:
contrato+migración → dominio/authz → API → UI → observabilidad/tests → gate. No se
asignan fechas hasta conocer equipo y entorno. Un gate fallido devuelve historias
al mismo hito, no se compensa abriendo el siguiente.
