# Actores, RBAC y journeys V1

**Estado:** borrador para aprobación del Hito 0  
**Principio:** denegar por defecto; rol, organización, scope de obra y estado del recurso deben autorizar cada operación.

## 1. Modelo de autorización

Una autorización efectiva requiere simultáneamente:

```text
sesión válida + MFA verificado + usuario activo + mismo organization_id
+ permiso del rol + scope compatible + guard de estado + segregación de funciones
```

- Los roles agrupan permisos; no implican acceso global.
- `UserScope` limita a `ORGANIZATION` o a una lista explícita de obras.
- Los endpoints de colección filtran antes de paginar y los endpoints por UUID
  responden de modo no revelador cuando el recurso está fuera de tenant/scope.
- Un Administrador no obtiene lectura operativa por el solo hecho de administrar
  identidades; necesita el permiso y scope correspondientes.
- Los permisos de exportar, descargar archivos originales y ver PII son separados
  de los permisos de lectura común.
- Las decisiones de estado se validan en backend y se registran en `audit_log`.

## 2. Roles

Abreviaturas: `ADM` Administrador, `TEC` Técnico H&S, `AUD` Auditor,
`RHS` Responsable H&S, `ENE` Editor normativo y `ANR` Aprobador normativo.

| Área/permiso | ADM | TEC | AUD | RHS | ENE | ANR | Scope/guard adicional |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `identity.users.read` | ✓ | — | — | — | — | — | organización |
| `identity.users.write` | ✓ | — | — | — | — | — | no elevarse a sí mismo; MFA obligatorio |
| `identity.roles.read` | ✓ | — | — | ✓ | — | — | RHS sólo lectura |
| `identity.roles.write` | ✓ | — | — | — | — | — | cambios privilegiados requieren reautenticación |
| `identity.scopes.write` | ✓ | — | — | — | — | — | no asignar obras fuera de su alcance administrativo |
| `identity.sessions.revoke` | ✓ | — | — | — | — | — | usuario puede revocar sus propias sesiones |
| `audit_log.read` | ✓ | — | — | ✓ | — | — | RHS sólo eventos de obras en scope; PII redactada |
| `worksites.read` | ◐ | ✓ | ✓ | ✓ | ◐ | ◐ | obra asignada; ◐ requiere scope operativo explícito |
| `worksites.write` | — | ✓ | — | ✓ | — | — | maestro no borrable si tiene historia; optimistic lock |
| `worksites.stages.write` | — | ✓ | — | ✓ | — | — | intervalos válidos; varias etapas activas permitidas |
| `resources.read` | — | ✓ | ✓ | ✓ | — | — | obra asignada; identificadores enmascarados |
| `resources.write` | — | ✓ | — | ✓ | — | — | PII sólo con permiso separado |
| `pii.view` | — | ◐ | — | ◐ | — | — | descifrado en servidor con concesión explícita, propósito y audit log redactado |
| `pii.write` | — | ◐ | — | ◐ | — | — | cifrado reversible + HMAC de lookup en servidor; no concede lectura |
| `documents.read_metadata` | — | ✓ | ✓ | ✓ | — | — | scope del sujeto/obra |
| `documents.download_original` | — | ◐ | ◐ | ✓ | — | — | autorización corta y export log |
| `documents.upload` | — | ✓ | ✓ | ✓ | — | — | cuarentena; AUD sólo durante auditoría propia activa |
| `documents.review` | — | ✓ | — | ✓ | — | — | no cambia vigencia derivada ni sobrescribe versión |
| `machines.read` | — | ✓ | ✓ | ✓ | — | — | obra asignada |
| `machines.write` | — | ✓ | — | ✓ | — | — | transición válida y version check |
| `audits.create` | — | — | ✓ | ✓ | — | — | obra asignada, checklist publicable |
| `audits.edit` | — | — | ✓ | ✓ | — | — | sólo autor/editor y dispositivo lock; BORRADOR/EN_CURSO |
| `audits.finalize` | — | — | ✓ | ✓ | — | — | autor/editor; controles completos y sin sync pendiente |
| `audits.close` | — | — | — | ✓ | — | — | distinto del autor; todos los guards satisfechos |
| `findings.create` | — | ✓ | ✓ | ✓ | — | — | obra asignada; NO_CUMPLE lo exige |
| `findings.correct` | — | ✓ | ✓ | ✓ | — | — | actor autorizado distinto no es requisito para corregir |
| `findings.verify` | — | — | — | ✓ | — | — | nunca creador ni autor de la corrección que verifica |
| `reports.read` | ◐ | ✓ | ✓ | ✓ | — | — | misma obra; variante redactada según permisos |
| `reports.generate` | — | — | — | ✓ | — | — | auditoría FINALIZADA/CERRADA; job idempotente |
| `reports.export_full` | — | — | — | ◐ | — | — | permiso explícito y audit log |
| `offline.prepare` | — | — | ✓ | ✓ | — | — | MFA reciente, obra asignada, dispositivo activo |
| `offline.sync` | — | — | ✓ | ✓ | — | — | mismo editor/dispositivo; paquete vigente |
| `offline.conflicts.resolve` | — | — | — | ✓ | — | — | no resolver silenciosamente; decisión auditada |
| `regulatory.sources.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | fuentes publicadas; borradores sólo roles normativos |
| `regulatory.drafts.write` | — | — | — | — | ✓ | — | regla real nace inactiva |
| `regulatory.review` | — | — | — | — | ✓ | ✓ | comentarios append-only |
| `regulatory.publish` | — | — | — | — | — | ◐ | distinto del creador y rol deshabilitado sin validador |
| `templates.write` | ✓ | — | — | ✓ | — | — | no HTML arbitrario; nueva versión |

`◐` significa que el rol base no basta: requiere una concesión explícita adicional.

## 3. Segregación de funciones

| Acción | Actor impedido | Resultado esperado |
|---|---|---|
| Verificar/cerrar desvío | creador del desvío | `409 segregation-of-duties` |
| Verificar una corrección | autor de esa corrección | `409 segregation-of-duties` |
| Cerrar auditoría | autor de la auditoría | `409 segregation-of-duties` |
| Publicar regla | creador de esa versión | `409 segregation-of-duties` |
| Activar regla jurídica real | cualquier usuario sin gate H&S/legal | `403 feature-disabled` |
| Aprobar propia elevación de privilegios | usuario afectado | segundo administrador o procedimiento de bootstrap |
| Descargar/exportar sin permiso explícito | lector común | `403` y evento de intento denegado |

## 4. Journeys principales

### J-01 — Administrar identidad y scopes

1. ADM inicia sesión, completa TOTP y reautentica para una acción privilegiada.
2. Crea una cuenta interna sin autorregistro y asigna uno o más roles.
3. Limita `UserScope` a obras concretas; el backend rechaza scopes ajenos.
4. El usuario activa MFA y guarda códigos de respaldo una sola vez.
5. ADM verifica con vista previa de permisos efectivos y confirma.
6. Se registran actor, permisos antes/después, request ID y timestamp UTC.

Alternos: correo duplicado produce `409`; MFA no activado impide operación; al
revocar usuario se invalidan todas sus sesiones y paquetes offline asociados.

### J-02 — Alta integral de una obra sintética

1. TEC crea obra con código, jurisdicción y metadatos mínimos.
2. Agrega dos etapas temporales que pueden solaparse.
3. Asigna contratistas con vigencias; registra personas y sus relaciones
   persona–contratista–obra sin duplicarlas.
4. Configura requisitos documentales y carga archivos, que quedan en cuarentena.
5. Tras MIME/hash/antivirus, TEC revisa versiones y observa vigencias derivadas.
6. Registra máquinas, asignaciones, operador e inspección inicial.
7. El detalle de obra reconcilia cantidades y faltantes con listados filtrados.

Alternos: un intervalo inválido devuelve `422`; una edición con ETag viejo `412`;
malware/MIME inconsistente queda rechazado sin exponer el archivo.

### J-03 — Auditoría online recuperable

1. AUD selecciona obra y crea una auditoría BORRADOR con idempotency key.
2. El servidor fija autor, editor, dispositivo, etapas y versión de checklist.
3. AUD marca asistencia, pendientes anteriores y pasa a EN_CURSO.
4. Cada control se guarda con autosave, ETag e idempotencia.
5. `NO_CUMPLE` abre/enlaza un desvío en la misma operación; los otros resultados
   que lo requieren incluyen motivo.
6. Tras una interrupción, la UI recupera la versión confirmada y reintenta sólo
   operaciones sin acuse.
7. AUD finaliza; el snapshot queda inmutable y se libera el editor lock.

Alternos: un segundo dispositivo recibe `423`; duplicar una mutación devuelve la
misma respuesta; controles incompletos producen `409` con errores por campo.

### J-04 — Auditoría offline y sincronización

1. Con MFA reciente, AUD registra dispositivo y solicita paquete de una obra.
2. Define contraseña offline independiente; el cliente deriva la clave y cifra
   IndexedDB con AES-GCM. La clave/contraseña no llega al servidor.
3. Se descarga sólo checklist, datos enmascarados y pendientes mínimos, con TTL.
4. En modo avión registra asistencia, respuestas, fotos y desvíos como mutaciones
   UUID ordenadas e idempotentes.
5. Al volver conexión, la app reautentica si corresponde y envía un `SyncBatch`.
6. El servidor aplica operaciones válidas una vez, devuelve acuses por mutación y
   crea conflictos explícitos para las restantes.
7. El cliente purga fotos sólo después del acuse y muestra cualquier conflicto.

Alternos: paquete vencido requiere conexión; dispositivo revocado no sincroniza;
falta de espacio bloquea nuevas fotos pero preserva mutaciones; reenvío del batch
no duplica; conflicto queda para RHS y nunca usa último cambio gana.

### J-05 — Corrección y verificación independiente

1. TEC/RHS consulta desvíos abiertos por prioridad y vencimiento.
2. Un actor agrega corrección y evidencia, pasando a EN_CORRECCION.
3. Al declarar completa pasa a PENDIENTE_VERIFICACION.
4. RHS distinto del creador y del autor de la corrección revisa la evidencia.
5. Puede rechazarla (vuelve a EN_CORRECCION con motivo) o verificar y cerrar.
6. Cada transición conserva el historial; nunca sobrescribe evidencia previa.

Alternos: autocierre se rechaza; deadline vencido es una condición derivada, no
una transición destructiva; ETag obsoleto produce `412`.

### J-06 — Cierre, PDF y conformidad

1. RHS distinto del autor abre una auditoría FINALIZADA.
2. Revisa guard de desvíos, conflictos y controles, y solicita generación.
3. Worker usa snapshot y versión de plantilla; genera PDF, SHA-256 y variante
   redactada, sin HTML arbitrario.
4. Una persona registra conformidad simple: nombre, rol, fecha, consentimiento y
   trazo manuscrito, con aviso de que no es firma digital certificada.
5. RHS cierra auditoría; el backend rechaza cualquier mutación histórica.
6. Regenerar crea una versión de reporte nueva vinculada al mismo snapshot.

Alternos: job repetido es idempotente; fallo no cambia estado; exportación sin
permiso entrega variante redactada o `403`.

### J-07 — Regla normativa sintética

1. ENE crea fuente sintética, regla y versión BORRADOR con DSL válida.
2. Simula sobre casos sintéticos y obtiene APLICA/NO_APLICA/INDETERMINADO.
3. Envía a EN_REVISION; otro actor deja observaciones.
4. ANR distinto del creador publica sólo si el feature gate del validador está
   habilitado. Para V1 sin validador, sólo reglas `SYN-*` pueden aprobarse.
5. Evaluaciones guardan rule version e inputs normalizados.
6. Una nueva versión reevalúa requisitos abiertos sin mutar auditorías históricas.

### J-08 — Dashboard reconciliado

1. Usuario abre “Mis obras”; la API filtra por tenant y scope antes de agregar.
2. Ve faltantes/vencidos, desvíos abiertos/vencidos, máquinas y última auditoría.
3. Al seleccionar una métrica obtiene exactamente los registros del numerador.
4. Resultado de auditoría muestra `CUMPLE/(CUMPLE+NO_CUMPLE)` con ambos valores y
   excluye justificada y visiblemente NO_APLICA/NO_VERIFICADO.
5. Nunca se muestran “cumplimiento legal”, “óptimo” ni inferencias no sustentadas.

## 5. Recuperación y bootstrap

- No hay autorregistro ni recuperación por correo en V1.
- Un administrador puede iniciar recuperación con identidad verificada por canal
  organizacional; otro administrador confirma si cambia roles/scopes.
- Los códigos de respaldo se almacenan con un password hash adecuado a su
  entropía, se muestran una sola vez y cada uso los invalida. No comparten clave
  ni primitiva con el HMAC de identificadores.
- El primer administrador se crea mediante comando one-shot auditado, disponible
  sólo desde consola de la VM y deshabilitado después del bootstrap.
- Si queda un único administrador, su desactivación exige crear/validar reemplazo.
