# ADR-0003 — Asociaciones documentales explícitas y PII protegida

- Estado: Aceptado para implementación arquitectónica por la persona solicitante;
  la activación de PII real requiere completar los pendientes operativos de
  `DEC-004` y el gate de datos reales
- Fecha: 2026-09-02

## Contexto

Los documentos pertenecen a tipos de sujetos distintos y conservan historia. Una
FK polimórfica debilita integridad. DNI/CUIL en claro o con un digest rápido sin
clave permite exposición y enumeración por su espacio pequeño. A la vez, un valor
que el negocio deba consultar no puede reemplazarse sólo por un hash/HMAC porque
esa representación no es recuperable.

## Decisión

`Document` se vincula mediante exactamente una tabla explícita
Worksite/Contractor/Person/MachineDocument. Cada carga crea `DocumentVersion` y
`FileAsset`; la revisión se almacena y la vigencia se deriva. Binarios pasan por
cuarentena, MIME real, hash, límites y antivirus.

La PII recuperable se cifra con AES-256-GCM de sobre. Se persisten ciphertext,
nonce/tag y versión de clave; el AAD liga organización, sujeto, registro, campo y
versión de esquema. Descifrar requiere RLS, scope de obra, `pii.view`, propósito y
trazabilidad. El permiso de escritura no implica lectura.

Búsqueda, deduplicación y unicidad exactas usan un token HMAC-SHA-256 separado,
calculado con clave dedicada sobre una normalización y separación de dominio
versionadas que incluyen la organización y el tipo de identificador. El HMAC es
pseudonimización, no anonimización ni cifrado: no permite recuperar el dato y
filtra igualdad dentro de su ámbito. No se expone y no hay búsqueda parcial V1.

Contraseñas se almacenan con Argon2id salado y parametrizado; secretos que deben
recuperarse, como la semilla TOTP, se cifran. Los SHA-256 de binarios, snapshots y
reportes son únicamente huellas de integridad y no protegen la confidencialidad ni
prueban origen por sí solos. Cada familia usa claves y ciclo de rotación separados.
Masking por defecto y permisos de ver, editar, descargar/exportar permanecen
independientes.

## Consecuencias

Más tablas y joins a cambio de FKs, borrados seguros y consultas auditables. La
rotación exige rewrap/reencrypt de ciphertext y re-tokenización HMAC como procesos
distintos; el dual read requiere más de una versión de token durante una ventana
acotada. RLS y audit log siguen siendo controles obligatorios: la criptografía no
autoriza acceso ni registra quién lo realizó. No se habilita PII real hasta aprobar
custodio/material de claves, retención, backup/restore y propósito.

## Alternativas descartadas

`subject_type/subject_id`, columnas nullable múltiples, cifrado determinístico,
digest rápido sin clave para identificadores, usar HMAC como si fuera reversible o
anónimo, cifrar contraseñas y tratar un SHA-256 de integridad como confidencialidad
o prueba de origen.
