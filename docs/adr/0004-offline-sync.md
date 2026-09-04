# ADR-0004 — Paquete offline cifrado y sincronización explícita

- Estado: Propuesto
- Fecha: 2026-09-02

## Contexto

Campo requiere modo avión incluso en Safari/iOS. Caches web comunes, Background
Sync exclusivo o último cambio gana no protegen datos ni evidencia.

## Decisión

Paquete de una obra/auditoría, editor+dispositivo únicos y TTL siete días. Cliente
cifra IndexedDB/fotos con AES-GCM y clave derivada de contraseña offline que nunca
llega al servidor. Sólo datos mínimos/enmascarados.

Mutaciones tienen UUID, sequence, idempotency key y base version. Sync se dispara
en primer plano al volver conexión; servidor manda en maestros, aplica una vez y
crea `SyncConflict` para divergencias. Fotos se purgan sólo tras acuse. Revocación
impide reabrir/sincronizar según política sin borrar evidencia pendiente a ciegas.

## Consecuencias

Funciona en navegadores objetivo y preserva conflictos, pero aumenta pruebas de
crypto/storage/reintento. Olvidar contraseña obliga a purgar/descargar de nuevo.
No se prometen sincronización silenciosa ni recuperación de clave local.

## Alternativas descartadas

Service worker cache sin cifrar, token servidor como clave, Background Sync como
único mecanismo, LWW y editar una auditoría desde múltiples dispositivos.

