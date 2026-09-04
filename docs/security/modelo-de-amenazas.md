# Modelo de amenazas V1

Método STRIDE orientado a activos: credenciales/MFA, PII, archivos, evidencia,
snapshots, reglas normativas, reportes y disponibilidad offline.

| ID | Amenaza/abuso | Control preventivo | Detección/respuesta | Prueba bloqueante |
|---|---|---|---|---|
| T01 | credential stuffing | Argon2id, rate limit, lock progresivo, MFA | alertas por cuenta/IP sin guardar PII excesiva | intentos/bloqueo/recuperación |
| T02 | robo/fijación de sesión | cookie opaca segura, rotación, CSRF, TTL/revocación | evento de nueva sesión y revocación global | cookie flags, CSRF y replay |
| T03 | IDOR cross-tenant/scope | filtro tenant primero, constraints y RLS obligatoria | log de denegación agregado | UUID conocido en cada endpoint |
| T04 | elevación de privilegios | roles/scopes separados, reauth, no autoelevación | diff auditado y alerta privilegio | matrices positivas/negativas |
| T05 | autocierre/aprobación | guards de segregación en dominio/DB | evento `segregation_denied` | finding/audit/rule |
| T06 | upload malware/polyglot | límites, MIME real, cuarentena, ClamAV fail closed | métricas de scan/rechazo, purge | EICAR/oversize/MIME mismatch |
| T07 | object key adivinable | bucket privado, keys opacas, auth corta | descargas auditadas | acceso directo y token vencido |
| T08 | alteración histórica | append-only, ETag, hashes/snapshots, rol DB mínimo | verificación de chain/hash | update/delete prohibido |
| T09 | manipular PDF/template | DSL de plantilla allowlist, worker aislado, hashes | job/log sin contenido | configuraciones y render visual |
| T10 | regla normativa maliciosa | JSON schema + operadores allowlist, sin eval, límites | trace y rechazo de publicación | fuzz/recursión/costo/autopublish |
| T11 | pérdida/robo offline | AES-GCM, contraseña independiente, mínimos, TTL/revocación | dispositivo revocado y purge | extracción/expiry/revocation |
| T12 | replay/sync duplicado | UUID, idempotency key, base_version, transacción | estado por mutation/conflict | batch repetido/out-of-order |
| T13 | overwrite concurrente | If-Match y conflictos, no LWW | tasa de 412/conflict | dos editores/dispositivos |
| T14 | XSS/CSRF | CSP, escaping, sin HTML arbitrario, token CSRF | report-only antes de enforce | payloads en comentarios/templates |
| T15 | SSRF | sin URL fetch genérico, allowlist de fuentes, egress limitado | DNS/egress logs | IP privada/redirect/DNS rebinding |
| T16 | DoS/disco lleno | rate/body limits, cuotas, backpressure, alertas 70/80/90 | capacidad/cola/readiness | carga grande y dependencia caída |
| T17 | secreto en repo/log | secret scan, env/secret files, redacción estructurada | CI bloquea y rotación runbook | fixtures/log snapshots |
| T18 | backup inutilizable | cifrado externo, checksum, restore trimestral | evidencia RPO/RTO | restore completo aislado |
| T19 | supply chain | locks/digests, SBOM, provenance, scan, Dependabot | alertas y parcheo | build frozen y vulnerabilidades |
| T20 | administrador host | mínimo acceso, cifrado, separación y logs externos | revisión accesos y export de audit | ejercicio operativo |
| T21 | enumeración/reidentificación de DNI/CUIL | ciphertext reversible separado; HMAC keyed con dominio tenant/tipo; sin token expuesto ni búsqueda parcial | alertas por patrones de comparación y rotación de clave | diccionario offline no valida contra dump; HMAC nunca aparece en API/log/export |
| T22 | API usada como oráculo de descifrado | RLS + scope + `pii.view`, propósito, MFA reciente, rate limit y respuesta no reveladora | evento redactado por lectura/export y alerta de volumen | cross-tenant, sin permiso/MFA y lectura masiva denegados |

## Requisitos de diseño

- Fail closed para autorización, antivirus, publicación normativa y export full.
- Liveness no depende de servicios; readiness no expone detalles.
- CSP sin `unsafe-eval`; nonces/hashes para scripts. Headers: HSTS, nosniff,
  frame-ancestors, referrer-policy y permissions-policy mínima.
- Rate limits diferenciados para login, upload, sync, reportes y API general.
- Errores/redacción consistentes impiden oráculos de existencia.
- Cifrado reversible, HMAC de lookup, Argon2id y SHA-256 de integridad tienen
  claves/objetivos separados; ninguna primitiva releva RLS, autorización o audit.
- Dependencia caída degrada sólo capacidad relacionada: antivirus mantiene
  cuarentena; S3 impide archivo/reporte, pero consultas DB siguen disponibles.

## Riesgo aceptado provisional

Un único ambiente y paquete offline de siete días dejan riesgo residual. Sólo los
responsables definidos en el gate pueden aceptarlo; no se interpreta la existencia
de mitigaciones como aprobación.
