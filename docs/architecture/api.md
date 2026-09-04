# Contrato REST inicial `/api/v1`

**Estado:** contrato de blueprint; Hito 1 materializa OpenAPI versionada y cliente TypeScript generado.

## 1. Convenciones

- JSON UTF-8; fechas ISO 8601; instantes UTC terminados en `Z`; IDs UUID.
- Nombres de recursos y campos en inglés; copy de UI en español.
- Colecciones por cursor: `?limit=50&cursor=...&sort=created_at&order=desc`.
- `limit` 1–100. Respuesta: `{"items":[],"next_cursor":null}`.
- Filtros explícitos; parámetros desconocidos producen `422`.
- `ETag: "<version>"` en recursos mutables. `PATCH`/transición requiere
  `If-Match`; falta `428`, desactualizado `412`.
- POST reintentable/transiciones/jobs/sync requieren `Idempotency-Key` UUID. La
  misma key+body devuelve la respuesta original; body distinto devuelve `409`.
- Recursos fuera de tenant/scope responden `404` para evitar enumeración. Un
  permiso faltante sobre un recurso visible responde `403`.
- No hay endpoints genéricos de update/delete para historia inmutable.

## 2. Problem Details

Errores usan `application/problem+json`:

```json
{
  "type": "https://hys.invalid/problems/etag-mismatch",
  "title": "El recurso cambió",
  "status": 412,
  "detail": "Recargá el recurso antes de reintentar.",
  "instance": "/api/v1/worksites/00000000-0000-0000-0000-000000000001",
  "code": "etag_mismatch",
  "request_id": "00000000-0000-0000-0000-000000000099",
  "errors": []
}
```

No incluir SQL, stack, rutas internas, PII ni existencia de recursos ajenos.
Estados relevantes: 400 request inválido, 401 sesión/MFA, 403 permiso, 404 no
revelador, 409 transición/idempotencia/segregación, 412 ETag, 413 tamaño, 415 MIME,
422 campos, 423 editor lock, 428 precondición y 503 dependencia/readiness.

## 3. Autenticación y sesión

Cookie de sesión opaca `HttpOnly; Secure; SameSite=Lax`; token CSRF separado y
header `X-CSRF-Token` en mutaciones. Rotación al login/MFA/elevación. TOTP y
códigos de respaldo; sin autorregistro.

| Método/ruta | Propósito | Auth/resultado |
|---|---|---|
| `POST /auth/login` | validar credenciales | rate limit; sesión `MFA_PENDING` |
| `POST /auth/mfa/totp/verify` | completar login | rota sesión; `204` |
| `POST /auth/mfa/enroll` | iniciar alta TOTP | sesión + reauth; secreto una vez |
| `POST /auth/mfa/enroll/confirm` | confirmar factor | código válido; backup codes una vez |
| `POST /auth/backup-codes/use` | completar MFA | consume código atómicamente |
| `POST /auth/logout` | revocar sesión actual | `204` |
| `GET /auth/session` | identidad/permisos/scopes efectivos | datos mínimos, no secretos |
| `POST /auth/reauthenticate` | elevar sesión temporalmente | password+MFA; TTL corto |
| `GET /auth/sessions` | sesiones propias | metadatos de dispositivo |
| `DELETE /auth/sessions/{id}` | revocar propia sesión | `204` |

Administración: `/users`, `/roles`, `/permissions`, `/user-scopes` con CRUD
limitado por permisos de identity; recuperación y bootstrap son acciones
administrativas auditadas, no reset público.

## 4. Rutas de dominio

`R` lista/detalle, `C` crea, `U` actualiza con ETag y `A` acción/transición.

### Obras y recursos

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /worksites` | `worksites.read/write` | cursor/filtros; código único tenant |
| `GET/PATCH /worksites/{id}` | idem | scope; soft delete mediante acción separada |
| `POST /worksites/{id}/archive` | `worksites.write` | guard de historia; no borra |
| `GET/POST /worksites/{id}/stages` | `worksites.read/stages.write` | intervalos y varias activas |
| `PATCH /worksite-stages/{id}` | `worksites.stages.write` | ETag; conserva historial |
| `GET/POST /contractors` | `resources.read/write` | maestro tenant |
| `GET/PATCH /contractors/{id}` | idem | enmascarado y ETag |
| `GET/POST /worksites/{id}/contractor-assignments` | `resources.read/write` | relación temporal |
| `GET/POST /people` | `resources.read/write` | escritura cifra el identificador recuperable y calcula HMAC de lookup separado; ninguno se devuelve |
| `GET/PATCH /people/{id}` | idem | respuesta enmascarada por defecto |
| `GET/POST /worksites/{id}/person-assignments` | `resources.read/write` | persona–contratista–obra temporal |

El piloto expone `GET/POST /worksites/{id}/functional-assignments` para consultar
y registrar la función temporal de un actor sintético. La respuesta incluye
profesión, función, empresa representada, alcance y vigencia. La creación sólo
acepta UUID del adaptador sintético y nunca crea usuarios; exige una persona
asignada a la misma obra, profesión compatible y, para funciones del contratista,
la participación PRINCIPAL. El alcance efectivo no puede exceder el alcance del
actor ni cruzar de obra.

Una comparación exacta normaliza en servidor y consulta el HMAC bajo RLS; no
acepta ni devuelve tokens HMAC. Revelar el identificador requiere `pii.view`,
scope, propósito y MFA reciente cuando corresponda; el servidor descifra el
ciphertext y registra el evento redactado. No existe endpoint de descifrado
genérico ni búsqueda parcial.

### Documentos y archivos

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /document-types` | `documents.read_metadata/templates.write` | catálogo versionado |
| `GET/POST /document-requirements` | idem | sujeto y aplicabilidad |
| `GET/POST /documents` | `documents.read_metadata/upload` | filtros de revisión/vigencia/sujeto |
| `GET /documents/{id}` | `documents.read_metadata` | versiones y vigencia derivada |
| `POST /documents/{id}/versions` | `documents.upload` | crea upload en cuarentena |
| `POST /documents/{id}/reviews` | `documents.review` | approve/reject+motivo; idempotente |
| `POST /files/uploads` | `documents.upload` | metadata y canal de carga autorizado corto |
| `POST /files/{id}/complete` | `documents.upload` | verifica tamaño/hash; encola AV |
| `GET /files/{id}/download-authorization` | `documents.download_original` | URL/token corto; evento de exportación |
| `GET /document-status` | `documents.read_metadata` | listados faltante/rechazado/próximo/vencido |

Nunca servir objetos de cuarentena. El servidor detecta MIME; el declarado es sólo
metadata. Carga y finalización requieren hash/tamaño y límites configurados.

### Máquinas

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /machines` | `machines.read/write` | maestro, owner y estado |
| `GET/PATCH /machines/{id}` | idem | ETag |
| `GET/POST /machines/{id}/worksite-assignments` | `machines.read/write` | intervalo temporal |
| `GET/POST /machines/{id}/operator-assignments` | idem | persona/obra e intervalo |
| `GET/POST /machines/{id}/inspections` | idem | snapshot de controles versionados |
| `POST /machines/{id}/transitions` | `machines.write` | target, inspection, reason; `409` inválida |

### Auditorías y controles

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /audits` | `audits.read/create` | POST fija snapshot, editor y device |
| `GET /audits/{id}` | `audits.read` | estado, progreso, ETag, lock |
| `POST /audits/{id}/start` | `audits.edit` | BORRADOR→EN_CURSO |
| `PUT /audits/{id}/attendance/{person_id}` | `audits.edit` | idempotente; snapshot persona |
| `GET /audits/{id}/controls` | `audits.read` | cursor/categoría/estado |
| `PUT /audits/{id}/controls/{id}` | `audits.edit` | resultado, motivo, finding link, ETag+key |
| `POST /audits/{id}/finalize` | `audits.finalize` | valida totalidad y calcula snapshot hash |
| `POST /audits/{id}/close` | `audits.close` | RHS distinto; guards y ETag |
| `GET /control-catalog/versions/{id}` | `audits.read` | definición inmutable usada |

`POST /worksites/{id}/audits` acepta opcionalmente `auditor_assignment_id` para
seleccionar una asignación vigente del actor. La auditoría persiste obra, actor
auditor, asignación, fecha y, cuando existe, la persona profesional responsable
del proyecto; `author_actor_id` y `editor_actor_id` continúan como campos de
compatibilidad.

### Desvíos y evidencia

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /findings` | `findings.read/create` | filtros obra/estado/vencido/severidad |
| `GET/PATCH /findings/{id}` | `findings.read/create` | sólo campos permitidos antes de cierre |
| `POST /findings/{id}/corrections` | `findings.correct` | descripción/evidencia; append-only |
| `POST /findings/{id}/submit-verification` | `findings.correct` | guard de evidencia |
| `POST /findings/{id}/verifications` | `findings.verify` | accept/reject+motivo; segregación |
| `POST /findings/{id}/evidence` | `findings.correct` | asset disponible o pendiente controlado |
| `GET /findings/{id}/timeline` | `findings.read` | eventos ordenados append-only |

### Offline

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `POST /devices` | sesión MFA | registra instalación/public key |
| `DELETE /devices/{id}` | propia/ADM | revoca, invalida paquetes |
| `POST /offline-packages` | `offline.prepare` | worksite/audit/device; manifest+expiry |
| `GET /offline-packages/{id}/manifest` | editor | datos mínimos; no clave local |
| `POST /offline-packages/{id}/revoke` | propia/ADM/RHS | revoca y audita |
| `POST /offline-packages/{id}/sync-batches` | `offline.sync` | batch+mutations ordenadas; acuse individual |
| `GET /sync-batches/{id}` | editor/RHS | applied/rejected/conflicted |
| `GET /sync-conflicts` | `offline.conflicts.resolve` | por obra/estado |
| `POST /sync-conflicts/{id}/resolutions` | RHS | nueva decisión auditada, nunca LWW |

### Reportes y dashboard

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /report-template-versions` | `reports.read/templates.write` | parámetros allowlist |
| `POST /audits/{id}/reports` | `reports.generate` | job idempotente, snapshot+template |
| `GET /reports/{id}` | `reports.read` | estado, hash, versión, nivel redactado |
| `GET /reports/{id}/download-authorization` | `reports.read/export_full` | decide variante y audita |
| `POST /reports/{id}/acknowledgements` | `reports.read` | consentimiento y trazo cifrado |
| `GET /dashboard/worksites` | `worksites.read` | agregados tenant/scope y `as_of` |
| `GET /dashboard/worksites/{id}` | `worksites.read` | numeradores/denominadores y enlaces de filtro |

### Normativa y audit log

| Método/ruta | Permiso | Contrato principal |
|---|---|---|
| `GET/POST /regulatory/sources` | regulatory read/draft | real nace pendiente/inactiva |
| `GET/POST /regulatory/rules` | regulatory read/draft | key, source, título |
| `POST /regulatory/rules/{id}/versions` | `regulatory.drafts.write` | DSL + vigencia; nueva versión |
| `POST /regulatory/rule-versions/{id}/simulate` | regulatory role | inputs sintéticos, resultado+trace |
| `POST /regulatory/rule-versions/{id}/submit-review` | editor | BORRADOR→EN_REVISION |
| `POST /regulatory/rule-versions/{id}/publish` | aprobador | doble aprobación/feature gate |
| `POST /regulatory/rule-versions/{id}/retire` | aprobador | motivo y nueva vigencia |
| `GET /regulatory/evaluations` | regulatory/read scope | snapshot y trace no jurídico |
| `GET /audit-log` | `audit_log.read` | cursor, filtros, redacción y scope |
| `POST /audit-log/exports` | permiso explícito | job y evento de exportación |

## 5. Health y contrato operativo

| Ruta | Semántica |
|---|---|
| `GET /health/live` | proceso/event loop responde; no consulta dependencias |
| `GET /health/ready` | DB accesible y revisión de esquema compatible; `503` genérico si no |
| `GET /openapi.json` | contrato de la versión desplegada; sin rutas admin ocultas |

En la ruta pública quedan `/api/v1/health/live` y `/api/v1/health/ready`. Métricas
se exponen sólo en red interna/autenticada, no bajo el API público.

## 6. Schemas mínimos

- `Create*`: no acepta IDs/tenant/actor/estado controlados por servidor.
- `Patch*`: campos opcionales explícitos; `additionalProperties=false`.
- `Resource`: incluye `id`, `organization_id` sólo cuando no filtra información,
  `created_at`, `updated_at`, `version`, links/permissions útiles.
- Snapshots e historia tienen schemas propios e inmutables.
- OpenAPI incluye ejemplos exclusivamente sintéticos y security schemes de
  cookie+CSRF; el cliente generado se verifica sin diff en CI.
