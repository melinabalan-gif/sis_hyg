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

Las funciones profesionales de contratistas se asignan explícitamente a la
empresa representada. El personal de proyecto puede no tener empresa asociada;
esa asociación no se infiere por crear la persona ni por asignarla a una obra.
Registrar una maquinaria no crea una inspección implícita: cada inspección debe
aportar un checklist técnico completo de trece controles.

Una auditoría finalizada y sus controles quedan protegidos también en base de
datos mediante triggers de inmutabilidad. Las correcciones, verificaciones,
revisiones documentales e inspecciones posteriores se agregan como nuevos
eventos, sin sobrescribir la historia.

## Consecuencias

- El esquema requiere la migración `20260905_0008`, con RLS, grants explícitos,
  responsabilidades de desvíos y protección de auditorías finalizadas.
- El downgrade conserva nullable la asociación opcional de personal para no
  descartar datos; volver a `NOT NULL` requiere una migración explícita que
  asigne primero esas filas a una empresa.
- El contrato OpenAPI y el cliente web se regeneran desde `apps/api/openapi.json`.
- La independencia de desvíos se conserva: quien creó la corrección no puede
  verificarla; quien detectó el desvío sí puede hacerlo cuando otra persona
  registró la corrección.
- Los reportes ejecutivo y de auditoría se generan desde el estado persistido y
  ahora incluyen responsabilidades, documentación, revisiones, maquinaria,
  inspecciones, etapas, desvíos y trazabilidad; continúan siendo demostrativos
  y no representan certificación legal.

## Fuera de alcance

Autenticación productiva, normativa real, OCR/IA, archivos binarios, portal de
contratistas e integraciones externas.
