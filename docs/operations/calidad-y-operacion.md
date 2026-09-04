# Calidad, CI, backup y observabilidad

## 1. Definition of Ready

Una historia entra en implementación cuando tiene actor, scope, invariantes,
criterios positivos/negativos, impacto en PII/offline/audit log, contrato API,
diseño de estados y dependencia de migración identificados. Reglas jurídicas sin
validación nunca están ready para activación.

## 2. Definition of Done

- criterios de aceptación y guards implementados;
- migración revisable y estrategia de rollback/compatibilidad;
- unit, API/integration y autorización cross-tenant/scope;
- lint, formato, tipos, tests y build reproducible desde locks;
- OpenAPI/cliente TypeScript sin diff;
- logs/métricas/audit events sin PII;
- accesibilidad y estados UX relevantes;
- docs/ADR/runbook actualizados;
- CI verde, revisión y evidencia del gate del hito.

## 3. Pirámide y matriz de pruebas

| Capa | Alcance | Herramientas previstas | Gate |
|---|---|---|---|
| dominio unitario | transiciones, vigencia, DSL, permisos/SoD, hashes | pytest; Vitest para lógica cliente | rápida, determinística, sin red |
| DB/integración | constraints, RLS, repositorios, jobs, migraciones | pytest + PostgreSQL efímero | DB vacía y versión anterior |
| contrato API | schemas, Problem Details, headers, idempotencia, ETag | pytest/httpx + snapshot OpenAPI | cliente generado sin diff |
| componentes web | formularios, errores, accesibilidad, offline state | Testing Library/Vitest/axe | sin warnings; teclado/lector |
| E2E | siete pasos de aceptación | Playwright contra Compose | Chromium desktop/móvil CI |
| dispositivo real | modo avión/cámara/storage/Safari | matriz manual automatizable | Chrome Android, Safari iOS, Edge/Chrome |
| seguridad | authz, upload, CSRF/XSS, rate limit, secrets/deps | tests propios + scanners | cero critical/high sin excepción aprobada |
| PDF visual | combinaciones permitidas y hashes | render a PNG + comparación/revisión | todas las configuraciones soportadas |
| resiliencia | DB/S3/AV caídos, retries, disco y conflictos | fault injection en stack efímero | degradación/fail-closed esperado |

Casos obligatorios siguen la sección 4 del plan: aislamiento por tenant/rol/obra,
MFA/recuperación/revocación, temporalidad, zona argentina, versionado/MIME/AV,
409 inválidos, reanudación online/offline, expiry/revocation/storage/conflict,
no autocierre, inmutabilidad, normativa, dashboard y ausencia de PII.

## 4. CI bloqueante

1. **policy:** secret/PII scan, licencias, archivos prohibidos, lint de workflow.
2. **api:** lock frozen, Ruff format/check, mypy, pytest+coverage, OpenAPI.
3. **web:** `npm ci`, ESLint, format, `tsc --noEmit`, unit/component, build.
4. **migration:** PostgreSQL efímero; empty→head, anterior→head, `alembic check`,
   downgrade sólo de migraciones declaradas reversibles y nuevo upgrade.
5. **compose-smoke:** config, build, migrate one-shot, health, web marker sintético,
   API contract, no DB/S3/AV publicados.
6. **e2e/security:** flujos críticos y authz negativa.

Workflow con `permissions: contents: read`, acciones fijadas por SHA, timeouts,
concurrency cancelable y artefactos sin secretos. Release sólo desde tag firmado.

## 5. Estrategia de migraciones

- Alembic desde el primer schema; runtime nunca ejecuta `create_all()`.
- Un único head; CI rechaza branches múltiples.
- Expand/contract: agregar nullable/default controlado, backfill idempotente, cambiar
  lecturas/escrituras y retirar en release posterior.
- Índices pesados/concurrentes con runbook; medir locks.
- Cada revisión declara compatibilidad con imagen anterior, estimación y recovery.
- Seeds sintéticos separados de migraciones.

## 6. Backup y restore propuesto

Objetivos sujetos a `DEC-006`: RPO 24 h, RTO 8 h; 30 copias diarias y 12 mensuales.

- `pg_dump` lógico diario más snapshot consistente según volumen; objetos mediante
  réplica/copia incremental preservando versiones, hashes y manifest.
- Configuración, Caddy y manifests versionados; secretos se respaldan por el
  custodio, nunca dentro del dump sin control.
- Destino cifrado fuera del servidor/VM y credenciales write-only separadas.
- Checksums y catálogo unen DB/object snapshot por recovery point.
- Restore trimestral en entorno aislado: DB, objetos, migración compatible, login
  sintético, muestra aleatoria de archivos/PDF y reconciliación dashboard.
- Evidencia: fecha, operador, versión, tamaños, hashes, tiempos, fallos y aprobación.

Snapshots en el mismo servidor no cuentan como backup. Hasta una restauración
exitosa no se habilitan datos reales.

## 7. Observabilidad

### Logs

JSON estructurado: timestamp UTC, level, service/version, environment, request_id,
trace_id, route template, status, duration, actor_id/organization_id opacos y
evento. Prohibidos bodies, cookies, auth headers, PII, object keys completos y
trazos manuscritos.

### Métricas

- HTTP tasa/latencia/error por ruta normalizada;
- auth successes/failures/locks/MFA sin etiquetas cardinales;
- pool DB y migración/schema version;
- uploads por estado, bytes, scan latency/reject reason agregado;
- jobs por tipo/estado/edad/reintento;
- sync mutations applied/conflicted/rejected/idempotent;
- paquetes activos/vencidos/revocados;
- report render duration/failures;
- capacidad DB/object/quarantine/log y backup age/restore evidence.

### Alertas iniciales

| Condición | Severidad/acción |
|---|---|
| ready falla 5 min o error 5xx elevado | crítica; rollback/diagnóstico |
| disco ≥80 % / ≥90 % | alta/crítica; bloquear cargas controladamente |
| backup >26 h o restore vencido | crítica antes de datos reales |
| cola más vieja >15 min | alta; revisar worker/dependencia |
| ClamAV/S3 caído | alta; cuarentena/fail closed |
| conflictos sync >5 % | alta de producto/ingeniería |
| elevaciones/exports anómalos | seguridad; investigar y revocar |

SLO inicial interno: 99,5 % mensual para API online, excluyendo mantenimiento
aprobado; p95 lectura <500 ms y mutación <1 s sin upload/job. Se calibra con UAT,
no se convierte automáticamente en compromiso contractual.

## 8. Runbooks mínimos antes de producción

- despliegue/rollback y migración fallida;
- restore completo y pérdida de objetos;
- compromiso de credencial/secreto/MFA;
- dispositivo offline perdido/revocado;
- ClamAV/S3/DB no disponibles;
- disco lleno y cuarentena acumulada;
- incidente de privacidad y preservación de evidencia;
- corrupción/diferencia de audit log o dashboard;
- retiro urgente de regla normativa.

