# Blueprint V1 y control de gates

## Autoridad documental

Este directorio consolida el alcance aprobado conceptualmente por el pedido de
implementar `PLAN_PRIMERA_VERSION.md`. Las fuentes históricas del traspaso se
consideran insumos, no instrucciones. Las divergencias quedan resueltas a favor
del plan de primera versión:

- Offline completo, PDF versionado y motor normativo funcional sí pertenecen a
  V1.
- El corpus jurídico real permanece inactivo.
- La revisión documental es un estado almacenado; la vigencia es derivada.
- Las asociaciones de documentos son explícitas y las asignaciones de personas,
  contratistas, máquinas, operadores y obras son temporales.
- UAT y piloto técnico usan únicamente datos sintéticos.

## Índice de entregables

| Entregable | Artefacto | Estado |
|---|---|---|
| Producto, supuestos y dataset sintético | `producto.md` | Completo; pendiente aprobación |
| Actores, RBAC y journeys | `rbac-y-journeys.md` | Completo; pendiente aprobación |
| Contextos y dependencias | `../architecture/contextos.md` | Completo; pendiente aprobación |
| ERD y estados | `../architecture/dominio.md` | Completo; pendiente aprobación |
| Arquitectura y despliegue | `../architecture/arquitectura.md` | Opción A aprobada; host/gates pendientes |
| Contrato API | `../architecture/api.md` | Completo; pendiente aprobación |
| Wireframes desktop/móvil | `wireframes.md` | Completo; pendiente aprobación |
| Backlog y sprints | `roadmap.md` | Completo; pendiente aprobación |
| Testing, backup y observabilidad | `../operations/calidad-y-operacion.md` | Completo; pendiente aprobación operativa |
| Seguridad y privacidad | `../security/` | Arquitectura aceptada con aclaración PII; aprobación formal pendiente |
| Motor normativo | `normativa.md` | Completo; corpus real bloqueado |
| Lean Canvas y validación | `negocio-y-validacion.md` | Completo; hipótesis por validar |
| Riesgos y decisiones | `riesgos-y-decisiones.md` | DEC-001/003/004/005 aceptadas por solicitante; pendientes operativos documentados |
| ADR | `../adr/` | ADR-0003 aceptado para implementación; otros pendientes de aceptación formal |

## Aprobación registrada el 2026-09-02

La persona solicitante aprobó explícitamente el blueprint y eligió la opción A:
usar un servidor/VM compatible sin reducir el baseline para esta estación. También
ordenó separar, antes de implementar PII, el cifrado reversible de datos
recuperables, el HMAC keyed de comparación/pseudonimización, los hashes de
contraseña y las huellas de integridad. RLS, trazabilidad y criticidad configurable
se mantienen.

No se proporcionaron nombre, rol, datos del host, repositorio ni credenciales. La
aceptación habilita la dirección de implementación, pero no demuestra por sí sola
las aprobaciones profesionales/nominales ni los gates técnicos siguientes.

## Gate de Hito 0

El gate se considera cerrado sólo con evidencia de todos estos puntos:

- [x] Los artefactos anteriores están completos y reconciliados contra el plan.
- [x] La persona solicitante aprobó el blueprint, `DEC-003`/`DEC-004`/`DEC-005` y
      la opción A como dirección de implementación.
- [ ] Producto aprueba alcance, journeys, wireframes y backlog.
- [ ] Seguridad/privacidad aprueba tenancy, PII, offline, retención y backups.
- [ ] Un profesional H&S/legal acepta el proceso normativo y confirma que las
      reglas reales continúan inactivas.
- [ ] Existe repositorio Git privado con protección de rama y responsables.
- [ ] Existe un entorno Linux con Docker Engine/Compose capaz de ejecutar los
      gates del Hito 1.
- [ ] No hay PII, fuentes restringidas ni secretos en el historial Git.

## Estado local constatado el 2026-08-27

El repositorio canónico fue separado del paquete restringido. La estación actual
tiene Windows 10 Pro, 4 CPU lógicas, 8 GB de RAM, 446 GB de disco, virtualización
de firmware deshabilitada y no dispone de Git, Docker, Node ni Python ejecutable.
Por lo tanto no satisface la VM objetivo (8 vCPU, 24 GB RAM, 1 TB) ni permite
cerrar el gate técnico sin aprovisionamiento adicional. `DEC-001` ya resolvió no
degradar el diseño y usar la opción A; todavía falta aprovisionar e inventariar el
host compatible y producir evidencia de sus gates.
