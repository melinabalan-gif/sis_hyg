# ADR-0006 — Normativa determinística y corpus real inactivo

- Estado: Propuesto — requiere aprobación H&S/legal para cualquier fuente real
- Fecha: 2026-09-02

## Contexto

Las fuentes cambian por jurisdicción, vigencia y modificatorias. Hardcode o IA
podrían generar conclusiones legales falsas y perder procedencia.

## Decisión

Modelar Source→Rule→RuleVersion→Applicability/Requirement con fuente oficial,
versión y vigencia. DSL JSON pura con facts tipadas, operadores allowlist, límites,
trace y tres resultados: APLICA/NO_APLICA/INDETERMINADO. Doble aprobación y nunca
autoaprobación.

En V1 el motor se prueba con `SYN-*`. Todo corpus jurídico real queda
`PENDIENTE_VALIDACION_NORMATIVA`, inactivo y fuera de indicadores hasta existir
validador independiente. Versiones nuevas reevalúan abiertos sin alterar históricos.

## Consecuencias

Resultados explicables/repetibles sin afirmar cumplimiento. Incorporar una norma
requiere trabajo editorial/profesional. UI, API y reportes deben conservar el
lenguaje no jurídico.

## Alternativas descartadas

Reglas dispersas en frontend, scripts/eval, LLM como autoridad, texto sin versión y
autoaprobación del editor.

