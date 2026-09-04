# ADR-0007 — Actores sintéticos y funciones por obra

**Estado:** aceptado para el corte piloto

## Decisión

Mantener el adaptador de actores sintéticos existente y persistir su función en
`WORKSITE_FUNCTIONAL_ASSIGNMENT`. La profesión controlada vive en `PERSON`, la
empresa representada es una relación de la asignación y el alcance se guarda de
forma explícita. No se introduce un modelo de autenticación nuevo.

La participación de una empresa en una obra distingue `PRINCIPAL`, `CONTRACTOR`
y `SUBCONTRACTOR` y puede referenciar una empresa contratante de la misma obra y
tenant. Sólo una participación puede ser principal.

Las auditorías guardan la obra, actor, asignación, fecha y persona profesional
asociada cuando está disponible. Los campos históricos de autor/editor se
conservan para compatibilidad.

La demo persiste exactamente cuatro asignaciones funcionales de personas: auditor
delegado, responsable H&S de proyecto, responsable H&S del contratista principal y
técnico H&S del contratista principal. El selector legado
`responsable-suplente` representa al responsable H&S del contratista principal;
`contratista-principal` identifica a la empresa y no crea una asignación de usuario.

## Consecuencias

- La autorización de acciones de auditoría deja de depender únicamente del texto
  de rol y verifica asignación, obra y vigencia.
- Las auditorías históricas pueden conservar campos de asignación nulos cuando
  el actor no podía determinarse con seguridad.
- El seed sintético puede mostrar la cadena principal → contratista →
  subcontratista sin convertir empresas en usuarios.

## Fuera de alcance

Autenticación productiva, portal de contratistas, normativa real e integraciones.
