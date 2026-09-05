# ADR-0008 — Correcciones de QA del corte piloto

**Estado:** aceptado para el corte piloto

## Decisión

El piloto separa la carga de datos operativos de las verificaciones técnicas.
Documentos, habilitaciones de personas, inspecciones de maquinaria y cambios de
etapa se registran con actor, función, fecha y fundamento cuando corresponde.

Las revisiones, validaciones y eventos de etapa son históricos y append-only. La
vista actual se deriva de esos registros: los documentos nuevos comienzan en
`PENDIENTE`, las inspecciones mantienen checklist/evidencia y las etapas exponen
estado e historial.

La creación de obras recibe país, provincia y municipio, no hereda asignaciones
funcionales y se mantiene dentro del adaptador de actores sintéticos. El
contratista principal conserva una vista organizacional de solo lectura; las
acciones técnicas continúan protegidas por función, obra y alcance.

## Consecuencias

- El esquema requiere una migración reversible `20260905_0007` con RLS y grants
  explícitos para las nuevas tablas históricas.
- El contrato OpenAPI y el cliente web se regeneran desde `apps/api/openapi.json`.
- La independencia de desvíos se conserva: quien creó la corrección no puede
  verificarla; quien detectó el desvío sí puede hacerlo cuando otra persona
  registró la corrección.
- Los reportes ejecutivo y de auditoría se generan desde el estado persistido y
  continúan siendo demostrativos; no representan certificación legal.

## Fuera de alcance

Autenticación productiva, normativa real, OCR/IA, archivos binarios, portal de
contratistas e integraciones externas.
