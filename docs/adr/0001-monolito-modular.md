# ADR-0001 — Monolito modular

- Estado: Propuesto
- Fecha: 2026-09-02
- Gate: aprobación de arquitectura/producto

## Contexto

La V1 tiene un equipo/escala pequeños, un flujo transaccional unido y un único
despliegue. Microservicios añadirían fallos distribuidos, contratos y operación
sin evidencia de necesidad.

## Decisión

Implementar FastAPI como monolito modular con contextos `identity`, `worksites`,
`resources`, `documents`, `machines`, `audits`, `findings`, `offline`, `reports`,
`regulatory` y `audit_log`. Cada módulo posee modelos/casos de uso y expone
interfaces; no hay consultas cruzadas desde routers. Web, API y worker son
procesos/contenedores separados del mismo producto y PostgreSQL transaccional.

## Consecuencias

Transacciones e invariantes son simples y el deploy es único. Deben imponerse
límites por tests/lint/revisión para evitar una masa acoplada. La extracción futura
se justifica con métricas, no se prepara con una red distribuida prematura.

## Alternativas descartadas

Microservicios (costo operativo), backend monolítico sin módulos (acoplamiento) y
Next.js full-stack como autoridad (no coincide con stack/seguridad acordados).

