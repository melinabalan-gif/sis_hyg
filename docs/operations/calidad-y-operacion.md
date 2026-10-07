# Calidad, CI, backup y observabilidad

## Estado efectivo del piloto — 2026-10-07

**Sólo datos sintéticos; no se habilita producción.** Las secciones siguientes
son objetivos V1, no una certificación de controles desplegados. El workflow
versionado incorpora controles; un resultado local no demuestra su ejecución en
GitHub ni protección de ramas, aprobación humana o hardening del host.

| Control actual | Cobertura y límite |
|---|---|
| Policy | Fuente Git actual e historial alcanzable de todas las refs; rechaza clones shallow, Office/claves/.env versionados, formatos conocidos de tokens, literales de credenciales y DNI/CUIL/contacto con etiquetas. Reporta IDs opacos, no valores/rutas. No es DLP exhaustivo ni anonimización. |
| Términos protegidos | `HYS_RESTRICTED_TERMS_B64` se decodifica estrictamente; si falta, informa cobertura no ejecutada. Para gate de privacidad: `python scripts/policy_check.py --history --require-restricted-terms`. Configuración custodiada y aprobación siguen pendientes; no cargar términos reales en fixtures. |
| Dependencias | npm audit y pip-audit sobre export frozen del lock completo; sin auto-fix. Inventario CycloneDX npm/Python en almacenamiento temporal del runner; no contiene datos de negocio. No demuestra provenance ni cubre vulnerabilidades del OS/imágenes. |
| Licencias/workflow | YAML real parseado con PyYAML aislado fijado; SHA de acciones, permisos read-only y timeout por job. Allowlist SPDX npm y obligaciones conocidas MPL-2.0 (axe/lightningcss) y LGPL-3.0-or-later (binarios sharp) explícitas. No sustituye dictamen legal ni actionlint completo. Licencias Python inventariadas, aprobación aún pendiente. |
| Contratos/migraciones | OpenAPI `--check`, regeneración del SDK sin diferencias, único head igual a readiness; integración DB incluye empty→head, downgrade/re-upgrade y `alembic check`. PostgreSQL real aislado sigue requerido para acreditar resultados. |
| Journey | Playwright desktop/móvil: alta sintética real UI/API, dirección persistida tras reload, navegación por teclado y denegación API. No cubre siete pasos V1, MFA, binarios u offline inexistentes. Requiere loopback y opt-in explícito; no captura screenshots/trazas/datos. |
| Proxy | CSP del piloto sin unsafe-eval, frame-ancestors none, object-src none, base/form self y X-Frame-Options DENY. Inline permitido para bootstrap Next: no es CSP productiva con nonce/hash. Access logs desactivados hasta demostrar redacción de query/headers/rutas. |
| Smoke | Shell/PowerShell comprueban salud, banner sintético, migrador y cinco puertos privados DB/S3/AV; ausencia de servicio/inspección falla. Bypass TLS sólo HTTPS loopback; PowerShell requiere 7, en 5.1 usar certificado confiable sin switch. No es E2E. |

El reemplazo del wrapper ESLint Next evita `fast-glob→micromatch→braces`, cuyo
aviso no tiene parche publicado. Configs soportadas TypeScript/React/hooks/a11y
mantienen guards; reglas declarativas prohíben imports Pages Router, img/head/script
raw y navegación interna sin Link. No se afirma equivalencia con todas las
heurísticas de Core Web Vitals (fuentes, polyfills y Pages Router); build/tipos y
journeys complementan el gate. No se vendorea ni se aliasa una API incompatible.

### Ensayo de restore lógico sintético

En un PostgreSQL **aislado**, crear origen con nombre terminado `_test` y destino
vacío distinto terminado `_restore_test`, ambos loopback. Exportar sólo en el
proceso `HYS_ENVIRONMENT=test`, `HYS_DRILL_SOURCE_URL` y `HYS_DRILL_TARGET_URL`.
Ejecutar `python scripts/restore_drill.py --allow-synthetic-restore` (en Windows,
agregar `--pg-bin` con el directorio de herramientas portables). No usa `.env`.
Rechaza destinos no vacíos y jamás hace clean/drop; pg_dump custom→pg_restore,
compara huellas de dumps de datos; archive de hasta 16 MiB sólo en memoria y sin
retención. Cada herramienta tiene timeout de 60 s. En CI `--container` usa las
herramientas de la misma versión del PostgreSQL efímero. No imprime URLs,
credenciales ni contenido; la DB restaurada queda para inspección del operador.

El ensayo no es backup productivo: no configura destino externo cifrado,
retención, KMS, snapshots de objetos, scheduler, alertas ni RPO/RTO. Para datos
reales siguen pendientes DEC-006, restore completo con objetos y aprobación.
También siguen abiertos autenticación/MFA, nonce CSP, rate limiting probado en
un componente soportado (Caddy estándar no ofrece `rate_limit`), scanner de
imágenes/OS, provenance, privacidad formal, host Linux y gates V1. No desplegar
un plugin comunitario implícito ni afirmar cumplimiento legal.

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
