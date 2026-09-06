# BLOQUE RESPONSABLES - H&S GESTION

Trabajar exclusivamente sobre la actual pestaña "Actores" de una obra y su lógica de asignaciones.

NO tocar:
- Nueva obra
- Home
- header general
- documentación
- personal
- maquinaria
- auditorías
- desvíos
- dashboard
- PDFs
- normativa
salvo cambios mínimos estrictamente necesarios para soportar este bloque.

## 1. Cambio conceptual y visual

Renombrar la pestaña "Actores" a:

RESPONSABLES

La pantalla ya no debe exponer al usuario el modelo técnico genérico:
- identidad sintética
- persona profesional
- función en la obra
- empresa representada
- alcance

La arquitectura interna persona + profesión + función + empresa + obra + alcance debe conservarse en backend, pero no mostrarse como un formulario genérico al usuario.

## 2. Diseño de la pantalla

Mostrar una sección clara titulada:

"Responsables de la obra"

Mostrar como mínimo estas responsabilidades:

1. Responsable H&S del proyecto
2. Auditor
3. Responsable H&S de contratista principal
4. Técnico H&S de contratista principal

Cada responsabilidad debe mostrarse como una tarjeta/fila clara con:

- nombre de la persona asignada
- profesión
- empresa/organización representada cuando corresponda
- estado de la asignación
- fecha de vigencia si existe

Para Auditor:
- Auditor es una FUNCION, no una profesión.
- Puede ejercerla un Licenciado H&S o un Técnico H&S.
- Si el Auditor es un Técnico delegado, mostrar de forma legible:
  "Delegado por: [nombre del Licenciado H&S responsable]"
- Mantener la trazabilidad existente mediante delegated_by_assignment_id o el mecanismo vigente.

Si no existe una persona asignada, mostrar:
"Pendiente de asignar"

## 3. Administración de asignaciones

Únicamente pueden crear, cambiar o finalizar asignaciones de responsables:

- CONTRATISTA PRINCIPAL
- LICENCIADO H&S DEL PROYECTO

Para estos perfiles mostrar acciones contextuales como:

- "Asignar"
- "Cambiar responsable"
- "Cambiar auditor"
- "Cambiar técnico"

según corresponda.

Los siguientes perfiles deben tener esta sección SOLO LECTURA:

- Técnico H&S de contratista principal
- Auditor
- Licenciado H&S de contratista principal

No alcanza con ocultar botones en frontend:
el backend debe rechazar modificaciones de asignaciones realizadas por perfiles no autorizados.

## 4. UX de asignación

Al presionar Asignar o Cambiar, mostrar únicamente los campos necesarios para esa responsabilidad.

No volver a mostrar el formulario genérico actual de cuatro selectores.

Ejemplos:

Para Responsable H&S del proyecto:
- seleccionar profesional compatible

Para Auditor:
- seleccionar persona
- mostrar profesión
- si requiere delegación, seleccionar/registrar Licenciado delegante según las reglas vigentes

Para Responsable H&S de contratista principal:
- seleccionar profesional correspondiente

Para Técnico H&S de contratista principal:
- seleccionar técnico correspondiente

No permitir combinaciones incompatibles de profesión, función o empresa.

## 5. Historial

Agregar debajo una sección secundaria:

"Historial de responsables"

Preferentemente colapsable/desplegable.

Debe conservar y mostrar de manera humana la trazabilidad de asignaciones anteriores:

- persona
- función
- fecha desde
- fecha hasta cuando corresponda
- quién realizó/asignó el cambio cuando exista ese dato
- delegación del Auditor cuando corresponda

No mostrar enums o nombres técnicos internos al usuario.

## 6. Preservar dominio y datos

No eliminar modelos de actores, profesiones, funciones, scopes ni organizaciones.

El cambio principal es:
- simplificar la experiencia de usuario
- restringir correctamente quién administra asignaciones
- conservar la arquitectura y trazabilidad interna.

Preservar los datos sintéticos existentes y adaptar el seed solamente si es necesario.

## 7. Validación

Agregar/actualizar pruebas específicas para confirmar:

- Contratista principal puede administrar responsables.
- Licenciado H&S del proyecto puede administrar responsables.
- Técnico H&S de contratista principal NO puede modificarlos.
- Auditor NO puede modificarlos.
- Licenciado H&S de contratista principal NO puede modificarlos.
- lectura sigue disponible para todos los perfiles autorizados a acceder a la obra.
- Auditor conserva profesión independiente de su función.
- delegación del Auditor técnico queda trazable.
- historial no se pierde al cambiar una asignación.
- build web y TypeScript siguen pasando.
- tests API relacionados siguen pasando.

No hacer commit.

Al finalizar, detenerse y entregar:
1. resumen de lo implementado,
2. archivos modificados,
3. migraciones creadas si las hubiera,
4. tests ejecutados y resultado,
5. cualquier decisión funcional que haya quedado ambigua.
