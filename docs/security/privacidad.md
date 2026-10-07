# Política de privacidad y manejo de datos V1

**Implementación del piloto (2026-10-07):** las primitivas y garantías descritas
abajo son requisitos V1; no están todas implementadas. Se prohíben datos reales.
El scanner heurístico actual inspecciona fuente/historial Git con salida
redactada, pero no prueba ausencia absoluta de PII ni sustituye cifrado, DLP,
revisión humana o configuración de términos protegidos. CSP permite inline de
Next para el piloto; logs de acceso del proxy permanecen desactivados hasta
verificar redacción. Backup lógico sintético no acredita backup externo cifrado,
restauración de objetos ni DEC-006. Cobertura efectiva y gates abiertos se
detallan en `../operations/calidad-y-operacion.md`.

**Estado arquitectónico:** aprobado por la persona solicitante el 2026-09-02, con
la aclaración criptográfica de este documento. La habilitación de datos reales
continúa bloqueada hasta la aprobación formal de privacidad/seguridad y los gates
operativos indicados abajo.

## Clasificación

| Clase | Ejemplos | Tratamiento |
|---|---|---|
| Público | assets de UI, documentación comercial aprobada | puede servirse públicamente |
| Interno | catálogos sintéticos, métricas técnicas agregadas | usuarios internos autorizados |
| Confidencial | obra, contratista, auditoría, hallazgo, documento, reporte | tenant/scope, cifrado en tránsito/reposo, export auditado |
| Restringido/PII | DNI/CUIL, datos de contacto, firma/trazo, adjuntos personales | permiso separado, masking, cifrado de campo, mínima retención |
| Secreto | contraseñas, TOTP, backup codes, claves, tokens | primitiva específica según necesidad de recuperación; nunca logs/UI/export común |

## Minimización y propósito

- V1 no solicita PII si un identificador sintético/operativo alcanza.
- DNI/CUIL no son obligatorios por defecto; su habilitación requiere base/política
  aprobada. No se ofrece búsqueda parcial.
- Se registra propósito al revelar/exportar PII y se limita a obras en scope.
- El trazo de conformidad se cifra y se asocia al reporte; no se presenta como
  firma digital certificada.
- Logs, métricas, trazas y eventos técnicos usan IDs opacos y campos permitidos,
  nunca bodies, cookies, tokens, identificadores o nombres de archivo sensibles.

## Primitivas criptográficas y usos separados

TLS moderno protege el tránsito; los volúmenes y backups se cifran. Esos controles
no reemplazan la protección de campo ni RLS. En aplicación se distinguen cuatro
objetivos y no se reutiliza una primitiva como si resolviera otro:

### Datos recuperables: cifrado autenticado reversible

- La PII que el negocio deba volver a mostrar —por ejemplo DNI/CUIL o un trazo de
  conformidad— se protege con cifrado de sobre AES-256-GCM. Una DEK por
  registro/ámbito cifra el valor; la KEK queda en un custodio/KMS separado de la
  base de datos.
- Se conservan ciphertext, nonce único, tag de autenticación, versión de algoritmo
  y clave. El AAD liga como mínimo organización, tipo de sujeto, ID de registro,
  nombre de campo y versión de esquema para impedir trasplantes de ciphertext.
- Descifrar es una operación deliberada: exige tenant y obra en scope, permiso
  `pii.view`, propósito, MFA reciente cuando corresponda y un evento de auditoría
  sin el valor en claro. `pii.write` no concede lectura.

### Comparación exacta: HMAC keyed y pseudonimización

- Para igualdad, deduplicación o unicidad exacta se calcula HMAC-SHA-256 con una
  clave dedicada sobre una codificación canónica, versionada y separada por
  dominio que incluye organización, clase de identificador y valor normalizado.
  La normalización se prueba y se versiona; V1 no ofrece búsqueda parcial.
- El token HMAC es determinístico dentro de ese contexto, vive separado del
  ciphertext y nunca sale por API, UI, logs o exportaciones. Su clave no se
  reutiliza como DEK/KEK, clave de sesión ni clave de otra organización/dominio.
- Un HMAC no es cifrado: no existe operación para recuperar el valor desde el
  token. Tampoco anonimiza; permite observar igualdad dentro de su ámbito y, junto
  con información auxiliar o acceso a un oráculo, conserva riesgo de
  reidentificación. Se trata como dato restringido pseudonimizado.

### Credenciales: hashes de contraseña y digests de tokens

- Las contraseñas se verifican con Argon2id, salt aleatorio único y parámetros de
  memoria/tiempo/paralelismo versionados. No se cifran ni se procesan con SHA-256
  rápido o con el HMAC de PII.
- Los códigos de respaldo de entropía humana usan un password hash apropiado y se
  invalidan al consumirlos. Para tokens de sesión o recuperación generados con
  alta entropía sólo se persiste un digest/HMAC dedicado y se compara en tiempo
  constante; el token original no se recupera.
- Una semilla TOTP sí debe recuperarse para verificar códigos: se cifra como
  secreto recuperable, nunca se confunde con el hash de una contraseña.

### Integridad: SHA-256 de artefactos

- Archivos, manifests, snapshots y reportes usan SHA-256 sobre bytes/canonical
  form para detectar cambios y referenciar una versión. Es un digest no keyed:
  no oculta contenido, no pseudonimiza PII y por sí solo no demuestra autoría ni
  evita que quien pueda reemplazar artefacto y digest modifique ambos.
- La autenticidad/tamper evidence combina el digest con permisos append-only,
  cadena o checkpoint protegido y, cuando el caso lo requiera, MAC o firma. Nunca
  se usa un hash de integridad como sustituto del cifrado de un campo recuperable.

La rotación también se separa: rewrap/reencrypt para claves de cifrado y
re-tokenización con dual read acotado para versiones HMAC. Ambas rutas son
idempotentes, medibles y auditadas; la versión anterior se retira al completar la
verificación. La selección del custodio/KMS, claves, parámetros y ceremonia de
recuperación sigue siendo el pendiente operativo de `DEC-004`; no se guardan
claves junto al ciphertext ni en el repositorio.

## Acceso, masking y exportación

- Respuesta común: identificador `••••123` sólo si el formato aprobado lo permite
  y el servidor obtuvo el sufijo mediante un flujo autorizado o desde un atributo
  protegido diseñado para masking; el HMAC no permite derivarlo. De lo contrario,
  `DATO PROTEGIDO`.
- `pii.view`, `pii.write`, `download_original` y `export_full` son permisos
  independientes y requieren MFA reciente para acciones de alto riesgo.
- Links de descarga son de un uso/TTL corto, ligados a usuario/asset y auditados.
- Export redactado omite PII, trazos, originales y metadata innecesaria.
- El soporte técnico no tiene acceso implícito; acceso excepcional es temporal,
  aprobado y registrado.

## Retención y eliminación

Hasta aprobación legal se aplican defaults conservadores:

- sesiones: metadata 90 días después de revocación; token inutilizable de inmediato;
- paquetes offline: purga local tras sync/revocación/expiración; metadata 180 días;
- cuarentena rechazada: purga del binario en 7 días; conservar hash/resultado mínimo;
- logs técnicos: 30 días online y 90 días agregados;
- exportaciones temporales: 24 horas;
- maestros dados de baja: ocultos, no borrados si existe historia referencial;
- auditorías, evidencia, informes y audit log: plazo pendiente de dictamen; no
  borrarlos automáticamente antes de una política aprobada.

Solicitudes de corrección/eliminación generan caso auditado y se resuelven con
retención legal/referencial; no se ejecuta cascada destructiva improvisada.

## Backup, incidentes y terceros

- Ningún dato real hasta backup externo cifrado y restore probado.
- Backups heredan clasificación y controles; acceso de restore separado.
- SeaweedFS/GHCR/hosting y cualquier proveedor se inventarían y evaluarían antes
  de transferir datos; V1 busca almacenamiento bajo control propio.
- Incidente: contener/revocar, preservar evidencia, evaluar alcance, notificar a
  responsables y documentar acciones. Los plazos legales los define asesoría.

## Dataset sintético

Sólo dominios reservados (`example.invalid`), referencias explícitas Demo y
adjuntos generados con marca `DATOS SINTETICOS`. CI bloquea patrones, hashes y
nombres de fuentes restringidas. No se copia ni se "anonimiza" el relevamiento
real. Reemplazar un identificador por HMAC sólo lo pseudonimiza y no autoriza su
uso como dataset sintético.
