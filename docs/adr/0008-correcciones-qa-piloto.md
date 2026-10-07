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
- La independencia de desvíos sigue el blueprint canónico: sólo un Responsable
  H&S autorizado puede verificar/cerrar; nunca el creador del desvío ni el autor
  de la corrección. La interpretación previa que permitía verificar al detector
  queda sustituida por esta regla canónica.
- Los reportes ejecutivo y de auditoría se generan desde el estado persistido y
  ahora incluyen responsabilidades, documentación, revisiones, maquinaria,
  inspecciones, etapas, desvíos y trazabilidad; continúan siendo demostrativos
  y no representan certificación legal.

## Fuera de alcance

Autenticación productiva, normativa real, OCR/IA, archivos binarios, portal de
contratistas e integraciones externas.

## Revisión documental por versión

Toda revisión nueva identifica la versión documental vigente e inmutable y
exige un revisor distinto de su autor. Las revisiones históricas sin vínculo
conocido conservan su vínculo nulo; no se reconstruye ni se inventa su versión.
La migración `20261006_0012` conserva esas filas y exige vínculo para filas
nuevas. El rollback conserva las revisiones pero elimina el vínculo añadido;
requiere volver conjuntamente a la API anterior.

## Metadatos de legajos del piloto

Las acciones de carga/actualización del legajo usan el documento y sus versiones
existentes; no crean un almacenamiento paralelo ni aceptan archivos binarios.
La disponibilidad de servicios auxiliares y la carga horaria semanal se guardan
en `Document.notes` con el marcador `hys.technical_metadata.v1`. `detail` conserva
el texto humano, y las actualizaciones conservan claves desconocidas, notas
legadas y fechas de vigencia. El editor no presenta el JSON como nota humana.

Se reutiliza así la persistencia, el historial y el reinicio de revisión del
documento: cada cambio crea una versión `PENDIENTE`. La API valida tipos, horas
entre 1 y 168 en intervalos de media hora, y referencia a un auditor vigente de
la misma obra/organización. El auditor puede ser distinto del actor que completa
el programa. Su nombre y profesión provienen de la asignación real, no de
valores predeterminados editables.

Esta representación está limitada al piloto sintético. Evita otra migración y
mantiene compatible el texto legado, a cambio de no permitir consultas SQL
tipadas por estos campos. Si se requiere esa consulta en un hito posterior,
deberá diseñarse una migración explícita sin reescribir versiones históricas.

## Confirmación de transacción y selección de obra

La unidad de trabajo del piloto termina antes de enviar la respuesta HTTP:
`get_pilot_service` declara `Depends(get_pilot_context, scope="function")`.
Las rutas materializan DTO o bytes PDF dentro de la operación; no hay streams,
lecturas diferidas ni tareas de fondo que consuman esa transacción. La sesión
padre conserva alcance de request. Así un fallo de commit no anuncia un 201
exitoso. Se sigue el [alcance de dependencia documentado por FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope),
sin commits manuales adicionales ni cambios del contrato OpenAPI.

Una respuesta de listado puede ser anterior al alta confirmada. La navegación
consulta el detalle seleccionado para resolver su visibilidad, en lugar de
revocarla por ausencia en ese snapshot. Un 403/404 vigente elimina selección y
datos visibles; un error transitorio no se interpreta como pérdida de permisos.
El cambio de actor sigue invalidando respuestas y datos del actor anterior.
