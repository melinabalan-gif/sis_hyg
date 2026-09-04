# Motor normativo determinístico V1

**Estado:** diseño funcional. Ninguna norma jurídica real puede activarse sin validador H&S/legal.

## 1. Propósito y límites

El motor determina aplicabilidad de requisitos bajo inputs explícitos; devuelve
únicamente `APLICA`, `NO_APLICA` o `INDETERMINADO`. No evalúa evidencia de campo
como “cumplimiento legal”, no interpreta texto con IA y no altera snapshots
históricos.

Fuentes nacionales, de Santa Fe y Rosario se inventarían con URI oficial, hash,
versión/vigencia y estado `PENDIENTE_VALIDACION_NORMATIVA`. Pueden investigarse y
versionarse, pero publicación/efecto permanecen deshabilitados. Pruebas activas
usan sólo fuentes/reglas `SYN-*` inequívocamente ficticias.

## 2. Ownership y ciclo

```text
Jurisdiction → RegulatorySource → Rule → RuleVersion
                                      ├→ Applicability DSL
                                      ├→ Requirement
                                      └→ ControlCatalogVersion mapping
```

`worksites` es dueño de jurisdicciones; `regulatory` de fuentes/reglas/requisitos;
`documents` y `audits` consumen proyecciones versionadas. Cada evaluación guarda
rule version, inputs normalizados, resultado, trace acotado y SHA-256.

## 3. DSL JSON

Documento raíz:

```json
{
  "dsl_version": 1,
  "when": {
    "all": [
      {"fact": "worksite.country", "op": "eq", "value": "AR"},
      {"fact": "worksite.stage_codes", "op": "contains", "value": "SYN_STAGE_A"},
      {"fact": "activity.synthetic_depth_m", "op": "gte", "value": 1.25}
    ]
  },
  "on_true": "APLICA",
  "on_false": "NO_APLICA",
  "on_unknown": "INDETERMINADO"
}
```

Esto es una regla sintética de test, no un umbral jurídico.

### Operadores allowlist

| Grupo | Operadores | Tipos |
|---|---|---|
| booleano | `all`, `any`, `not` | expresiones |
| igualdad | `eq`, `neq` | string/number/bool/date |
| orden | `gt`, `gte`, `lt`, `lte` | number/date |
| conjuntos | `in`, `not_in`, `contains`, `contains_any`, `contains_all` | scalar/list |
| presencia | `exists`, `is_null` | cualquier fact declarada |
| rango | `between` | number/date, límites inclusivos explícitos |

No existen `eval`, regex libre, scripts, acceso a red/DB/reloj o facts arbitrarias.
Facts se registran con nombre, tipo, unidad, enum y versión. Fechas/decimales se
normalizan; faltante/type mismatch produce unknown y por defecto INDETERMINADO.

### Límites

- profundidad máxima 12; 100 nodos; listas de 100 valores;
- body 64 KiB; strings 256 caracteres;
- evaluación pura con timeout/costo máximo;
- schema `additionalProperties=false` y discriminadores por nodo;
- `on_unknown` no puede ser APLICA/NO_APLICA para regla jurídica real.

## 4. Publicación y doble aprobación

1. ENE registra fuente y su versión exacta; fuente real nace pendiente/inactiva.
2. Crea RuleVersion BORRADOR y casos de decisión esperados.
3. Validador de schema/tipos/complexity y simulador deben pasar.
4. Envía a EN_REVISION; observaciones son append-only.
5. ANR distinto del creador verifica fuente, alcance, vigencia y tests.
6. Sólo con feature gate y validador H&S/legal identificado pasa a APROBADA.
7. RETIRADA requiere motivo/vigencia; no borra evaluaciones.

En la situación inicial el paso 6 está bloqueado para fuentes reales. El rol ANR
puede probar el workflow con `SYN-*`, pero no eludir el tipo de fuente.

## 5. Evaluación y reevaluación

- Se selecciona versión cuya jurisdicción/vigencia coincide con el instante
  objetivo; solapamientos incompatibles son error de publicación.
- Los facts provienen de un snapshot tipado, no de consultas implícitas.
- El trace lista nodos/resultados sin revelar PII.
- Publicar nueva versión encola reevaluación de requisitos abiertos.
- Auditorías FINALIZADAS/CERRADAS conservan su evaluación y referencias originales.
- Una reevaluación puede crear/retirar una proyección de requisito futuro, nunca
  reescribir un control histórico ni cerrar un finding.

## 6. Pruebas bloqueantes

- truth tables de cada operador, unknown y composición;
- schema/facts/tipos/unidades inválidos;
- profundidad/tamaño/costo y property-based/fuzz;
- vigencias y jurisdicción Nación→Provincia→Municipio→obra/etapa;
- ausencia de fuente/versión/casos/aprobación impide publicar;
- creador no aprueba; fuente real no activa con feature gate apagado;
- determinismo: mismo version+input hash produce mismo resultado;
- versión nueva reevalúa abiertos y no modifica históricos;
- UI/API nunca traduce resultado a “cumplimiento legal”.

## 7. Inventario no ejecutable

El inventario puede referenciar las fuentes semilla enumeradas por el plan para
investigación (Nación, Santa Fe y Rosario), siempre con estado pendiente. No se
copian artículos, condiciones, umbrales ni conclusiones hasta validación contra el
texto oficial vigente y sus modificatorias.

