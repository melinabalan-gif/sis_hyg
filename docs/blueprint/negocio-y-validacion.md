# Lean Canvas y validación del piloto

## Lean Canvas

| Bloque | Hipótesis V1 |
|---|---|
| Problema | vencimientos tardíos; legajos dispersos; auditorías lentas; desvíos sin trazabilidad; control manual de máquinas |
| Segmentos | constructoras/estudios H&S con varias obras y responsables corporativos; early adopters con dolor documental y visitas frecuentes |
| Propuesta única | control operativo de la obra que conecta legajos, campo, correcciones e histórico, incluso offline |
| Solución | obra central, vigencias, maquinaria, auditoría PWA, desvíos verificables, PDF y dashboard reconciliado |
| Alternativas | planillas, carpetas compartidas, mensajería, software documental/contratistas y formularios genéricos |
| Canales | venta consultiva, redes profesionales H&S, cámaras/partners y pilotos acompañados |
| Ingresos | hipótesis: fee base por organización + escala por obras activas; onboarding separado; sin fijar precio antes del piloto |
| Costos | desarrollo/soporte, hosting/backup, seguridad, onboarding, almacenamiento, validación H&S/legal y adquisición |
| Métricas clave | tiempo de auditoría/documentación, anticipación de vencimientos, cierre de desvíos, WAU, uso offline, errores y voluntad de pago |
| Ventaja buscada | modelo longitudinal centrado en obra y trazabilidad cruzada; no se presume ventaja defendible hasta validarla |

## Diseño del piloto

- Duración objetivo: 4–8 semanas después del UAT sintético y del gate de datos reales.
- Cohorte: 1–3 organizaciones candidatas, empezando con una sola operativa.
- Antes: medir durante dos ciclos el proceso actual con el mismo criterio.
- Durante: onboarding acompañado, entrevista semanal y registro de incidentes.
- Después: comparar baseline, costo de carga, recurrencia y propuesta comercial.

## Experimentos y umbrales de decisión

| Hipótesis | Experimento | Señal para continuar | Señal para revisar/detener |
|---|---|---|---|
| La auditoría se acelera | 5 recorridos comparables antes/después | mediana ≥20 % menor sin pérdida de controles | mejora <10 % o más errores críticos |
| Se anticipan vencimientos | medir alertas accionadas antes de fecha | ≥70 % de vencimientos relevantes atendidos antes | alertas ignoradas/incorrectas >30 % |
| Mejora seguimiento | cohorte de desvíos por severidad | mediana de cierre ≥20 % menor y sin autocierre | evidencia insuficiente o más vencidos |
| El modo offline aporta | recorridos en zonas con mala conexión | ≥80 % sincroniza sin ayuda ni pérdida | conflicto/error >5 % de mutaciones |
| Hay adopción recurrente | WAU por rol durante 4 semanas | ≥70 % de usuarios objetivo activos semanalmente | <40 % tras onboarding |
| El onboarding es tolerable | cronometrar una obra completa | ≤4 h iniciales para dataset acordado | >8 h o requiere migración no prevista |
| Existe intención de pago | entrevista + oferta concreta al cierre | ≥2 de 3 aceptan piloto pago o carta de intención | elogio sin compromiso/precio viable |

Los umbrales son hipótesis de producto, no SLA contractuales. El owner puede
cambiarlos antes de iniciar el piloto mediante decisión registrada, nunca después
de observar resultados.

## Métricas con definición mínima

- **Tiempo de auditoría:** inicio EN_CURSO a FINALIZADA, informando tiempo offline.
- **Anticipación:** días entre primera alerta vista y fecha de vencimiento.
- **Tiempo de cierre:** creación de finding a verificación válida; segmentado por criticidad.
- **Tasa de conflicto:** mutaciones que requieren revisión / mutaciones recibidas.
- **Uso semanal:** usuario con al menos una acción de dominio confirmada, no sólo login.
- **Exactitud dashboard:** diferencia entre agregado y consulta de detalle; objetivo 0.
- **Voluntad de pago:** oferta, monto/rango, decisor y condición documentados.

## Salvaguardas

- Ninguna métrica usa un score de cumplimiento legal.
- No incorporar features premium, IA o integraciones antes de validar el circuito.
- No iniciar piloto real sin backup/restore, privacidad, capacitación y hardening.
- Consentimientos y entrevistas se gestionan fuera de datos de producto hasta que
  su tratamiento esté aprobado.

