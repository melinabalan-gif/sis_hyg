# Riesgos, decisiones y aprobaciones

## Decisiones y estado

| ID | Decisión | Recomendación de blueprint | Estado al 2026-09-02 | Pendiente operativo/formal |
|---|---|---|---|---|
| DEC-001 | Entorno de desarrollo/CI | Usar un host distinto que cumpla al menos 8 vCPU, 24 GB RAM, 1 TB cifrado y virtualización; no reducir el baseline productivo para adaptarlo a esta PC | **APROBADA — opción A** por la persona solicitante | Aprovisionar/identificar host y ejecutar gates |
| DEC-002 | Repositorio remoto | GitHub privado + GHCR privado, rama `main` protegida, dos revisores para seguridad/migraciones | **PENDIENTE** | Cuenta, organización, owners y credenciales externas |
| DEC-003 | Aislamiento tenant | Defensa en profundidad: filtros/scopes obligatorios en aplicación, FK/uniques con `organization_id` y PostgreSQL RLS para tablas operativas desde el esquema inicial | **APROBADA** por la persona solicitante | Validación nominal de arquitectura/seguridad y evidencia de pruebas |
| DEC-004 | Identificadores sensibles | AES-256-GCM de sobre para PII recuperable; HMAC-SHA-256 keyed, normalizado y separado para igualdad/pseudonimización; Argon2id para contraseñas; SHA-256 para integridad; masking por defecto y sin búsqueda parcial | **APROBADA CON ACLARACIÓN** por la persona solicitante | Custodio/KMS, claves separadas, parámetros/rotación, retención y aprobación formal de privacidad/seguridad antes de PII real |
| DEC-005 | Criticidad | Catálogo versionado por organización con defaults `BAJA/MEDIA/ALTA/CRITICA`; cada finding fotografía versión, plazo default y severidad | **APROBADA** por la persona solicitante | Validación nominal de producto/H&S y pruebas históricas |
| DEC-006 | Backup externo | Destino fuera del servidor, cifrado, RPO 24 h, RTO 8 h, retención 30 diarias + 12 mensuales y restore trimestral | **PENDIENTE** | Presupuesto, destino y responsable operativo |
| DEC-007 | Aprobadores | Un owner de producto, uno de seguridad/privacidad y un validador H&S/legal independiente | **PENDIENTE** | Responsables humanos identificables |

La decisión de `DEC-001` está tomada, pero hasta que el host exista y `DEC-002` se
resuelva sólo puede escribirse/revisarse el baseline: no se declara
reproducibilidad ni CI verificada. `DEC-004` fija ya la semántica arquitectónica,
pero sus pendientes operativos y `DEC-006` bloquean PII y datos reales. La V1
opera con una sola organización aunque `DEC-003` se adopta desde el esquema
inicial.

## Registro de riesgos

Escala: probabilidad e impacto `B/M/A`; riesgo residual esperado tras mitigación.

| ID | Riesgo | P | I | Mitigación/trigger | Owner propuesto | Residual |
|---|---|---:|---:|---|---|---:|
| R-001 | Fuga entre organizaciones/obras | M | A | pruebas negativas por endpoint, RLS, scopes y revisión; trigger: UUID ajeno retorna datos | Seguridad | B |
| R-002 | Pérdida del único servidor | M | A | backup externo + restore trimestral; trigger: snapshot local tratado como backup | Operaciones | M |
| R-003 | PII expuesta en logs/fixtures/export | M | A | clasificación, redactado, DLP en CI y revisión; trigger: DNI/CUIL en artefacto | Privacidad | B |
| R-004 | Dispositivo offline perdido | M | A | AES-GCM, TTL, datos mínimos, revocación y purge; trigger: dispositivo reportado | Seguridad | M |
| R-005 | Conflicto destruye evidencia | M | A | idempotency keys, optimistic locking y revisión, nunca LWW | Ingeniería | B |
| R-006 | Malware en adjuntos | M | A | cuarentena, MIME real, hash, límites y ClamAV; fail closed | Seguridad | B |
| R-007 | Regla jurídica errónea se interpreta como cumplimiento | M | A | corpus real inactivo, doble aprobación, lenguaje no legal y validador | H&S/legal | B |
| R-008 | Autoaprobación o alteración histórica | M | A | segregación de funciones, snapshots, audit log append-only y tests | Producto | B |
| R-009 | Informe no reproducible | M | A | plantilla/snapshot versionados, SHA-256 y prueba visual determinista | Ingeniería | B |
| R-010 | Entorno único impide rollback seguro | M | A | stacks efímeros CI, imágenes inmutables, migraciones compatibles y restore | Operaciones | M |
| R-011 | Baja adopción móvil | M | M | UAT de campo, autosave, objetivos de tiempo y entrevistas semanales | Producto | M |
| R-012 | Carga inicial supera valor percibido | A | M | dataset mínimo, carga asistida manual y medir tiempo de onboarding | Producto | M |
| R-013 | Dependencia de almacenamiento/antivirus | M | M | puertos abstractos, health/degraded mode y export probado | Ingeniería | B |
| R-014 | Capacidad del host insuficiente | A | A | aprovisionar y verificar el host de opción A antes del gate; observar CPU/RAM/disco | Operaciones | M |

## Evidencia de aprobación

El 2026-09-02 la persona solicitante aprobó explícitamente el blueprint, eligió la
opción A (servidor/VM compatible) y pidió corregir `DEC-004` antes de implementar
PII. La instrucción mantiene RLS, trazabilidad y criticidad configurable. No se
informaron nombre, rol organizacional, host, repositorio ni credenciales; este
registro no los inventa ni convierte esa aceptación en las validaciones
independientes que exige el gate.

| Fecha | Actor disponible | Alcance | Evidencia | Estado |
|---|---|---|---|---|
| 2026-09-02 | Persona solicitante; nombre/rol no informados | Blueprint, opción A, `DEC-003`, `DEC-004` aclarada y `DEC-005` | Instrucción explícita en la conversación de trabajo | **REGISTRADA** |

Para cada aprobación formal se registrarán nombre, rol, fecha y hash de commit
cuando existan. Los campos desconocidos permanecen pendientes:

| Área | Responsable | Fecha | Commit | Estado |
|---|---|---|---|---|
| Producto/alcance | PENDIENTE | — | — | PENDIENTE |
| Seguridad/privacidad | PENDIENTE | — | — | PENDIENTE |
| H&S/legal | PENDIENTE | — | — | PENDIENTE |
| Operaciones/infraestructura | PENDIENTE | — | — | PENDIENTE |
