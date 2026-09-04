# ADR-0002 — Aislamiento tenant y scopes

- Estado: Aceptado para implementación por la persona solicitante; validación
  nominal de arquitectura/seguridad y evidencia técnica pendientes
- Fecha: 2026-09-02

## Contexto

V1 opera una organización, pero debe impedir que el esquema y código vuelvan
costoso/arriesgado habilitar una segunda. Filtros voluntarios aislados son
insuficientes frente a IDOR o consultas nuevas.

## Decisión

Todo agregado salvo Organization lleva `organization_id NOT NULL`. FKs y uniques
son tenant-aware; el contexto autenticado fija tenant y scope antes del acceso.
Repositorios exigen `AuthorizationContext` y no aceptan tenant desde el body.
PostgreSQL RLS se activa desde la migración inicial en todas las tablas operativas
tenant-aware, además de los filtros de aplicación. El rol de runtime no es owner,
no tiene `BYPASSRLS`, fija el contexto tenant de forma transaccional y las tablas
usan `FORCE ROW LEVEL SECURITY` donde corresponda. Jobs y tareas privilegiadas
usan roles separados y explícitos, no una omisión implícita de la política.

Colecciones filtran antes de agregar/paginar y UUID fuera de scope devuelve 404.
Fixtures siempre incluyen una organización señuelo y tests negativos por endpoint.

## Consecuencias

Hay defensa en profundidad y evidencia repetible, a cambio de más constraints,
contexto de conexión y pruebas. Jobs/migraciones usan roles separados y no eluden
RLS accidentalmente. La existencia de columnas no autoriza multitenancy productiva.

## Alternativas

DB por tenant (demasiada operación para V1) y sólo filtros de aplicación (riesgo de
omisión). Posponer RLS hasta una segunda organización también se descarta: la
decisión aprobada exige probarla desde el primer esquema y endpoint tenant-aware.
