Objetivo unico: realizar una ronda integral de correcciones sobre la demo H&S Gestion v0.1 a partir del QA funcional realizado, preservando el flujo que ya funciona y sin incorporar normativa, IA, OCR, nueva infraestructura ni funcionalidades fuera del piloto.

IMPORTANTE:
- QA-25 de inicio de auditoria ya fue corregido. Preservar esa solucion.
- Mantener PostgreSQL, RLS, aislamiento multi-tenant, migraciones, Docker y arquitectura actual.
- No debilitar seguridad ni permisos para simplificar la implementacion.
- No implementar motor normativo todavia.
- No agregar portal externo de contratistas.
- No agregar CI remoto ni integraciones.
- Mantener datos de demo 100% sinteticos.
- El objetivo principal es que el piloto sea funcionalmente correcto, intuitivo y presentable a un profesional H&S.

==================================================
P0 - PRESERVAR FLUJO FUNCIONAL
==================================================

Mantener operativo de punta a punta:

obra
-> actores
-> etapas
-> contratistas
-> personal
-> documentacion
-> maquinarias
-> auditoria
-> checklist
-> desvio
-> correccion
-> envio a verificacion
-> rechazo o aceptacion
-> cierre
-> dashboard
-> PDF.

Mantener auditorias finalizadas y eventos cerrados trazables e inmutables.

Agregar o actualizar pruebas de regresion para todos los cambios de esta ronda.

==================================================
P1 - MODELO DE ACTORES, ASIGNACIONES Y PERMISOS
==================================================

Mantener separados:
- persona;
- profesion;
- funcion en la obra;
- organizacion representada;
- obra;
- alcance de permisos.

No resolver permisos solamente por un rol generico.

Funciones principales del proyecto:
- RESPONSABLE_HYS_PROYECTO
- AUDITOR
- RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL
- TECNICO_HYS_CONTRATISTA_PRINCIPAL

Permitir tambien profesionales H&S pertenecientes a otras contratistas. Deben quedar asociados a la empresa concreta que representan y tener alcance limitado a esa empresa salvo delegacion adicional.

Eliminar del selector de identidades la funcion generica "Responsable H&S suplente". No corresponde al modelo validado.

Reemplazar etiquetas genericas:
- "Tecnico de obra" -> "Tecnico H&S de contratista principal"
- "Auditor" -> "Auditor"
- "Responsable H&S" -> "Licenciado H&S del proyecto"

Incorporar claramente como identidad profesional:
- Licenciado H&S de contratista principal.

CONTRATISTA PRINCIPAL:
No eliminarla del sistema. Es un actor organizacional importante y potencial cliente/comprador.
No modelarla como persona ni como profesion "Contratista".
Debe funcionar como cuenta/vista organizacional de supervision.
Debe poder consultar:
- estado general de obra;
- contratistas;
- personal;
- documentacion y vencimientos;
- maquinarias;
- auditorias;
- desvios;
- correcciones;
- cierres;
- indicadores;
- reportes.
No debe ejecutar funciones tecnicas reservadas a profesionales H&S:
- aprobar documentacion;
- ejecutar auditorias;
- validar inspecciones tecnicas;
- autodeclarar cumplimiento;
- cerrar tecnicamente desvios.

CONTRATISTAS:
Simplificar el dominio:
- CONTRATISTA PRINCIPAL
- CONTRATISTA

No mantener como categorias de negocio separadas "contratista secundaria" y "subcontratista".
Preservar la jerarquia mediante una relacion "contratada por" / parent_contractor.
Ejemplo:
Contratista principal -> Contratista A -> Contratista B.

Los permisos de profesionales de contratistas deben depender de:
funcion + obra + empresa representada + alcance delegado.

TECNICO H&S DE CONTRATISTA PRINCIPAL:
Debe poder:
- cargar y mantener contratistas dependientes;
- cargar y mantener personal;
- cargar documentacion;
- registrar nuevas versiones;
- cargar maquinarias;
- realizar inspecciones de maquinaria;
- informar correcciones de desvios;
- cargar evidencias;
- enviar correcciones a verificacion.
No debe:
- ejecutar auditorias generales del proyecto;
- aprobar su propia documentacion;
- verificar/cerrar una correccion que el mismo realizo.

TECNICOS H&S DE OTRAS CONTRATISTAS:
Mismas capacidades operativas pero limitadas a su propia empresa y alcance asignado.
No pueden modificar datos de otras contratistas.

AUDITOR DELEGADO:
Debe poder:
- consultar estructura de contratistas;
- consultar personal;
- verificar habilitacion del personal;
- registrar como hallazgo/desvio una persona presente pero no registrada;
- revisar documentacion;
- aprobar, observar o rechazar documentacion;
- iniciar y ejecutar auditorias;
- completar checklist;
- crear desvios mediante NO_CUMPLE;
- revisar correcciones;
- consultar correcciones sin permiso para verificar o cerrar como Auditor.
No debe:
- editar datos maestros de contratistas;
- editar datos maestros del personal como tarea habitual;
- corregir el mismo desvio que luego verifica.

Regla canónica de independencia del desvio:
Sólo un Responsable H&S autorizado puede verificar o cerrar.
El creador del desvio y el autor de la correccion quedan excluidos.
Quien detecto el desvio NO puede verificarlo ni cerrarlo; tampoco el autor de la correccion. La verificacion exige Responsable H&S autorizado.

El auditor delegado puede crear una obra solamente si tiene delegacion/habilitacion explicita del Licenciado H&S responsable. Esa habilitacion debe ser trazable.

LICENCIADO H&S DEL PROYECTO:
Debe conservar capacidad amplia de gestion:
- alta y mantenimiento cuando corresponda;
- personal;
- etapas;
- documentacion;
- auditorias;
- revision;
- verificacion;
- cierre;
- delegaciones.
Puede modificar etapas de obra.

==================================================
P2 - ALTA DE OBRA Y ASIGNACIONES
==================================================

No crear nuevas obras desde un formulario pequeno incrustado en la barra lateral.

"Nueva obra" debe abrir una vista/pantalla propia.

Alta inicial simple:
- codigo;
- nombre;
- pais;
- provincia;
- municipio.

No mostrar regex ni mensajes tecnicos.
Si el codigo tiene espacios/minusculas, normalizar cuando sea seguro o mostrar:
"El codigo solo puede contener letras, numeros y guiones. Ejemplo: OBRA-001."

Separar jurisdiccion:
- Pais
- Provincia
- Municipio

No implementar normativa con esos datos todavia.

Una obra nueva NO debe heredar automaticamente:
- auditor delegado;
- licenciado de contratista principal;
- tecnico de contratista principal;
- otros actores arbitrarios.

Una obra nueva debe iniciar sin asignaciones profesionales salvo una asignacion explicita y justificable del creador.

Despues de crear la obra mostrar onboarding:

1. Configurar responsables y actores H&S
2. Registrar contratista principal
3. Definir etapa inicial
4. Incorporar contratistas/personal
5. Preparar documentacion

Agregar una gestion clara de "Actores y funciones de esta obra".

Mostrar para cada actor:
- nombre;
- profesion;
- funcion;
- empresa representada;
- alcance.

Las asignaciones deben respetar:
Responsable H&S proyecto -> representa Proyecto/Obra
Auditor -> representa Proyecto/Obra
Licenciado H&S contratista principal -> representa Contratista Principal
Tecnico H&S contratista principal -> representa Contratista Principal
Profesionales de otras contratistas -> representan su contratista especifica.

==================================================
P3 - HOME, NAVEGACION Y UX GENERAL
==================================================

Agregar siempre una forma clara de volver:
Obras -> Obra seleccionada
o boton "< Volver a obras".

La Home debe ser contextual por usuario/asignacion.

No mostrar exactamente la misma portada para todos.

Tecnico H&S:
mostrar pendientes operativos:
- documentacion para cargar;
- vencimientos;
- correcciones;
- contratistas;
- personal.

Auditor:
mostrar:
- auditorias;
- documentacion pendiente de revision;
- verificaciones pendientes;
- hallazgos;
- personal no habilitado/no registrado.

Licenciado H&S proyecto:
mostrar:
- estado H&S de obras;
- documentos vencidos;
- desvios;
- verificaciones;
- auditorias;
- pendientes.

Contratista Principal organizacional:
mostrar dashboard ejecutivo:
- estado documental;
- vencimientos;
- desvios;
- auditorias;
- maquinarias;
- contratistas;
- progreso;
- indicadores.

Regla UX:
cada pantalla debe responder rapidamente:
1. Que esta pasando?
2. Que tengo que hacer?
3. Cual es el siguiente paso?

No mostrar enums internos al usuario.

Traducir:
PRINCIPAL
CONTRACTOR
SUBCONTRACTOR
LICENCIADO_HYS
TECNICO_HYS
AUDITOR
NO_CUMPLE
NO_APLICA
NO_VERIFICADO
EN_CORRECCION
PENDIENTE_VERIFICACION
CREATED_FROM_CONTROL
CORRECTION_ADDED
SUBMITTED_FOR_VERIFICATION
VERIFICATION_RECHAZADA
VERIFICATION_ACEPTADA

a lenguaje natural en castellano.

No cambiar los enums internos si no es necesario.

Corregir header actual donde textos aparecen pegados:
"AuditorProfesion..."
"Tecnico de obraProfesion..."
etc.

Mostrar de manera legible:
Nombre/funcion
Profesion
Empresa representada
Alcance.

==================================================
P4 - PERSONAL
==================================================

Tecnicos cargan y mantienen personal.

Licenciado puede intervenir y gestionar cuando corresponda.

Auditor no modifica ficha maestra normalmente.

Agregar concepto de verificacion/habilitacion del trabajador en la obra, separado de editar sus datos.

Estados sugeridos:
- PENDIENTE_VERIFICACION
- HABILITADO
- DOCUMENTACION_INCOMPLETA
- NO_HABILITADO

Registrar:
- quien verifico;
- funcion;
- fecha;
- observacion/motivo.

En auditoria permitir detectar una persona presente que no figura en la nomina:
"Persona no registrada en obra"
-> generar hallazgo/desvio sin que el auditor tenga que crear silenciosamente una ficha de personal.

No mostrar profesionales del Proyecto como si pertenecieran a la Contratista Principal.

==================================================
P5 - DOCUMENTACION
==================================================

Separar completamente:
CARGA DOCUMENTAL
de
REVISION DOCUMENTAL.

Tecnico:
- carga documento;
- sujeto;
- tipo;
- fechas;
- archivo/evidencia;
- nueva version;
- envia a revision.

No puede elegir "APROBADO" al cargar.

Documento nuevo debe quedar:
PENDIENTE DE REVISION.

Licenciado/Auditor autorizado:
sobre un documento existente debe poder:
- APROBAR;
- OBSERVAR;
- RECHAZAR;
- agregar fundamento.

Registrar:
- cargado por;
- fecha de carga;
- revisado por;
- funcion del revisor;
- fecha de revision;
- resultado;
- fundamento.

Mantener separados:
Estado de revision:
- pendiente;
- aprobado;
- observado;
- rechazado.

Estado de vigencia:
- vigente;
- por vencer;
- vencido.

Un documento puede estar aprobado y luego vencido.

==================================================
P6 - MAQUINARIAS
==================================================

Mantener historial de inspecciones.

Separar:
alta administrativa del equipo
de
inspeccion tecnica.

Ampliar ficha minima:
- tipo;
- codigo interno;
- descripcion;
- marca;
- modelo;
- dominio/patente cuando aplique;
- contratista/propietario;
- operador asignado cuando corresponda.

Preparar documentacion asociada:
- seguro;
- VTV/RTO cuando aplique;
- documentacion vehicular;
- carnet/licencia/habilitacion del operador;
- certificados aplicables.

No implementar normativa automatica.

Inspeccion:
incorporar checklist basico:
- frenos;
- luces;
- alarma de retroceso;
- bocina;
- neumaticos;
- espejos;
- cinturon;
- matafuego;
- balizas;
- perdidas;
- protecciones;
- señalizacion;
- dispositivos especificos.

Resultados:
- CUMPLE
- NO_CUMPLE
- NO_APLICA
- NO_VERIFICADO

Estado del equipo:
- OPERATIVA
- CON_OBSERVACIONES
- FUERA_DE_SERVICIO

Registrar inspector:
- persona;
- funcion;
- fecha;
- evidencia.

Permitir validacion posterior cuando corresponda, separada de la inspeccion.

==================================================
P7 - AUDITORIAS
==================================================

Mantener auditorias finalizadas inmutables.

Agregar historial navegable de auditorias.

Actualmente despues de finalizar una auditoria se muestra otra auditoria anterior y no se puede abrir claramente la recien realizada.

Crear listado/selector:
- ID de auditoria;
- fecha;
- auditor;
- funcion;
- estado.

Permitir abrir cualquier auditoria historica en modo lectura.

Mostrar observaciones de cada control despues del cierre.

Auditoria finalizada debe mostrar:
- ID;
- fecha/hora inicio;
- fecha/hora cierre;
- auditor;
- asignacion funcional;
- responsable profesional asociado;
- controles;
- resultado;
- observaciones;
- desvios generados;
- evidencias.

Mantener:
NO_CUMPLE -> genera desvio automaticamente.

==================================================
P8 - DESVIOS, CORRECCION Y CIERRE
==================================================

Hacer el flujo extremadamente intuitivo.

Mostrar claramente:
ID del desvio
Origen
Auditoria
Fecha
Control
Detectado por
Contratista/persona/maquinaria afectada
Responsable de corregir
Criticidad
Plazo
Estado.

Generar ID visible y legible para evitar confundir desvios similares.

Flujo:
ABIERTO
-> EN_CORRECCION
-> PENDIENTE_VERIFICACION
-> CERRADO

Si verificacion rechazada:
PENDIENTE_VERIFICACION -> EN_CORRECCION

Acciones por rol:

Tecnico/responsable operativo:
- Informar correccion
- Adjuntar evidencia
- Enviar a verificacion

Auditor/Licenciado autorizado:
- Ver correccion
- Ver evidencia
- Aceptar y cerrar
- Rechazar y devolver
- Fundamento

No mostrar al Auditor/Licenciado verificador formularios de "Agregar correccion" si esta actuando como verificador.

No mostrar al tecnico botones de cierre/verificacion de su propia correccion.

Despues de agregar una correccion, hacer muy evidente:
"Siguiente paso: Enviar a verificacion."

EVIDENCIA:
Preparar soporte para fotos/archivos, no solo texto.
Relacionar evidencia con:
- desvio;
- correccion;
- usuario;
- fecha.

TRAZABILIDAD:
Preservar todos los eventos pero traducirlos visualmente.

Ejemplo:
"05/09 11:12 - Desvio detectado durante auditoria"
"05/09 11:19 - Tecnico H&S informo correccion"
"05/09 11:22 - Correccion enviada a verificacion"
"05/09 11:26 - Correccion rechazada: Hay faltantes"
"05/09 11:29 - Nueva correccion informada"
"05/09 11:30 - Correccion verificada. Desvio cerrado"

No mostrar al usuario nombres de eventos internos salvo en logs tecnicos.

==================================================
P9 - ETAPAS
==================================================

Auditor:
solo consulta.

Tecnico H&S:
puede registrar y actualizar etapas.

Licenciado H&S proyecto:
puede registrar, modificar, activar y cerrar etapas.

Mantener posibilidad de varias etapas simultaneas.

Usar selector de etapas conocidas en lugar de exigir nombre libre:
- Preparacion
- Demolicion
- Excavacion
- Submuracion
- Fundaciones
- Estructura
- Albanileria
- Instalaciones
- Terminaciones
- Cierre

Mantener sector, inicio, fin opcional y notas.

Registrar historial:
quien modifico etapa;
fecha;
cambio realizado.

No activar normativa todavia.

==================================================
P10 - DASHBOARD
==================================================

Mantener los datos actuales pero volverlos accionables.

Priorizar:
- vencidos;
- pendientes;
- desvios abiertos;
- verificaciones pendientes;
- maquinaria fuera de servicio;
- ultima auditoria.

En lugar de mostrar solamente contadores, usar mensajes claros:
"1 documento vencido requiere accion"
"1 desvio abierto"
"1 correccion pendiente de verificar".

Ratio de auditoria:
no mostrar solamente "50% CUMPLE".
Mostrar contexto:
3 controles totales
1 cumple
1 no cumple
1 no aplica
y porcentaje como indicador secundario.

Cuando no existen auditorias, reemplazar "Sin base" por:
"Aun no hay auditorias realizadas."

Dashboard de obra nueva:
en lugar de solo tarjetas en cero, mostrar onboarding inicial.

==================================================
P11 - PDF Y REPORTES
==================================================

El PDF actual no debe eliminarse. Reconvertirlo en:
"Reporte Ejecutivo de Obra".

Crear ademas:
"Informe de Auditoria".

REPORTE EJECUTIVO:
- membrete H&S Gestion;
- empresa/organizacion;
- obra;
- estado;
- documentacion;
- vencimientos;
- desvios;
- maquinarias;
- ultima auditoria;
- indicadores;
- fecha de generacion.

INFORME DE AUDITORIA:
Debe ser profesional, membretado y presentable.

Encabezado:
- logo H&S Gestion;
- empresa/estudio usuario;
- nombre de obra;
- codigo;
- direccion/jurisdiccion;
- fecha;
- ID de auditoria;
- estado.

Responsables:
- Licenciado H&S proyecto;
- Tecnico auditor delegado;
- Contratista principal;
- Licenciado H&S contratista principal;
- Tecnico H&S contratista principal cuando corresponda.

Datos de auditoria:
- inicio;
- cierre;
- etapa;
- auditor;
- funcion;
- responsable profesional asociado.

Personal:
- resumen de presentes;
- estado de habilitacion;
- personas no registradas si las hubo.

Documentacion:
- vigente;
- por vencer;
- vencida;
- pendiente;
- observada/rechazada.

Maquinarias:
- equipos;
- estado;
- inspecciones relevantes.

Checklist:
para cada control:
- descripcion;
- resultado;
- observacion;
- evidencia.

Desvios:
- ID;
- hallazgo;
- criticidad;
- responsable;
- plazo;
- estado.

Seguimiento:
- correcciones;
- evidencias;
- rechazos;
- aceptacion;
- cierre.

Evidencias fotograficas cuando existan.

Pie:
"Documento generado por H&S Gestion a partir de registros trazables del sistema."
Para la demo:
"Demo funcional - datos sinteticos - no constituye certificacion legal."

No simular firma digital ni certificacion juridica.

==================================================
VALIDACION FINAL
==================================================

Antes de terminar:
- ejecutar migraciones si son necesarias;
- API tests;
- web tests;
- lint;
- typecheck;
- build;
- PostgreSQL/RLS;
- seed idempotente;
- smoke runtime;
- flujo completo de demo.

Crear o actualizar pruebas especificas para:
- permisos por funcion/empresa;
- creador del desvio y autor de la correccion no pueden verificar; sólo Responsable H&S independiente;
- tecnico no puede autoverificar;
- revision documental separada;
- obra nueva sin actores heredados;
- historial de auditorias;
- jerarquia de contratistas unificada;
- vista organizacional Contratista Principal.

No hacer commit automaticamente.

Detenerse con:
1. resumen de cambios;
2. decisiones de dominio aplicadas;
3. migraciones;
4. archivos modificados;
5. pruebas ejecutadas;
6. resultados;
7. incompatibilidades;
8. funcionalidades pendientes por decision profesional;
9. confirmacion de que el flujo demo sigue operativo punta a punta.
