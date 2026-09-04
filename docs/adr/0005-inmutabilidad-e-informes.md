# ADR-0005 — Snapshots, inmutabilidad e informes reproducibles

- Estado: Propuesto
- Fecha: 2026-09-02

## Contexto

Catálogos, documentos y normativa evolucionan. Consultar siempre el estado actual
haría cambiar auditorías/reportes históricos; update/delete silencioso rompe la
trazabilidad.

## Decisión

Finalizar una auditoría congela asistencia, scope, control definitions/results,
referencias regulatorias y hashes relevantes. Evidencia/corrección/verificación,
audit log y reportes son append-only. Cerrar exige RHS distinto del autor.

PDF se genera en worker desde snapshot + `ReportTemplateVersion` allowlist, guarda
hash del snapshot/archivo y variante full/redacted. Regenerar crea nueva versión.
Conformidad simple registra consentimiento/trazo cifrado y aviso de no firma digital.

## Consecuencias

Históricos reproducibles y auditables a cambio de almacenamiento y versionado.
Correcciones crean eventos/versiones. DB roles/policies y tests impiden update/delete.

## Alternativas descartadas

Render desde tablas vivas, sobrescribir PDF, HTML arbitrario y permitir reapertura
de auditoría cerrada.

