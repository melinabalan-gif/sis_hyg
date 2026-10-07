# Resultado de auditoría del sistema — 2026-10-06

## 1. Dictamen ejecutivo

**Auditoría completada con hallazgos confirmados y límites de verificación. El sistema NO está listo para producción ni tiene demostrados todos los recorridos del piloto.** Se verificaron migraciones y aislamiento PostgreSQL; también se encontraron omisiones de autorización, independencia documental, acciones de interfaz sin persistencia y deriva del contrato API. No se corrigió código, no se publicaron commits y no se modificó la base operativa.

| Resultado principal | Evidencia definitiva |
|---|---|
| Backend unitario/contrato | 92 pruebas pasan, 4 fallan; cobertura parcial 60 % |
| PostgreSQL/integración | 11 pasan, 4 fallan; 96 deseleccionadas |
| Frontend | 18 pruebas originales pasan; lint, tipos y build pasan con dependencias existentes no reproducidas desde locks |
| Formato | 3 archivos API y 3 web requieren normalización; Ruff no volvió a fallar por caída de herramienta |
| Contratos | OpenAPI guardado desactualizado; cliente generado también difiere del snapshot guardado |
| Dependencias | npm: 14 nodos afectados, 13 altos y 1 crítico; solo runtime: 3 nodos, 2 altos y 1 crítico. Python: 44 paquetes, sin vulnerabilidades conocidas detectadas |
| Stack completo | Configuración Compose válida; build/smoke cancelado, sin veredicto |

Las cifras de npm son **paquetes/nodos afectados, no vulnerabilidades únicas ni explotaciones demostradas**. Un build aprobado no invalida los defectos funcionales. El piloto declara datos sintéticos y falta de capacidades productivas: esos límites no se presentan como regresiones nuevas.

## 2. Baseline, método y cobertura

- Fecha local: 2026-10-06, zona Buenos Aires (UTC−03:00); consolidación iniciada a las 21:51:08. La fecha UTC del host puede ser 2026-10-07.
- Commit auditado: `e013b7ab0b51d1662bd6926be26c1fd8684086e4`; rama local `desarrollo-piloto`. No se comprobó en esta auditoría el estado remoto actual de `main`, sus protecciones, visibilidad ni ejecuciones reales de CI.
- Inventario: **157 archivos rastreados**, 70 API, 46 web y 41 de documentación/configuración/infraestructura. Baseline de integridad: 162 archivos existentes (157 rastreados, 2 de estado local, 2 respaldos y 1 configuración privada), sin modificaciones rastreadas al inicio.
- Pruebas ejecutadas sobre copias externas de `git archive HEAD`, sin configuración privada ni servicios operativos. Dependencias existentes se reutilizaron o copiaron; sondas sintéticas y generación permanecieron fuera del repositorio original.
- Herramientas observadas: Python 3.14.7, uv 0.12.6, Node 24.19.0, npm 11.17.0, Docker cliente/servidor 29.7.2, servidor Linux amd64, Compose 5.5.0; Ruff 0.16.5, mypy 2.3.1, pytest 9.1.1, Alembic 1.19.1.
- Diferencia respecto de configuración: Node 24.20.0/npm 11.19.0 y uv CI 0.12.9. `engine-strict=true` impidió instalación limpia del frontend. No se certifica reproducibilidad con herramientas exactas ni build web de Linux.
- Autoridad documental: `AGENTS.md` identifica `docs/blueprint/` como fuente canónica. ADR y documentos históricos se contrastaron, sin asumir que una contradicción autoriza cambiar una garantía.

### Matriz de cobertura

| Área | Cobertura alcanzada | Límite explícito |
|---|---|---|
| API/dominio/errores/configuración | Lectura manual focalizada, sondas con servicios reales y storage simulado; 60 Python parseados/formato/lint y 31 fuentes bajo mypy | No lectura semántica línea por línea de todo archivo/fixture; probes no equivalen a explotación desplegada |
| Tenancy/permisos | RLS y privilegios reales PostgreSQL; inspección de guards y timeline | Pruebas de asignaciones bloqueadas por payload; timeline no probado contra despliegue |
| Base/migraciones/historia | Base sintética nueva, head/metadata, rollback total/parcial, reupgrade, FK/RLS, seed idempotente | 4 pruebas de persistencia/historia/journey no alcanzan su acción |
| Web/UI/estados | Fuente completa del workspace y componentes/rutas/CSS; pruebas originales y 4 probes sintéticos | Sin navegador, lector de pantalla, axe, UAT móvil ni medición de cobertura frontend |
| Contrato/cliente | Comparación completa OpenAPI actual/guardado; regeneración aislada y contraste de cliente | UI usa adaptador manual; tipos verdes no garantizan contrato real |
| Infra/operación/CI | Lectura de Compose/Dockerfiles/Caddy/scripts/workflow; config y PostgreSQL real | Sin smoke final, CI remoto, ensayo de backup/restore ni scanner de imágenes/SO |
| Seguridad/dependencias | Policy heurística, lock Python y npm audit; aplicabilidad de avisos principales | No DLP exhaustivo, historial Git completo, pentest ni explotación de CVE |
| Documentación | 24 documentos de `docs/`, instrucciones y documentos raíz contrastados con implementación | Aprobaciones profesionales y gates operativos no inferidos de texto |
| Archivos públicos | robots inspeccionado; cabecera PNG y dimensiones 1730×909 verificadas | Imagen no revisada visualmente |

Excluidos del análisis de contenido: configuración privada, fuentes restringidas externas, dependencias, cachés, builds, estado local y respaldos no rastreados. Su exclusión no equivale a certificación de ausencia de datos sensibles.

## 3. Comprobaciones y reproducción segura

Los comandos siguientes corresponden al directorio indicado de una **copia aislada**. `python` representa el ejecutable verificado del entorno API. Ningún comando exige imprimir credenciales. Registrar código de salida y resumen; no publicar logs completos ni variables privadas.

| Área/comando | Salida | Resultado |
|---|---:|---|
| API: `python -m pytest tests/unit tests/contract --cov=hys_api --cov-report=term-missing` | 1 | 96 recolectadas; 92 pasan/4 fallan; 10,75 s |
| API: `ruff check .` | 1 | Un I001 en migración 0011 |
| API: `ruff format --check .` | 1 | 3 requieren formato; 57 correctos; sin crash |
| API: `mypy --cache-dir .audit-mypy-cache` | 0 | Sin problemas en 31 fuentes |
| API: `python scripts/export_openapi.py --check` | 1 | Snapshot desactualizado |
| API: `python -m pytest -m integration -q` | 1 | 11 pasan/4 fallan/96 deseleccionadas; 33,74 s |
| Raíz: `python scripts/policy_check.py` | 0 | Sin coincidencias heurísticas; términos restringidos específicos no configurados |
| Raíz: `docker compose --env-file <synthetic.env> --file <snapshot>/compose.yaml --project-name <audit-only> config --quiet` | 0 | Modelo válido, sin iniciar servicios |
| Externo: `uv tool run --from pip-audit pip-audit -r <requirements-del-lock> --no-deps --disable-pip --format json` | 0 | 44 paquetes registry runtime/dev; 0 avisos conocidos |
| Web: `npm run format:check` | 1 | 3 archivos sin formato esperado |
| Web: `npm run lint` / `npm run typecheck` | 0 / 0 | Candidato original restaurado, sin probe ni generación concurrente |
| Web: `npm test -- tests/component/home-page.test.tsx tests/unit/healthz.test.ts` | 0 | 18/18: 17 componentes + 1 healthz |
| Web: `npm run build` | 0 | Compilación/tipos/prerender; `/`, `/_not-found`, `/healthz`, `/manifest.webmanifest` |
| Web: `npm audit --audit-level=high --json` | 1 | 14 nodos: 13 altos/1 crítico |
| Web: `npm audit --omit=dev --audit-level=high --json` | 1 | 3 nodos: 2 altos/1 crítico |
| Web aislada: `npm run api:generate` | 0 | Genera, pero index/sdk/types difieren; no es un PASS de consistencia |
| Web aislada: 4 pruebas temporales de reproducción UI | 0 | 4/4 confirman conductas erróneas; no incorporadas al repositorio |
| Compose aislado: build + smoke | Cancelado | Sin veredicto funcional; cancelación no es defecto del producto |

Cobertura API **solo unit/contract**: 60 %; 2402 statements, 831 sin ejecutar; 492 branches, 58 parciales. Servicio piloto 33 %, reportes 59 %, seed 0 %. Integración no incluida en esa cifra. Varias pruebas HTTP usan `FakePilotService`; no demuestran persistencia/autorización real.

**Base segura:** PostgreSQL nuevo con digest de Compose, nombre con segmento `test`/`synthetic`, puerto loopback exclusivo, `HYS_ALLOW_DESTRUCTIVE_TEST_DATABASE=1`, URLs de test/migración con propietario y URL runtime con `hys_app` distinto. Las tres apuntan al mismo endpoint aislado. Nunca heredar URLs operativas: fixtures ejecutan downgrade a `base` antes y después. Se comprobó `hys_app` sin superusuario/BYPASSRLS y 0 tablas operativas al terminar, excluyendo `alembic_version`.

**Pruebas PostgreSQL aprobadas:** empty→head, metadata=head, downgrade/reupgrade completo y parcial; seed/RLS/policies; seed idempotente y reparación de metadatos sintéticos; grants mínimos; FK compuestas/filas cross-tenant; intervalos de etapas y jurisdicción legacy; rol app y privilegios públicos; RLS enabled/forced con ambos tenants.

**Incidentes del harness, no defectos de fuente:** primer provisioning durante bootstrap PostgreSQL produjo apagado transitorio y 15 errores de setup; repetición tras verificar rol obtuvo 11/4. Config inicial con `/dev/null` no portátil falló, archivo externo correcto pasó. Primeros checks web coincidieron con generación/fixture y se invalidaron; resultados definitivos se repitieron sobre bytes originales. Instalación `npm ci --no-audit` falló EBADENGINE; descarga runtime exacto se canceló por bloqueo y alternativa recibió ECONNRESET. Fallback permitió checks, no instalación reproducible. Matcher sintético inicial se corrigió exclusivamente fuera del candidato.

## 4. Hallazgos agrupados por causa raíz

Severidad expresa impacto/prioridad; estado expresa fuerza de evidencia. “Confirmado” está limitado al escenario descrito, no garantiza explotación contra un despliegue. Las recomendaciones **no autorizan implementación**. Hay 14 grupos: 12 confirmados, 1 con desalineación confirmada y efecto sospechado, y 1 sospechado; varios efectos secundarios permanecen no verificados.

### AUD-001 — Alta | Confirmado: timeline sin autorización de obra/empresa

- Evidencia: `apps/api/src/hys_api/modules/pilot/service.py:1428-1431,2151-2164`; `apps/api/src/hys_api/modules/pilot/router.py:496-505`; `apps/api/src/hys_api/db/tenant.py:25-30`.
- Esperado/actual: actor sin scope no accede a historial; servicio consulta tenant+UUID sin guard de obra/empresa. HTTP con router/servicio reales y storage simulado devolvió 200/1 evento; guards configurados para denegar registraron 0 llamadas.
- Reproducción: actor sintético válido solicita `GET /api/v1/findings/{id}/timeline` de obra no asignada; comparar con detalle obra autorizado. No se ejecutó explotación contra DB desplegada ni fuga entre tenants.
- Impacto/recomendación: lectura fuera de scope dentro del tenant. Aplicar autorización antes de eventos y pruebas negativas obra/empresa/asignación vencida, con respuesta no reveladora.

### AUD-002 — Alta | Confirmado en servicio: revisión propia de nueva versión documental

- Evidencia: `apps/api/src/hys_api/modules/pilot/service.py:770,834-852`; `apps/api/src/hys_api/modules/pilot/models.py:745-783`.
- Esperado/actual: independencia respecto del autor de versión revisada; guard compara con cargador original y revisión no identifica versión inmutable.
- Reproducción: A carga documento, B crea versión 2, B la aprueba. Servicio real con storage simulado aceptó `APROBADO` y flush; no transacción PostgreSQL de este escenario.
- Impacto/recomendación: aprobar contenido propio y perder trazabilidad precisa. Vincular revisión a versión y autor actuales; pruebas A→B→B denegada/A→B→C permitida, preservando historia.

### AUD-003 — Alta | Confirmado: contrato, fixtures y cliente desalineados

- Evidencia: `apps/api/src/hys_api/modules/pilot/schemas.py:138-159`; `service.py:236-273,3237-3252`; `apps/api/tests/unit/test_pilot_schemas.py:142-144`; `tests/unit/test_pilot_service_guards.py:104`; `tests/contract/test_openapi.py:61`; `tests/integration/test_pilot_persistence.py:427,860,965,1051`; `apps/web/src/generated/api/types.gen.ts:1204-1229`; `apps/web/src/lib/pilot-api.ts:415-423`.
- Actual: OpenAPI vivo requiere `name,address`; guardado/cliente exige `code,name`. Código ahora autogenerado; dirección se persiste pero no retorna por summary/detail. Payload acepta jurisdicción incompleta y servicio usa `SIN_ESPECIFICAR`.
- Pruebas: 3 unitarias fallan antes de intención (2 de permisos no llegan a autorización), 1 snapshot y 4 integración por `address` ausente. Fallan asignaciones/scope, versiones, inspecciones y journey persistido/cierre/PDF.
- Regenerar incluso el snapshot guardado cambia index/sdk/types (types +698/−11 y SDK +56 líneas): deriva no limitada a dirección. Adaptador manual con `Record<string, unknown>` y casts impide que tipos verdes la detecten.
- Reproducción: ejecutar suites y export `--check`; regenerar cliente únicamente en copia aislada y comparar; crear obra y consultar respuesta.
- Recomendación: confirmar requisito canónico de alta/jurisdicción, reconciliar lectura/escritura/esquema/fixtures y consumir o validar tipos generados. No debilitar pruebas de permisos para obtener verde.

### AUD-004 — Media | Confirmado: política de segregación contradictoria

- Evidencia: `AGENTS.md`, `README.md:34-35`, blueprint RBAC/segregación y `docs/architecture/dominio.md:318` prohíben creador y corrector; `docs/adr/0008-correcciones-qa-piloto.md:35-40` permite detector si otro corrigió. `service.py:1367-1426` controla última corrección y admite Auditor/RHS; `tests/unit/test_pilot_service_guards.py:446` no parametriza creador como prohibido.
- Esperado/actual: una garantía autorizada; documentos y código expresan garantías distintas. La raíz declara blueprint canónico, por lo que no basta cambiar README según ADR.
- Reproducción/impacto: contrastar regla del creador y actor verificador en las fuentes y prueba parametrizada; UAT puede validar expectativa equivocada.
- Recomendación: reconciliación formal. Si rige blueprint, cubrir creador negativo/RHS-only; si se aprueba otro corte, registrar aprobación y actualizar todas las fuentes antes de anunciar independencia.

### AUD-005 — Media | Desalineación confirmada; efecto 500 sospechado: límites HTTP/DB

- Evidencia: `schemas.py:13,142-144`; `apps/api/src/hys_api/modules/worksites/models.py:48-50`. Alias `ShortText` acepta 200; DB país/provincia/municipio limita 120. Probe aceptó 121.
- Esperado/actual: 422 antes de persistir; validación permite valores incompatibles. Misma clase en trade/role_label/sector.
- Reproducción: límites 120/121 en schema y luego DB sintética. No se ejecutó el 500: `DataError` fuera de traducción `IntegrityError` es riesgo, no resultado confirmado.
- Recomendación: límites coherentes por campo y migración, pruebas borde compartidas; no parches aislados por cada síntoma.

### AUD-006 — Alta | Confirmado: acciones visibles sin persistencia

- Evidencia: `apps/web/src/components/pilot-workspace.tsx:1863-1868,1888-1890,1897-1923,2215-2219,2393-2397`.
- Esperado/actual: cargar/actualizar/completar/adjuntar metadatos inicia flujo y conserva cambios; botones habilitados carecen de handler. Auditor/profesión/horas usan defaults ficticios; disponibilidad permanece en estado local.
- Reproducción sintética: Legajos→principal→Cargar no genera petición/diálogo; Baños Sí→Personal→Legajos pierde selección. Probes confirman, mientras tests originales validan visibilidad/comportamiento local.
- Impacto/recomendación: falsa percepción de registro. Conectar backend de metadatos/versiones/revisión y pruebas de recarga/reapertura; mientras no esté implementado, advertir/deshabilitar. No confundir con ausencia deliberada de binarios.

### AUD-007 — Media | Confirmado: dashboard y documentos omiten pendientes

- Evidencia: `pilot-workspace.tsx:2227-2245,998-1000,1173-1176,1200`.
- Actual: documento `PENDIENTE` queda etiquetado vigente; desvío `EN_CORRECCION` no cuenta ni activa intervención, llegando a “Sin pendientes”. Probes con un elemento reproducen ambas conductas.
- Esperado/impacto: resumen coincide con detalle y estados no resueltos; omisión altera priorización operativa.
- Recomendación: derivaciones únicas de todos los estados, pendientes/revisión diferenciados; tests aislados y combinaciones con reconciliación numerador/listado.

### AUD-008 — Media | Confirmado estáticamente: accesibilidad incompleta

- Evidencia: `pilot-workspace.tsx:395-413,1657-1673,2558-2562,2856-2884`.
- Actual: tabs sin flechas/Home/End/roving tabindex; controles de etapa, inspección y persona/severidad/empresa sin label o aria-label. Placeholder/opciones no reemplazan nombre accesible.
- Esperado/reproducción: inspección del patrón y nombres; completar prueba de teclado/lector en navegador. Contraste/conformidad WCAG no comprobados.
- Recomendación: patrón tabs completo y nombres explícitos; pruebas de teclado/axe/UAT, conservando focus-visible/skiplink/reduced-motion existentes.

### AUD-009 — Media | Sospechado: respuesta asincrónica obsoleta

- Evidencia: `pilot-workspace.tsx:173-183,185-213,220-235`. Setters ocurren antes de comprobar bandera active; detalle sin guard de respuesta vigente, cargas duplicadas selección/effect.
- Hipótesis: cambiar rápido obra/actor o volver al inicio deja detalle anterior/contexto nuevo. No reproducción controlada, fuga tenant ni bypass demostrados.
- Reproducción/recomendación: promesas sintéticas resueltas en orden inverso; cancelar o identificar generación de request y aplicar estado solo vigente. Backend mantiene autoridad.

### AUD-010 — Media | Confirmado estáticamente: UI no refleja permiso efectivo

- Evidencia: `pilot-workspace.tsx:160-170,2691-2694`; `service.py:1583-1604`.
- Actual: asignación histórica basta para ofrecer operar auditoría; UI no filtra vigencia/editor, servidor sí. Puede ofrecer control/finalización ajenos y recibir 403.
- Esperado/impacto: operaciones visibles acordes con asignación activa/autor; es desalineación UX, no autorización backend vulnerada.
- Recomendación: permiso efectivo coherente, vigencia/editor y rechazo explicado; pruebas positivas/negativas y contraste de corte piloto con blueprint.

### AUD-011 — Alta; incluye aviso crítico | Versiones vulnerables confirmadas, explotación no demostrada

- Evidencia: `apps/web/package-lock.json`, auditoría npm y `apps/web/package.json:43` (override js-yaml vulnerable). Véase tabla de avisos en sección 5.
- Reproducción: `npm audit --audit-level=high --json` y variante `--omit=dev` en copia con lock original.
- Impacto: dependencias afectadas por avisos conocidos, algunas solo tooling y otras con condiciones de entrada/runtime no observadas. No se confirmó RCE, DoS ni evasión TLS en esta aplicación.
- Recomendación: actualización compatible de paquetes/override y lock, seguida de audit/tests/build/contratos. No `npm audit fix --force`, downgrade ciego ni modificación durante auditoría.

### AUD-012 — Media | Confirmado: controles operativos más limitados que garantía documental

- Evidencia: `scripts/policy_check.py:14-21,35-37,50-73`; `.github/workflows/ci.yml:28-31`; `docs/operations/calidad-y-operacion.md:43,65-80`; `docs/security/privacidad.md`; `infra/caddy/Caddyfile`.
- Actual: policy heurística/términos opcionales/Office no cubre historial, PII genérica, licencias ni todos los tokens. CI no incorpora E2E Playwright, scanner Python/imágenes, SBOM/provenance, licencias/workflow lint. Backup/restore es propuesta sin evidencia operativa rastreada; Caddy no implementa CSP/frame-ancestors/rate limit exigidos por modelo de amenazas.
- Reproducción/impacto: contrastar script/workflow/runbooks/headers con requisitos; policy verde no certifica historial limpio ni PII ausente. Sin ensayo de restore ni scan SO, sin verdict productivo.
- Recomendación: declarar cobertura exacta y cerrar esos gates antes de datos reales; no copiar términos/valores privados al informe.

### AUD-013 — Baja | Confirmado: textos y normalización pendientes

- Evidencia: `pilot-workspace.tsx:1254-1255` contiene `T├®cnico` y `Cambiar t├®cnico` en fuente, no solo terminal. Ruff: `apps/api/migrations/versions/20261001_0011_add_worksite_address.py:7` I001 y formato/BOM; `schemas.py:148`, `service.py:238`. Web: `app/globals.css`, workspace y `tests/component/home-page.test.tsx`.
- Reproducción: pantalla Responsables y checks de formato. Crash Ruff anterior no se reprodujo; ahora finaliza exit 1 con problemas de formato.
- Recomendación: UTF-8/etiquetas probadas y normalización separada, antes de checks finales; no se aplicó ningún formatter.

### AUD-014 — Baja | Confirmado: smoke Windows no equivalente

- Evidencia: `scripts/smoke.ps1:8-10`; `scripts/smoke.sh:23-32`.
- Actual: AllowLocalCertificate solo evita TLS en PowerShell ≥7; PS5.1 no satisface esa opción. PowerShell no comprueba puertos DB/S3/AV como shell. Ambos prueban salud/banner/migrador, no journey completo.
- Reproducción: inspección del flujo/condición de versión; no ejecución contra stack existente.
- Recomendación: requisito PS7 o rechazo explícito, controles privados paritarios y descripción exacta del alcance smoke.

## 5. Dependencias: fuente y aplicabilidad

Consulta 2026-10-06 Buenos Aires. Los cuatro primeros avisos se verificaron en fuente oficial; restantes URLs son referencias del JSON de npm no inspeccionadas individualmente. Versiones afectadas de este lock, no lista universal de todos los rangos.

| Paquete/versionado | Aviso y parche | Aplicabilidad observada |
|---|---|---|
| Next 16.3.4, rango ≥16.2.0 y <16.3.6 | [GHSA-vcvr-r3jv-pc5j](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j), crítico; parche 16.3.6 | Requiere ImageResponse Node/next/og con SVG/atributos/styles controlados por atacante; no imports observados, OG PNG estático; no RCE demostrado |
| sharp 0.35.4, <0.35.5 | [GHSA-wq5f-xc86-pv6w](https://github.com/advisories/GHSA-wq5f-xc86-pv6w); parche 0.35.5 | Condiciones librsvg/Linux glibc/SVG; no decodificación SVG no confiable ni next/image observados; validar imagen Linux |
| source-map-js 1.2.1, ≥1.0.0 y <1.2.2 | [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q); parche 1.2.2 | DoS con indexed source maps no confiables; ruta de explotación no demostrada |
| js-yaml 4.3.1, ≥4.0.0 y <4.3.2 | [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh); parche 4.3.2 | DoS por empty merge sources; override fija vulnerable; no endpoint YAML público observado |
| brace-expansion 1.1.18 | [GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr) <1.1.21; [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7) <1.1.20; [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) <1.1.19 | Referencias npm, herramienta/transitivo; no exploit ejecutado |
| braces 3.0.3, ≤3.0.3 | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) | Referencia npm, no exploit ejecutado |
| undici 8.10.1 | [GHSA-rfgv-xxqx-mfg5](https://github.com/advisories/GHSA-rfgv-xxqx-mfg5), [GHSA-w293-vg96-wgc3](https://github.com/advisories/GHSA-w293-vg96-wgc3): ≥8.0.0 y <8.10.2; [GHSA-vp8m-p9jh-q5pm](https://github.com/advisories/GHSA-vp8m-p9jh-q5pm): ≥8.10.0 y <8.10.2 | WebSocket DoS/BalancedPool TLS/cache origin; no uso expuesto de esas APIs demostrado; parche 8.10.2 |

Los otros nodos afectados, por propagación/transitivos, incluyen `@hey-api/json-schema-ref-parser@1.4.4`, `@hey-api/openapi-ts@0.99.0`, `@hey-api/shared@0.5.0`, `@next/eslint-plugin-next@16.3.4`, `eslint-config-next@16.3.4`, `fast-glob@3.3.1`, `micromatch@4.0.8`. Los tres runtime reportados son Next, sharp y source-map-js. Resultado Python sin avisos conocidos en 44 paquetes no significa ausencia de toda vulnerabilidad ni cubre imágenes/OS.

## 6. Límites declarados, riesgos no demostrados y prioridades

**Piloto no productivo:** identidad sintética seleccionable, sin autenticación/MFA productivas, offline cifrado, binarios/quarantine funcional, IA/OCR, portal externo ni integraciones. PDF síncrono del estado actual no constituye snapshot/versionado reproducible V1; normativa real continúa inactiva. No ingresar datos reales ni afirmar cumplimiento legal. Campos libres podrían recibir PII: prohibición documental no sustituye cifrado/control técnico.

**Pendientes de prueba:** visual QA PDF (ASCII/texto largo sin wrap), N+1/latencia/carga del servicio (~3542 líneas), retries/idempotencia ante POST guardado seguido de refresh fallido, móvil/accesibilidad completa, restore externo, resiliencia de dependencias, scanner imágenes, CI real/protecciones. Son riesgos/ausencia de evidencia, no errores reproducidos. Diagnóstico de host agosto es histórico; herramientas actuales no prueban aprovisionamiento productivo aprobado.

| Prioridad | Acción recomendada, sujeta a autorización |
|---|---|
| P0 | Mantener datos sintéticos y restricción no producción; tratar AUD-001/002, evaluar actualización de dependencias afectadas |
| P1 | Reconciliar contrato/fixtures/cliente y regla de segregación; repetir pruebas bloqueadas; resolver acciones sin persistencia y resúmenes engañosos |
| P2 | Permiso efectivo UI, accesibilidad, límites DB/HTTP, carrera de respuestas y normalización/textos |
| Gates posteriores | Entorno exacto reproducible, build/smoke Linux aislado, E2E/seguridad, backups/restore y evidencia operativa/privacidad |

No se recomienda ocultar fallos, rebajar pruebas ni interpretar otras pruebas verdes como sustituto de las cuatro de integración que no alcanzaron la acción. Las correcciones deben agruparse por raíz y cerrar con pruebas nombradas.

## 7. Integridad, limpieza y aceptación

- Código fuente original no corregido; generación/sondas/cache/cobertura únicamente externas. El informe es el único archivo nuevo autorizado dentro del repositorio.
- Contenedores y volúmenes de DB/Compose de auditoría eliminados mediante identidades/labels exactos; sin prune ni operaciones contra stack existente, sin recursos Compose iniciados tras build cancelado.
- No quedaron procesos Node propios ni procesos API no-shell referenciando sus áreas temporales. Las carpetas externas API y frontend/dependencias quedaron inactivas: eliminación recursiva rechazada por política de herramienta antes de ejecutarse; no se intentó otro intérprete ni bypass. Limpieza de carpetas externas incompleta; contenedores/volúmenes sí retirados. El entorno virtual original permaneció intacto. Evidencias externas conservadas sin rutas privadas en este documento.
- Verificación final de consolidación: SHA-256 de los 162 archivos del baseline sin cambios; inventario final 163, con este informe como único archivo agregado. `git status` conserva únicamente el estado local y dos respaldos preexistentes, más el informe, sin modificaciones rastreadas. Baseline comprende archivos rastreados/no ignorados y configuración privada raíz; no certifica todos los bytes de dependencias ignoradas (`.venv`/`node_modules`). Lectura UTF-8 estricta y estructura del informe verificadas.
- Aceptación: informe legible, comandos/resultados y límites trazables, 157 archivos inventariados; ejecución completa no implica todos los controles aprobados. Sin commits ni push.

## Aprendizajes clave

1. RLS por organización no reemplaza autorización por obra/empresa; storage simulado y PostgreSQL real demuestran cosas diferentes.
2. Un payload inválido impide verificar permisos: las pruebas bloqueadas no prueban ni refutan autorización.
3. La revisión independiente debe relacionarse con versión/autor, no únicamente cargador histórico.
4. Tipos/tests/build pueden pasar con botones sin acción y un adaptador desacoplado del contrato generado.
5. Dependencia vulnerable confirma exposición potencial, no explotación; ausencia de CVE conocido tampoco certifica seguridad.
6. Auditoría integral significa inventario, cobertura y límites explícitos, no revisión semántica total ni aprobación productiva.

## Anexo A — Inventario rastreado y profundidad

Cada casilla marca **archivo inventariado**, no aprobación individual. API: cobertura automática/estructural y lectura manual focalizada; web: lectura de fuente/configuración y checks, cliente generado estructural/regenerado, PNG solo cabecera; documentación/infra: lectura manual y checks aplicables. No se atribuye revisión manual individual donde el handoff no la demuestra.

### API — 70 archivos

- [x] `apps/api/.dockerignore` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/.python-version` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/Dockerfile` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/alembic.ini` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/README` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/env.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/script.py.mako` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260902_0001_initial_tenancy.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260903_0002_pilot_vertical_flow.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260903_0003_pilot_audit_catalog_controls.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260903_0004_worksite_jurisdiction_and_stages.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260903_0005_document_versions.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260904_0006_actor_domain_refactor.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260905_0007_qa_corrections.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260905_0008_remaining_qa_gaps.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260906_0009_auditor_delegation.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20260906_0010_responsible_assignment_history.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/migrations/versions/20261001_0011_add_worksite_address.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/openapi.json` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/pyproject.toml` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/scripts/export_openapi.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/api/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/api/dependencies.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/api/v1/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/api/v1/health.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/api/v1/router.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/core/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/core/config.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/core/errors.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/core/request_id.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/core/telemetry.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/base.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/models.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/readiness.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/schema.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/session.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/db/tenant.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/main.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/organizations/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/organizations/models.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/demo_seed.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/models.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/report.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/router.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/schemas.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/pilot/service.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/worksites/__init__.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/modules/worksites/models.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/src/hys_api/py.typed` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/conftest.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/contract/test_health.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/contract/test_openapi.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/contract/test_pilot_api.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/integration/conftest.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/integration/test_migrations.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/integration/test_pilot_persistence.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/integration/test_rls.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_config.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_pilot_dependencies.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_pilot_schemas.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_pilot_service_guards.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_readiness.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_request_id.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_telemetry.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/tests/unit/test_tenant.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/api/uv.lock` — inventariado; profundidad según matriz y nota de este anexo.

### Web — 46 archivos

- [x] `apps/web/.dockerignore` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/.npmrc` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/.nvmrc` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/.prettierignore` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/.prettierrc.json` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/AGENTS.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/CLAUDE.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/Dockerfile` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/app/globals.css` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/app/healthz/route.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/app/layout.tsx` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/app/manifest.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/app/page.tsx` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/eslint.config.mjs` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/next-env.d.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/next.config.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/openapi-ts.config.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/package-lock.json` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/package.json` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/public/og.png` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/public/robots.txt` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/components/environment-banner.tsx` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/components/pilot-workspace.tsx` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/components/readiness-panel.tsx` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/client.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/client/client.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/client/index.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/client/types.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/client/utils.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/auth.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/bodySerializer.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/params.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/pathSerializer.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/queryKeySerializer.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/serverSentEvents.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/types.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/core/utils.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/index.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/sdk.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/generated/api/types.gen.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/src/lib/pilot-api.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/tests/component/home-page.test.tsx` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/tests/setup.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/tests/unit/healthz.test.ts` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/tsconfig.json` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `apps/web/vitest.config.ts` — inventariado; profundidad según matriz y nota de este anexo.

### Documentación, infraestructura y raíz — 41 archivos

- [x] `.dockerignore` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `.editorconfig` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `.env.example` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `.gitattributes` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `.github/workflows/ci.yml` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `.gitignore` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `AGENTS.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `BLOQUE_RESPONSABLES.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `QA_CORRECCIONES_HYS_GENTLE.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `README.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `VIEW_V1_HYS.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `compose.yaml` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0001-monolito-modular.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0002-tenancy-y-rls.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0003-documentos-y-pii.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0004-offline-sync.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0005-inmutabilidad-e-informes.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0006-normativa-deterministica.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0007-actores-funciones-y-jerarquia.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/adr/0008-correcciones-qa-piloto.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/architecture/api.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/architecture/arquitectura.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/architecture/contextos.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/architecture/dominio.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/README.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/negocio-y-validacion.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/normativa.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/producto.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/rbac-y-journeys.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/riesgos-y-decisiones.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/roadmap.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/blueprint/wireframes.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/operations/calidad-y-operacion.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/operations/entorno.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/security/modelo-de-amenazas.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `docs/security/privacidad.md` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `infra/caddy/Caddyfile` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `infra/postgres/init-app-role.sh` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `scripts/policy_check.py` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `scripts/smoke.ps1` — inventariado; profundidad según matriz y nota de este anexo.
- [x] `scripts/smoke.sh` — inventariado; profundidad según matriz y nota de este anexo.

## Remediación secuencial — bloque API (2026-10-06)

Este apartado registra correcciones autorizadas posteriores a la auditoría. Los hallazgos originales permanecen como evidencia histórica. No se realizaron commits, publicaciones ni cambios sobre bases operativas.

| Hallazgo | Implementación | Evidencia y estado |
|---|---|---|
| AUD-001 | Timeline valida obra visible, función profesional vigente y empresa afectada antes de leer eventos; la propiedad de creación no sustituye asignación vigente. Cuenta organizacional conserva lectura de piloto documentada. Denegaciones de scope devuelven 404 no revelador. | RED: 3 fallos/1 paso; GREEN: 4 pasos. Refinamiento ownership RED: 1 fallo; GREEN dentro de suite final. **Verificado en servicio con almacenamiento simulado; pendiente integración DB negativa.** |
| AUD-002 | Revisión nueva exige `document_version_id`; bloquea versión desactualizada y autor de la versión vigente. Revisión referencia versión inmutable mediante FK compuesta organización/documento/versión. | RED: 3 fallos (schema), después 3 fallos conductuales al admitir campo; GREEN: 3 pasos. **Verificado unitario; migración/rollback DB pendientes.** |
| AUD-003 (API) | Restaurada validación de jurisdicción o país/provincia/municipio completos; dirección vuelve en resumen/detalle. Fixtures de alta incluyen dirección para alcanzar las verificaciones de permisos originales; OpenAPI regenerado. | RED: 2 fallos/4 pasos; GREEN: 63 pasos de suites focalizadas. Snapshot `--check` pasa. **API verificada; SDK y consumidores web pendientes del bloque siguiente.** |
| AUD-004 | Segregación canónica: sólo Responsable H&S con función/scope autorizados; creador del desvío y autor de corrección no verifican ni cierran. Restituido caso negativo de creador; ADR-0008 y documento QA reconciliados con blueprint. | RED matriz: 2 fallos/3 pasos; GREEN: 45 pasos de suites focalizadas. **Unitario verificado; integración independiente pendiente.** |
| AUD-005 | Límites HTTP por campo coinciden con persistencia: país/provincia/municipio/trade/role_label/sector/machine_type/brand/model 120; document_type 100; function_label 160; license_plate 32. | RED: 14 fallos; GREEN: 14 pasos, cada caso prueba límite y límite+1. **Validación previa a persistencia verificada; no se afirma ejecución PostgreSQL.** |
| AUD-013 (API) | Normalizados imports/BOM/formato de migración 0011 y archivos API tocados, antes de comprobaciones finales. | Ruff lint y format-check pasan; 62 archivos Python con formato correcto. **Web pendiente.** |

### Verificación final del bloque

- `python -m pytest apps/api/tests/unit apps/api/tests/contract -q`: **128 passed**, exit 0 (2,64 s).
- `ruff check apps/api`: **All checks passed**, exit 0.
- `ruff format --check apps/api`: **62 files already formatted**, exit 0.
- `mypy --cache-dir <cache temporal>` desde `apps/api`: **31 source files**, sin errores, exit 0.
- `python apps/api/scripts/export_openapi.py --check`: **OpenAPI snapshot OK**, exit 0.
- RDD: consulta de solo lectura, **off/default**, sin activar ni modificar el interruptor.
- Fixtures de configuración usan `_env_file=None` para no depender de secretos/configuración local. Ejecución con URL sintética y sin URL de migración heredada; pruebas unitarias/contract no operan sobre DB real.

### Migración y compatibilidad de AUD-002

Nueva revisión Alembic: `20261006_0012`, posterior a `20261001_0011`; readiness ahora espera esa revisión.
La columna histórica `document_reviews.document_version_id` es nullable: NULL significa versión desconocida, no una inferencia de versión. No hay backfill ni modificación de revisiones existentes. Una restricción `CHECK ... NOT VALID` conserva filas antiguas y exige vínculo para cada nueva inserción. La FK compuesta impide enlazar otra organización/documento. El downgrade conserva todas las filas de revisión, elimina solamente columna/FK/check/unique añadidos y debe acompañarse del rollback de API; se pierde el vínculo de versión añadido, no las revisiones. **No se ejecutó upgrade/downgrade en DB en este bloque.**

Clientes nuevos deben enviar el ID explícito de la versión actual; una revisión iniciada sobre versión anterior recibe `409 document_version_stale`. La UI/SDK deben actualizarse secuencialmente antes de entrega integrada. Las revisiones históricas se leen con ID de versión nulo.

### Pruebas de regresión nombradas

`test_timeline_denies_worksite_without_current_assignment` (sin asignación/vencida), `test_timeline_denies_finding_outside_represented_company`, `test_timeline_reads_same_company_after_scope_checks`, `test_timeline_creation_ownership_does_not_replace_current_function`, `test_document_review_is_bound_to_current_immutable_version` (autor actual/versión vieja/independiente), `test_worksite_jurisdiction_is_required_with_address`, `test_worksite_address_survives_summary_projection`, `test_worksite_accepts_canonical_jurisdiction_forms`, `test_finding_verification_requires_independent_rhs` (Auditor/creador/corrector/RHS proyecto/RHS contratista), `test_input_lengths_match_persistence_boundaries` (14 campos).

La suite original de permisos e historia permanece; no se eliminaron aserciones para ocultar fallos. Un chequeo intermedio tuvo error de sintaxis en fixture de configuración y otro necesitó actualizar expectativa de contrato para el nuevo campo address; ambos fueron diagnosticados y corregidos antes de los 128 pasos finales. No se incluyen outputs con valores privados.

### Límites de cierre

Este bloque no cierra los 14 hallazgos globales. Permanecen SDK/UI, infraestructura/CI/privacidad operativa, verificación DB aislada, pruebas visuales/carga y otros controles del informe. No se afirma que el piloto sea productivo. Cambios aún locales y sin commit. La reversión por unidad debe conservar juntos servicio/esquema/pruebas/docs; AUD-002 requiere rollback de migración y API coordinados.

## Remediación secuencial — bloque web y metadatos (2026-10-07)

Continuación autorizada del bloque API. Los 14 hallazgos originales y los resultados históricos anteriores se conservan. Este apartado acredita verificaciones locales acotadas, no un cierre productivo ni la ejecución de PostgreSQL.

| Hallazgo | Corrección | Evidencia y estado actual |
|---|---|---|
| AUD-003 (web) | Cliente generado desde OpenAPI vigente; adaptador importa `WorksiteCreate`, `DocumentCreate`, `DocumentVersionCreate` y `DocumentReviewCreate`. Alta envía dirección y jurisdicción; revisión envía ID explícito de versión actual. | Generación completada; pruebas de payload y tipos pasan. **Contrato web/API actualizado.** |
| AUD-006 | Carga/actualización abre editor real y guarda documentos/versiones. Servicios auxiliares y horas semanales usan notas estructuradas versionadas, preservando claves desconocidas, texto humano y fechas. Nombre/profesión del auditor provienen de asignación vigente. API valida tipos, intervalos de media hora y referencia de auditor de la misma obra/tenant, aunque sea distinto del editor. | Pruebas de guardar/reabrir/remontar y payload real pasan. Hallazgo adicional RED API: 1 fallo por filtro al actor editor; GREEN: 2 pasos. RED fechas auxiliares: 1 fallo; GREEN: 1 paso. **Persistencia simulada verificada; caso DB añadido, aún no ejecutado.** |
| AUD-007 | Dashboard incluye documentos `PENDIENTE` y desvíos `EN_CORRECCION`; legajo no presenta documentación pendiente ni parcialmente poblada como vigente/completa. | Regresiones de resumen y componentes incompletos pasan. **Verificado en componentes.** |
| AUD-008 | Tabs con foco itinerante, flechas, Home/End, selección y vínculo tab/panel. Controles inline de etapa, habilitación, inspección y auditoría con nombres accesibles. | Regresiones de teclado y nombres pasan. **Verificado en DOM simulado; no sustituye lector de pantalla/E2E.** |
| AUD-009 | Solicitudes llevan generación/contexto actor–obra; respuestas obsoletas no actualizan estado, refrescan ni anuncian éxito. Selección no carga dos veces el mismo detalle. | Promesas resueltas en orden inverso para actor, obra, mutación y refresco posterior: todas pasan. **Verificado en componentes.** |
| AUD-010 | Mutaciones documentales exigen obra activa, función, empresa representada, scope y asignación vigente. Operar auditoría depende del editor/asignación actual, no sólo del rol ni del autor original; una auditoría finalizada ajena no bloquea iniciar otra. Auditor asignado puede corregir, no verificar; verificación excluye creador/corrector. | Refinamiento RED: 7 fallos/4 pasos; GREEN focalizado: 11 pasos (incluye validación horaria). Casos sin asignación, vencida, futura, scope excesivo, función desconocida, obra archivada y matriz editor pasan. **UI verificada; backend continúa siendo autoridad. Ownership de setup no concede timeline profesional.** |
| AUD-013 (web) | Etiquetas sin mojibake y normalización de archivos web antes de checks. | Búsqueda en componentes/adaptador sin coincidencias de mojibake; formato/lint/tipos/build pasan. **Verificado localmente.** |

### Comprobaciones del candidato

- `npm run api:generate`: generación desde snapshot, exit 0; sin instalar dependencias.
- `npm run format:check`, `npm run lint`, `npm run typecheck`: exit 0, secuenciales después de normalización.
- `npm test`: **42 passed, 3 archivos**, exit 0 (15,25 s), incluido el último caso de refresco obsoleto. Antes de agregar ese caso, el mismo código de ejecución pasó 41 pruebas.
- `npm run build`: exit 0; compilación, TypeScript y generación estática completadas. El último cambio posterior afectó sólo una prueba; formato/lint/tipos y las 42 pruebas se comprobaron nuevamente, sin reconstruir fuentes runtime inalteradas.
- API desde `apps/api`: `python -m pytest tests/unit tests/contract -q`: **135 passed**, exit 0 (7,16 s); Ruff lint pasa, format-check **62 archivos**, mypy **31 fuentes**, snapshot OpenAPI OK.
- La primera ejecución API tuvo una URL de migración vacía que impidió colección; después, una variable de migración sintética heredada provocó 1 fallo de configuración/134 pasos. Se corrigió el entorno de ejecución (URL de aplicación sintética, variable de migración retirada, cwd sin `.env` raíz), no las aserciones de dominio, y se obtuvo el resultado final de 135 pasos. No se accedió a una DB operativa.
- Runtime observado: Node **24.19.0**, npm **11.17.0**; el contrato del proyecto declara **24.20.0/11.19.0**. Los resultados locales no acreditan el entorno exacto fijado. Sin bypass de engine-strict ni instalación global.

### Persistencia y reversión

`test_technical_metadata_survives_transaction_reopen_and_version_history` amplía la prueba DB para guardar metadatos, aprobar v1 con otro auditor, cargar v2, reabrir transacciones, comprobar notas/claves, dos versiones históricas, revisión vinculada a v1 y proyección v2 pendiente. **No se ejecutó aquí; queda para PostgreSQL aislado.** El almacenamiento estructurado no agrega esquema ni migración; continúa pendiente probar upgrade/downgrade de `20261006_0012` junto con el bloque API.

Reversión web: retirar juntos editor, wiring/adaptador, cliente generado, regresiones y documentación de metadatos; no eliminar documentos/versiones creados ni reinterpretar notas históricas. API conserva validación de revisión por versión y requiere rollback coordinado con 0012 si se revierte ese contrato. `.env`, `.atl` y respaldos previos se preservan. Sin commits, push, PR, SDD ni activación de RDD.

### Pendientes globales

AUD-011, AUD-012, AUD-014 y comprobaciones integradas de seguridad/operación/DB permanecen fuera de este bloque, sin reducir el objetivo autorizado de los 14 fixes. No se afirma cierre global, validación legal, autenticación productiva ni soporte de binarios.

## Remediación secuencial — dependencias y controles operativos (2026-10-07)

Este bloque continúa los anteriores sin borrar los hallazgos ni resultados históricos. Cambios locales autorizados, sin commit/push/PR, SDD, RDD, acceso a bases operativas ni modificación del stack existente. `.env`, `.atl` y respaldos anteriores se conservan.

| Hallazgo | Corrección implementada | Evidencia y estado residual |
|---|---|---|
| AUD-011 | Next 16.3.6; overrides compatibles js-yaml 4.3.2, sharp 0.35.5, source-map-js 1.2.2, undici 8.10.2 y brace-expansion 1.1.21/5.0.12. El wrapper ESLint Next arrastraba braces sin parche; se retiró esa raíz y se fijaron configs TypeScript/React/hooks/a11y soportadas con guards declarativos App Router. No alias incompatible, downgrade ni audit fix force. | Audit inicial actualizado: **15 nodos, 14 high y 1 critical**. Instalación limpia posterior y audit all/prod: **0 avisos conocidos**. RED lint: 5 fallos/4 pasos; GREEN: **9 pasos**. **Dependencias verificadas localmente en runtime exacto; no demuestra seguridad de imágenes/OS ni ausencia de vulnerabilidades desconocidas.** |
| AUD-012 | Policy sobre fuente Git actual e historial alcanzable, formatos de tokens/credenciales/DNI-CUIL/contacto, términos estrictos, claves/Office/.env versionados y salida opaca. CI incorpora regresiones, audit Python frozen, único head/readiness, licencias npm/YAML real, inventarios CycloneDX, restore lógico sintético y journey Playwright desktop/móvil; mantiene OpenAPI/SDK y gates DB existentes. Proxy agrega CSP/frame-deny y desactiva access logs hasta probar redacción. Docs separan objetivos V1 de cobertura real. | RED controles inicial: 3 fallos/11 errores; GREEN final: **18 pruebas Python**, incluyendo tres escenarios shell. Supply-chain actual pasa; policy fuente/historial pasa sin términos configurados y lo informa. Journey **2 tests descubiertos, ejecución integrada pendiente**; restore guard probado, **restore DB real pendiente** del bloque independiente. **Root de sobreafirmación y controles de piloto corregido; NO cerrado como gate productivo.** |
| AUD-014 | PowerShell comprueba migrador terminado, cinco endpoints privados DB/S3/AV y fallo de inspección/servicio; PS7 requerido explícitamente para bypass TLS sólo HTTPS loopback, sin override global ni redirects. Shell refuerza loopback y ausencia de servicios. Retry HTTP acotado equivalente. También se corrige `$home`, que colisionaba con `$HOME` de solo lectura. Marcador Unicode escapado evita dependencia de encoding PS5.1. | RED script original: error `$HOME`; RED shell original en copia temporal: servicio privado ausente aprobado incorrectamente. GREEN: **7 escenarios mock PowerShell**, tanto PS7 como PS5.1; **3 escenarios shell**, syntax-check pasa. PS5.1 con switch rechaza antes de HTTP con salida ejecutable `pwsh -File scripts/smoke.ps1 -AllowLocalCertificate`. **Paridad controlada verificada; smoke contra stack real aún pendiente.** |

### Runtime y comprobaciones locales

- Node **24.20.0**, npm **11.19.0**, sin bypass de `engine-strict` ni escrituras de configuración global. Archivo oficial portable verificado contra [SHASUMS de Node](https://nodejs.org/dist/v24.20.0/SHASUMS256.txt), SHA-256 del zip Windows x64 `6cac9ffbca8f6a47091e4b5c772e0606049c3871cb67d900c0cedde630e545ba`, extraído fuera del proyecto.
- `npm install --package-lock-only` seguido de `npm ci`: exit 0, lock coherente. `npm ls --all --json`: exit 0; `npm sbom --sbom-format cyclonedx`: exit 0, artefacto temporal externo.
- `npm audit --json` y `npm audit --omit=dev --json`: **0 info/low/moderate/high/critical**, exit 0.
- `npm run api:generate`: exit 0, mismo generador 0.99.0; `npm run format:check`, `npm run lint`, `npm run typecheck`: exit 0. `npm test`: **42 passed, 3 archivos**; `npm run build`: **Next 16.3.6**, exit 0.
- `npm run test:lint`: **9 passed**. Tests negativos de hooks condicionales, any, ARIA inválida, anchor interno raw, img/script raw e import `next/document`; caso válido con Link/JSX tipado.
- `python -m unittest discover -s scripts/tests -q`: **18 passed**. Ruff scripts lint/format y shell syntax-check pasan tras normalización. `scripts/tests/smoke.Tests.ps1`: **7 escenarios** en cada versión PowerShell, con dobles aislados y cero llamadas a Docker/HTTP reales.
- PyYAML **6.0.3** aislado: YAML real + SHA/timeout/permisos y allowlist npm pasan. La allowlist conserva obligaciones MPL/LGPL de paquetes actuales; no constituye aprobación legal ni cubre licencias Python, sólo inventariadas.
- Export `uv --frozen --all-groups --no-emit-project` + **pip-audit 2.10.0** aislado: **No known vulnerabilities found**, exit 0. Un primer intento usó ruta incorrecta de uv y el scanner recibió un archivo ausente; se corrigió ruta/cwd antes del resultado final, sin modificar locks Python ni aserciones.
- La primera ampliación policy detectó falsos positivos de variable `token`, fixture de redacción y literal de prueba; se estrechó detección a credenciales literales y placeholders sintéticos explícitos, se construyó el probe sin almacenar PII como literal y se añadieron regresiones JSON/YAML y variables. Sin excepciones para ocultar secretos reales.

### Fuentes y tradeoff del tooling

Fuentes oficiales verificadas: [Next parche 16.3.6](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j), [js-yaml 4.3.2](https://github.com/advisories/GHSA-2883-xcg3-v3hh), [sharp 0.35.5](https://github.com/advisories/GHSA-wq5f-xc86-pv6w), [source-map-js 1.2.2](https://github.com/advisories/GHSA-68fv-2mgg-jv7q), [undici](https://github.com/advisories/GHSA-w293-vg96-wgc3), [braces sin parche publicado](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). No se ejecutaron exploits ni se infiere explotación en la aplicación.

Configs directas siguen [typescript-eslint](https://typescript-eslint.io/users/configs/), [React/hooks](https://react.dev/reference/eslint-plugin-react-hooks) y plugins React/a11y. Se conservan guards de código/React/accesibilidad y se endurecen usos peligrosos App Router; no se declara equivalencia con **todas** las heurísticas Next Core Web Vitals de fuentes/polyfills/Pages Router. El tradeoff evita un paquete sin parche manteniendo pruebas negativas, build y tipos, sin replicar un framework de AST propio. Revisar nuevamente la decisión cuando exista upstream sin el transitivo vulnerable.

### Continuación segura y límites de cierre

1. Verificador independiente: PostgreSQL efímero para pruebas negativas/persistencia/RLS y migración 0012 upgrade/downgrade; no base operativa. Ejecutar restore con origen loopback terminado `_test`, destino vacío distinto `_restore_test`, `HYS_ENVIRONMENT=test`, URLs sólo en variables del proceso y `python scripts/restore_drill.py --allow-synthetic-restore --pg-bin <herramientas-portables>`. En CI `--container` usa herramientas de la misma versión del servicio efímero. Sin clean/drop; archive sólo en memoria hasta 16 MiB, timeout por herramienta 60 s, sin retener/imprimir contenido.
2. Journey integrado: contra API/web sintéticos loopback, `HYS_E2E_ALLOW_SYNTHETIC_MUTATIONS=1`, `HYS_E2E_BASE_URL` y bypass local TLS opcional explícito, ejecutar `npm run test:e2e`. Dos proyectos Chromium; no saltos silenciosos si falta autorización. No ejecutar sobre el stack operativo. La lista de tests acredita descubrimiento, **no ejecución**.
3. Linux/CI real: validar Caddy/Compose, imágenes/OS, E2E y smoke en stack efímero. No se ejecutó GitHub Actions ni se configuraron cuentas, secrets remotos o protecciones.

Permanecen deliberadamente abiertos datos reales, privacidad/KMS/PII productiva, autenticación/MFA, offline/binarios y corpus legal, rate limits por componente soportado, CSP con nonces/hashes, backup externo cifrado/objetos/RPO-RTO/DEC-006, imágenes/OS y provenance. CSP del piloto permite inline para Next; no usa unsafe-eval. No se supone un `rate_limit` inexistente en Caddy estándar. Esos gates no se marcan cerrados por checks locales verdes ni se implementa toda V1 dentro de esta remediación.

Reversión por unidad: AUD-011 manifest/lock/config/tests lint juntos, sin revertir SDK/contratos previos; AUD-012 scripts/CI/docs/headers/journey juntos, sin tocar datos/historia; AUD-014 ambos smoke y mocks juntos. No borrar backups ni modificar secretos para revertir.

Refinamiento AUD-014: [Docker CLI oficial](https://raw.githubusercontent.com/docker/cli/master/cli/command/container/port.go) devuelve error para un puerto correctamente no publicado; no se interpreta ese error como fallo de inspección. Los dos smoke consultan `docker inspect` con template JSON del binding específico y aceptan sólo `null`/`[]`; inspección fallida o cualquier binding falla. Se corrigieron los mocks para representar el comportamiento real (RED al simular `docker port` sin binding; GREEN con inspect), evitando enseñar a la prueba una semántica falsa.

## Remediación secuencial — regresiones reales de persistencia (2026-10-07)

La verificación integrada independiente detectó **7 fallos, 9 pasos y un error de teardown**, aunque las 135 pruebas unitarias/de contrato pasaban. Este bloque corrige esas causas sin borrar el registro anterior, debilitar autorización ni alterar datos operativos.

### Causas y correcciones

- **AUD-002 — rollback y metadatos:** el CHECK se creaba con nombre expandido mediante SQL directo, pero el downgrade volvía a aplicar la convención `ck_<tabla>_<nombre>`. Se usa `op.f("ck_document_reviews_version_required")` en creación y eliminación, con `postgresql_not_valid=True`; el ORM incorpora el mismo CHECK. La columna permanece nullable para conservar revisiones históricas de versión desconocida; no se infiere ninguna versión ni se reescriben filas históricas. El CHECK no validado protege nuevas filas y la FK compuesta exige organización/documento/versión compatibles.
- **Fixtures de asignaciones, documentos/versiones, máquinas y recorrido PDF:** intentaban crear obras con un técnico ya no autorizado. El alta/configuración usa el responsable creador permitido; el recorrido conserva técnicos, delegación del auditor y RHS independiente mediante asignaciones reales vigentes. Se mantienen escenarios y aserciones originales; no se elimina ni omite ninguna prueba.
- **AUD-001/AUD-004 — evidencia PostgreSQL adicional:** se agregan consultas reales de timeline sin asignación, con asignación en otra obra, vencida, de otra empresa y con sólo propiedad de creación; todas deben responder 404. La misma empresa con asignación vigente puede leer eventos. La verificación rechaza creador/corrector RHS con 409 y no-RHS con 403, sin cambiar el estado ni agregar verificaciones; un RHS independiente de la misma empresa sí cierra el desvío.

### RED → GREEN y comprobaciones finales

| Comprobación | Resultado observado |
|---|---|
| `test_document_review_metadata_requires_version_without_rewriting_legacy` | RED: CHECK ausente; GREEN: 1 paso. |
| `test_review_version_migration_preserves_unknown_legacy_and_checks_new_links` | RED PostgreSQL: downgrade intenta nombre doble y falla, con error de teardown; GREEN dentro de las 5 pruebas de migración. |
| Migración desde base vacía, metadata=head, rollback completo/parcial, legado y enlaces nuevos | 5 pasos en ejecución focalizada; incluido nuevamente en suite final. El legado conserva NULL/fundamento; se rechazan nuevas versiones NULL, de otro documento de la misma organización y cruces entre organizaciones; enlace válido aceptado, antes y después del roundtrip 0011→0012. |
| Cuatro escenarios originales bloqueados por fixtures | 4 pasos focalizados; nuevamente pasan en suite final, llegando a acciones/aserciones de dominio y PDF. |
| Timeline/RHS PostgreSQL | 10 escenarios focalizados; nuevamente incluidos en suite final. |
| Toda la integración API, después de normalización | **27 passed, 2 warnings, exit 0**, 32,02 s; teardown completo pasa. |
| Unitarias/de contrato API | **136 passed, exit 0**, 5,78 s. |
| Ruff lint / formato / mypy / snapshot OpenAPI | Exit 0; **63 archivos** formateados, **31 fuentes** tipadas, contrato sin cambios. No requiere regenerar SDK web. |

Las dos advertencias provienen de reflexión Alembic/SQLAlchemy sobre `dialect_options` y `not_valid`; no se ocultan, no son fallos de migración y `command.check` pasa. Los primeros intentos de la nueva matriz tenían errores propios del harness (código sintético con minúsculas, vigencia anterior al alta de personas, profesión/delegación del auditor, nombres de empresas repetidos y referencia a un campo no existente en `FindingView`); se corrigieron fixtures contra el contrato real, sin modificar guards de producción ni contar esos intentos como defectos del producto.

### Aislamiento y límites

PostgreSQL **17.11**, contenedor y volumen nuevos con etiqueta de propiedad exclusiva, puerto aleatorio publicado sólo en loopback y base sintética terminada `_test`. Migrador propietario y `hys_app` separados; `hys_app` verificado **sin superusuario ni BYPASSRLS**. Variables HYS heredadas retiradas antes de configurar URLs sintéticas; fixtures destructivas autorizadas sólo en esta base. No se leyó `.env` raíz ni se accedió/modificó el stack operativo. Recursos propios eliminados después de verificar identidad/etiqueta; logs sintéticos externos conservados para revisión. Sin commits, push, PR, SDD ni activación de RDD.

Este bloque acredita la corrección API/DB pendiente. No repite builds web ni comprobaciones de dependencias/operación ya verificadas sobre fuentes inalteradas; la síntesis independiente del objetivo completo y los gates productivos abiertos siguen siendo responsabilidad de la verificación final. No se declara aprobación global, cumplimiento legal ni autorización para datos reales.

## Verificación independiente integrada — candidato posterior a corrección DB (2026-10-07)

**Estado: bloqueado por una regresión residual AUD-009; no se declara cierre global.** Esta comprobación reemplaza los pendientes de ejecución PostgreSQL, restore y smoke de los apartados históricos, sin borrar sus resultados ni confundir controles del piloto con preparación productiva.

### Evidencia ejecutada

- Copia de los archivos actuales modificados, no de HEAD: **170 archivos incluidos**, SHA-256 sin cambios tras las verificaciones. Comparación con la primera copia independiente: sólo cinco archivos API cambiaron y se añadió la matriz DB de autorización. Web, scripts operativos, infraestructura, OpenAPI/SDK y locks permanecieron idénticos; se reutilizan explícitamente sus pruebas de 42 componentes/unitarias, 9 regresiones lint, 18 controles operativos, 7 mocks PS7 y 7 PS5.1, instalación limpia Node 24.20.0/npm 11.19.0, formato/lint/tipos/build y scanners sin avisos conocidos.
- API actual: **136 passed** unitarias/de contrato; Ruff lint y formato **63 archivos**, mypy **31 fuentes**, snapshot OpenAPI sin diferencias.
- PostgreSQL nuevo, migrador y `hys_app` separados, sin superusuario/BYPASSRLS para runtime: **27 passed, 136 deselected, 2 warnings**, exit 0 y teardown completo. Se ejecutaron metadata=head, rollback completo/parcial, roundtrip 0011→0012, legado NULL sin inferir historia, enlaces válidos y rechazo de nuevos NULL/documento ajeno/cruces de tenant; timeline real en seis condiciones y RHS independiente en cuatro; asignaciones/versiones/inspecciones/journey de cierre-PDF y notas estructuradas con claves desconocidas, revisión independiente v1 y v2 pendiente.
- Sonda externa adicional de revisión: autor de versión actual preparado como fixture de procedencia sintética; su revisión responde 409 y otro actor puede aprobar conservando historia. No se afirma que esa sonda demuestre un flujo de carga del navegador con cambio de autor.
- Linux real: imagen Caddy fijada valida configuración; build de API/web actuales, migración y seed terminan correctamente; DB, S3, AV, API y web saludables. **Smoke PowerShell 7 y POSIX pasan** contra HTTPS loopback propio; se inspeccionan puertos privados reales. Cabeceras reales incluyen CSP, `X-Frame-Options: DENY` y `nosniff`, sin `unsafe-eval`.
- Restore lógico real del candidato final, con herramientas de la misma imagen DB: origen sintético y destino nuevo distinto, fingerprint coincidente, exit 0, sin archivo retenido. No demuestra backup productivo externo/cifrado ni RPO/RTO.

### Matriz de cierre por hallazgo

| Hallazgo | Prueba y estado del alcance auditado |
|---|---|
| AUD-001 | `test_timeline_real_database_requires_current_worksite_and_company_scope`: seis escenarios DB; denegaciones 404 y lectura de la misma empresa. Verificado. |
| AUD-002 | `test_review_version_migration_preserves_unknown_legacy_and_checks_new_links`, metadata=head, rollback y revisión por versión; historia v1/v2 persistida. Verificado; rollback elimina el enlace añadido y reupgrade no inventa versiones para esas revisiones. |
| AUD-003 | OpenAPI/SDK iguales, payload tipado, respuesta/detalle con dirección, cuatro fixtures originales llegan a sus acciones y pasan. Verificado. |
| AUD-004 | `test_verification_real_database_requires_independent_rhs`: creador/corrector 409, no-RHS 403 sin modificar estado/historia, RHS independiente cierra. Verificado. |
| AUD-005 | Bordes compartidos unitarios y HTTP/DB independientes 120→201/121→422; dirección reabierta coincidente. Verificado. |
| AUD-006 | Componentes y `test_technical_metadata_survives_transaction_reopen_and_version_history`; sonda de navegador externa guardar/reload/reabrir pasó previamente sobre las mismas fuentes web. Verificado. |
| AUD-007 | Regresiones pendientes/EN_CORRECCION y legajos incompletos dentro de las 42 pruebas web. Verificado. |
| AUD-008 | Nombres/flechas/Home-End/foco en componentes y navegación real desktop; no certifica lector de pantalla, axe ni WCAG completa. Verificado en alcance. |
| AUD-009 | La primera ejecución Linux+Caddy pasa desktop y falla mobile después de crear. Sonda de lista anterior demuestra pérdida de selección. **No cerrado.** |
| AUD-010 | Matriz UI asignación/editor/obra/empresa y autorización/asignaciones DB reales pasan; backend conserva autoridad. Verificado. |
| AUD-011 | Lock/runtime exactos, build/tests, npm all/prod y scanner Python frozen sin avisos conocidos; no equivale a ausencia de CVE desconocidas. Verificado. |
| AUD-012 | Policy fuente/historial, controles/workflow/licencias/scanners, restore y cabeceras reales comprobados; documentación declara gates productivos abiertos. Browser integrado queda parcialmente fallido por AUD-009, no por CSP. |
| AUD-013 | Formato y etiquetas comprobados sobre bytes finales; sin normalizadores sobre fuente original. Verificado. |
| AUD-014 | PS7/POSIX smoke real, puertos privados y mocks PS5.1/PS7 pasan. Verificado. |

### Bloqueo residual: selección posterior a creación

El journey original Linux+Caddy obtuvo **1 passed / 1 failed**: mobile recibe POST 201 y dirección correcta, presenta “Obra creada y abierta”, pero permanece en inicio sin `tablist`. Todos los servicios estaban saludables. Una sola repetición diagnóstica con registro de orden pasó; no se usa para borrar el fallo original. Una sonda externa determinista conserva la respuesta real de lista previa, permite POST real 201 y devuelve esa lista anterior en la primera lectura posterior: la notificación de éxito aparece, pero la selección desaparece y la misma aserción de `tablist` falla.

La causa comprobada en `pilot-workspace.tsx` es el efecto que interpreta ausencia en una lista como autorización para `setSelectedId(null)`, inmediatamente después de que creación selecciona el ID confirmado. El timing exacto del commit backend no se demostró; no se presenta como causa confirmada. La corrección debe preservar la selección confirmada ante una lista obsoleta sin debilitar los guards de actor/obra ni las pruebas de recarga. No se corrigió código desde el verificador ni se ejecutó un ciclo de reintentos hasta obtener verde.

Contenedores, redes y volúmenes eliminados sólo tras validar nombres/etiquetas del proyecto exclusivo; puertos propios sin listeners. No se tocó el stack operativo, configuración privada, respaldos ni estado local. Evidencia sintética externa conservada. Sin commits, push, PR, RDD ni SDD; no se ejecutó CI remoto. Permanecen fuera de esta remediación datos reales, autenticación/MFA, KMS/PII, legal, offline/binarios, backup externo, nonces/CSP productiva, rate limits y provenance/imágenes/OS.

## Corrección residual AUD-009 — selección y confirmación de commit (2026-10-07)

**Estado: corrección local verificada; pendiente nueva comprobación del navegador integrado.** El fallo mobile y la sonda externa anteriores se mantienen como evidencia histórica. No se declara cierre global por estas pruebas locales.

### Dos mecanismos comprobados

1. **Selección:** el listado puede corresponder a un snapshot anterior al POST confirmado. Ya no revoca una selección por ausencia en ese listado: se consulta el detalle como autoridad de visibilidad. Un 403/404 vigente limpia selección, detalle, auditoría y anuncio de éxito, también durante el refresco posterior a una mutación. Los errores transitorios no se interpretan como pérdida de permisos. Se conservan generaciones, cancelación y limpieza de datos al cambiar actor/obra, sin flags, listas históricas ni estado paralelo.
2. **Transacción:** la hipótesis de commit se comprobó por separado con la ruta real, la dependencia real de unidad de trabajo y un `send` ASGI observado, sustituyendo sólo la sesión por una transacción sintética controlada. En FastAPI instalado **0.141.1**, el alcance por defecto emitía `201` antes de iniciar/completar el commit; un commit fallido también había enviado 201. `get_pilot_service` ahora declara `Depends(get_pilot_context, scope="function")`, según la [documentación oficial de FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope). La respuesta espera el commit; su fallo produce 500, nunca éxito previo. Las rutas del piloto materializan DTO o bytes PDF y no tienen streams, consultas diferidas ni tareas de fondo dependientes de la transacción; la sesión padre mantiene su alcance de request. Sin commits manuales adicionales, cambio de esquema, migración ni contrato wire.

### Evidencia RED → GREEN

| Prueba | Resultado |
|---|---|
| `AUD009 preserves a confirmed creation when the next list replays the pre-creation snapshot` | RED determinista: no existe tablist tras POST 201 y listado anterior. GREEN: selección/detalle permanecen y se realiza una sola lectura del detalle. |
| `AUD003 sends required jurisdiction with a typed worksite payload` | Se reforzó la aserción existente: éxito requiere también abrir la navegación de obra, no sólo presentar un mensaje. RED antes de la corrección; GREEN después. |
| `AUD009 authoritative detail denial ...` | RED en 403 y 404: persistía el anuncio de alta exitosa. GREEN: selección/datos/anuncio retirados. |
| `test_creation_response_waits_for_transaction_commit` | RED: 2 fallos (commit exitoso/fallido), orden `response_201 → commit_started`. GREEN: 2 pasos; durante commit no se envía respuesta, y después se observa 201 con commit completado o 500 ante fallo. |
| Regresiones AUD-009 focalizadas | **11 pasos**, cubren actor, obra, mutación, refresco obsoleto, creación en vuelo, lista anterior, pérdida de scope/asignación, denegación autoritativa y error transitorio. |

El primer armado de la prueba ASGI omitía `version` en el DTO de fixture, y el primer replay de componente reutilizaba un objeto `Response` de cuerpo consumible. Ambos errores del harness se corrigieron antes de contabilizar la evidencia RED del producto; no se modificaron aserciones de seguridad ni guards de dominio para obtener verde.

### Comprobaciones finales del bloque

- Runtime portátil fijado, sin instalar/actualizar dependencias: **Node 24.20.0 / npm 11.19.0**.
- Web, después de normalización: `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm test` (**49 passed, 3 archivos, 20,83 s**) y `npm run build` (**Next 16.3.6**, compilación/TypeScript/páginas estáticas): exit 0. Regresiones de lint: **9 pasos**, exit 0.
- API: `python -m pytest tests/unit tests/contract -q`: **138 passed**, exit 0 (4,03 s); Ruff lint pasa, format-check **64 archivos**, mypy **31 fuentes**, snapshot OpenAPI OK. SDK no regenerado porque el contrato no cambió.
- `git diff --check`: exit 0; los avisos de normalización CRLF/LF no representan errores de whitespace.
- Añadida `creation-list-snapshot.spec.ts`: captura la lista desde la API real antes de crear y reproduce ese payload en el primer GET posterior al POST real 201; comprueba selección y lectura inmediata del detalle. Conserva el journey original. La enumeración detecta **4 casos** (dos journeys × desktop/mobile), pero **no se ejecutó el navegador ni PostgreSQL en este bloque**. La primera enumeración sin opt-in sintético fue correctamente rechazada por configuración; una enumeración posterior con loopback/opt-in sólo descubre casos, sin enviar requests.

### Continuación y límites

La verificación independiente debe volver a ejecutar los dos journeys originales y los dos casos de snapshot sobre runtime Linux/API actual aislado, con POST seguido de lectura inmediata. El cambio API modifica el límite de transacción HTTP, no los guards, modelos ni migraciones ya comprobados; las evidencias anteriores de DB/restore/infra/scanners/locks siguen identificadas, no se presentan como nueva ejecución sobre estos bytes. No se repitieron stacks Docker ni se accedió a datos operativos.

Reversión de esta unidad: componente y regresiones de selección; alcance de dependencia y prueba de frontera ASGI; nuevo caso E2E y documentación asociados. No revertir las correcciones previas de seguridad/historia/migración ni eliminar registros persistidos. `.env`, `.atl`, respaldos y fuentes de las restantes remediaciones se preservan. Sin commits, push, PR, SDD ni activación de RDD.

## Verificación final del candidato residual — ejecución interrumpida por entorno (2026-10-07)

**Estado: evidencia funcional parcial confirmada; cierre global pendiente de los cuatro casos E2E.** No se declara aprobación. Este apartado actualiza los resultados del candidato posterior a la corrección AUD-009 y conserva íntegros los fallos y comprobaciones anteriores.

| Comprobación del candidato actual | Resultado efectivamente obtenido |
|---|---|
| Unitarias/de contrato API, incluyendo frontera ASGI de commit exitoso/fallido | **138 passed**, exit 0, 3,61 s. |
| PostgreSQL nuevo con propietario/runtime separados, migraciones/RLS/historia/timeline/RHS | **27 passed, 138 deselected, 2 warnings**, exit 0, 59,00 s; metadata=head y teardown completo pasan. |
| API Ruff lint / formato / mypy / OpenAPI | Exit 0; **64 archivos** con formato correcto, **31 fuentes** sin errores; snapshot sin diferencias. |
| Web formato / lint / tipos | Exit 0, runtime portátil **Node 24.20.0/npm 11.19.0**, dependencias previamente instaladas desde el mismo lock. |
| Web componentes/unitarias | **49 passed, 3 archivos**, exit 0, 54,61 s. |
| Build Linux de API/web actuales; Compose sintético nuevo | Build/up terminados, exit 0; migración exit 0, seed exit 0; DB, S3, AV, API y web saludables antes de la interrupción. |
| POST real seguido inmediatamente de GET detalle, HTTPS por Caddy | **201 → 200**, dirección persistida coincidente. |
| Smoke real del candidato actual en PowerShell 7 / POSIX | Ambos **Smoke OK**, exit 0; proyecto exclusivo, puertos privados inspeccionados. |
| Nuevos journeys originales y snapshot, desktop/mobile | **4 descubiertos; NO ejecutados**. El archivo de resultado E2E final no existe; descubrimiento no equivale a prueba aprobada. |

### Integridad y reutilización exacta

Se copiaron **172 archivos actuales incluidos**, sin configuración privada, estado local, herramientas ni respaldos. Los siete hashes entregados por el escritor coinciden; comparación SHA-256 final de esos 172 archivos: **cero cambios de fuente** durante los checks. Sólo se añade este apartado autorizado al informe.

Respecto del candidato independiente anterior cambiaron servicio API, workspace, regresiones de componentes y ADR; se agregaron pruebas de frontera ASGI y snapshot E2E. **Modelos/migraciones, OpenAPI/SDK, locks, scripts operativos e infraestructura permanecen idénticos.** Por esa comparación se conserva, sin presentarla como nueva ejecución, la evidencia anterior de scanners npm all/prod y Python sin avisos conocidos, 9 regresiones lint, 18 controles operativos, 7 mocks PS7 y 7 PS5.1, licencias/workflow/policy, validación/cabeceras Caddy y restore lógico sintético. El cambio de alcance de dependencia HTTP no altera el esquema restaurado. La prueba de metadatos e historia sí se volvió a ejecutar dentro de las 27 DB del candidato actual.

### Estado de los 14 hallazgos

Las matrices anteriores siguen identificando implementación y pruebas de AUD-001–AUD-014. PostgreSQL y componentes actuales corroboran sus alcances de autorización, independencia, contrato, bordes, persistencia, estados, accesibilidad y permisos; dependencias, normalización y smoke mantienen la evidencia anterior o actual indicada. La selección residual AUD-009 y la frontera de commit están comprobadas por componentes/ASGI actuales y POST→GET real. **Falta demostrar los cuatro journeys integrados del candidato corregido**, por lo que no se cierra AUD-009 ni se declara concluida la verificación global de los 14. No se transforma ese pendiente de entorno en un nuevo defecto de fuente.

### Interrupción y recursos propios pendientes

Al reanudar se inspeccionaron los handles existentes, sin reiniciar ni repetir servicios: Docker informó que no existe el named pipe `dockerDesktopLinuxEngine`; no se observaron procesos Docker Desktop/backend ni listeners en los tres puertos propios. Los handles de ejecución anteriores dejaron de estar disponibles. **Motor Docker no disponible** impide ejecutar E2E e inventariar/eliminar recursos; ausencia de listeners no demuestra eliminación de contenedores/volúmenes.

Recursos exactos del verificador pendientes de comprobación/limpieza: proyecto Compose `hys-final3-c56cb8` (servicios `db`, `db-provision`, `migrate`, `api`, `web`, `seaweedfs`, `clamav`, `caddy`; redes `_edge` y `_backend`; volúmenes `_postgres-data`, `_seaweed-data`, `_clamav-data`, `_caddy-data`, `_caddy-config`); contenedor PostgreSQL separado `hys-final3-db-c56cb8`, etiqueta `hys.audit.owner=c56cb8`. Puertos exclusivos loopback: 55459, 58059 y 58459. **Limpieza NO confirmada**. No se inició Docker Desktop ni ningún servicio del host; no se tocó el stack operativo ni se ejecutó prune.

Una vez que el usuario restablezca Docker Desktop, se debe inspeccionar ese proyecto existente y sus etiquetas antes de continuar, ejecutar sólo los cuatro casos E2E pendientes sobre el candidato actual y eliminar exclusivamente esos recursos tras comprobar su identidad. Se mantienen fuera de alcance datos reales, autenticación/MFA, KMS/PII, corpus legal, offline/binarios, backup externo/RPO-RTO, CSP productiva con nonces, rate limits y provenance/scans de imágenes/OS. No hubo commits, push, PR, SDD, RDD ni CI remoto. Memoria persistente retenida sin llamadas atribuibles al agente porque la identidad runtime no fue confirmada; esta limitación no invalida las pruebas registradas.

## Cierre de la verificación independiente — AUD-001 a AUD-014 (2026-10-07)

**Los 14 hallazgos quedan remediados y verificados dentro del alcance auditado del piloto sintético. No se declara preparación para producción.** Este resultado final reemplaza el estado pendiente de los cuatro E2E y la limpieza del apartado inmediatamente anterior; preserva los fallos históricos, la interrupción del motor y las correcciones sucesivas como trazabilidad.

### Evidencia terminal del candidato actual

Se reanudó el **proyecto existente y exclusivo**, sin reiniciar el stack operativo ni repetir builds/pruebas ya finalizadas. Docker volvió a responder como 29.7.2; se verificaron etiquetas de propiedad, salud estable y hashes antes de continuar. La fuente del servicio API dentro de la imagen coincide con el manifiesto; los IDs de imagen API/web coinciden con el registro del build Linux actual. Los **172 archivos incluidos** del candidato conservan sus hashes, sin modificaciones de fuente por el verificador.

- `npm run test:e2e`, Chromium fijado, Node **24.20.0/npm 11.19.0**, API/web Linux actuales y PostgreSQL sintético propio detrás de Caddy HTTPS loopback: **4 passed, exit 0, 15,2 s**, sin reintentos ni omisiones. Se ejecutaron `confirmed creation survives replay of the actual pre-creation list` y `synthetic create, reload, navigation and negative authorization journey`, cada uno en desktop y mobile. El primer caso captura un GET real anterior, confirma POST real y reproduce aquella lista; selección/detalle permanecen. El segundo conserva creación, recarga, teclado y denegaciones originales. No se sustituyó el fallo histórico por una repetición hasta obtener verde: se comprobó el candidato corregido y su regresión explícita.
- Otra comprobación HTTP real terminal: **POST 201 → GET detalle inmediato 200**, dirección persistida coincidente. Confirma visibilidad inmediata del alta con la unidad de trabajo actual.
- Se conserva la ejecución ya obtenida sobre los mismos bytes actuales: **138 API unitarias/de contrato**, **27 PostgreSQL / 138 deseleccionadas / 2 advertencias conocidas de reflexión / teardown limpio**, **49 pruebas web en 3 archivos**, API Ruff **64 archivos**, mypy **31 fuentes**, OpenAPI, formato/lint/tipos web y build Linux; todo exit 0. Las dos variantes de `test_creation_response_waits_for_transaction_commit` prueban que el commit termina antes de 201 y que su fallo no emite éxito previo.
- Smoke real PowerShell 7 y POSIX del mismo proyecto: exit 0. Evidencia anterior de restore, cabeceras/configuración Caddy, scanners, licencias, policy, 18 controles operativos y 7 mocks por cada versión PS7/PS5.1 se conserva por comparación exacta de modelos/migraciones, infraestructura, scripts, contratos y locks inalterados; no se anuncia como nueva ejecución.

### Matriz definitiva de remediación acotada

| Hallazgo | Implementación y prueba que respaldan el cierre |
|---|---|
| AUD-001 | Timeline aplica asignación vigente de obra y empresa antes de eventos; `test_timeline_real_database_requires_current_worksite_and_company_scope`, seis escenarios reales, denegaciones 404 y lectura permitida de la misma empresa. |
| AUD-002 | Revisión identifica versión actual/autor independiente; `test_document_review_is_bound_to_current_immutable_version`, historia DB v1/v2 y sonda real de guard por procedencia. `test_review_version_migration_preserves_unknown_legacy_and_checks_new_links` prueba legado NULL sin inventar historia, rechazo de nuevos NULL/enlaces ajenos, enlaces válidos y roundtrip; metadata=head y rollback completo/parcial pasan. |
| AUD-003 | Dirección/jurisdicción, fixtures y contratos reconciliados; OpenAPI sin diferencias, SDK regenerado sin cambios, `AUD003 sends required jurisdiction with a typed worksite payload`, dirección HTTP persistida y cuatro recorridos originales DB alcanzan sus acciones y pasan. |
| AUD-004 | Regla canónica excluye creador/corrector y exige RHS; `test_verification_real_database_requires_independent_rhs`, cuatro escenarios reales, rechazos sin mutación y cierre independiente permitido. |
| AUD-005 | Límites de campo coherentes con DB; `test_input_lengths_match_persistence_boundaries` y borde HTTP/DB 120→201 / 121→422 previamente ejecutado sobre esquema sin cambios. |
| AUD-006 | Editor y acciones guardan versiones reales; `AUD006 loads and versions document metadata and reopens persisted values`, disponibilidad/horas/notas/claves desconocidas y `test_technical_metadata_survives_transaction_reopen_and_version_history` pasan. Se conserva el navegador previo de guardar/reload/reabrir, sin anunciar repetición. |
| AUD-007 | Resúmenes incluyen PENDIENTE y EN_CORRECCION, sin presentar legajo parcial como completo; `AUD007 counts every unresolved document and finding without claiming a pending file is current` y `AUD007 does not mark a partly populated technical file complete`. |
| AUD-008 | Tabs con foco itinerante/flechas/Home-End y nombres accesibles; `AUD008 supports roving keyboard tabs with Home and End`, `AUD008 names inline stage and person verification controls` y teclado de los journeys desktop/mobile actuales. No equivale a certificación WCAG/lector de pantalla completa. |
| AUD-009 | Generaciones/contexto descartan respuestas obsoletas; detalle, no ausencia en listado, resuelve visibilidad. Regresiones actuales de creación, actor/obra/mutación, 403/404 y error transitorio; **cuatro E2E actuales**, incluyendo replay real desktop/mobile, pasan. Frontera de commit comprobada por ASGI y POST→GET real. |
| AUD-010 | Permisos UI reflejan vigencia/obra/empresa/editor y conservan backend como autoridad; matrices `AUD010 prevents resource mutation with %s assignments`, `AUD010 follows current audit editor rather than original author: %s` y asignaciones PostgreSQL pasan. |
| AUD-011 | Manifest/lock compatibles fijados; instalación limpia/runtime exacto, build y pruebas comprobados, npm all/prod y Python frozen sin avisos conocidos en la evidencia registrada. Sin promesa sobre vulnerabilidades desconocidas. |
| AUD-012 | Cobertura documental ajustada a controles reales: policy/historial, regresiones, workflow/licencias/inventarios/scanners, restore sintético real y cabeceras Caddy; journeys integrados actuales completos. Los gates productivos se declaran pendientes, no se presentan como implementados. |
| AUD-013 | Normalización y etiquetas corregidas; checks de formato API/web actuales pasan, sin normalización mutante durante la verificación. |
| AUD-014 | Smoke PS7/POSIX real comprueba migración y puertos privados; siete mocks PS7 y siete PS5.1 conservan rechazo explícito y seguro del bypass no soportado. |

### Limpieza e integridad confirmadas

Antes de eliminar se validaron **8 contenedores, 5 volúmenes y 2 redes** con la etiqueta exacta del proyecto `hys-final3-c56cb8`. `down --volumes` del proyecto exclusivo terminó exit 0; el PostgreSQL separado `hys-final3-db-c56cb8` se eliminó sólo tras comprobar `hys.audit.owner=c56cb8`. Inventario posterior: **0 contenedores / 0 volúmenes / 0 redes del proyecto**, y **0 listeners** en 55459, 58059 y 58459. No se ejecutó prune ni eliminación del stack operativo. Configuración privada, respaldos y estado local permanecen fuera de la copia y sin modificaciones.

### Qué no significa este cierre

No autoriza datos reales ni demuestra cumplimiento legal o producción. Permanecen pendientes autenticación/MFA, KMS/PII productiva, corpus legal profesional, offline/binarios, backup externo cifrado/RPO-RTO/objetos, CSP productiva con nonces, rate limits, scans de imágenes/OS y provenance, CI remoto/protecciones y UAT/lector de pantalla exhaustivos. No hubo commits, push, PR, SDD ni activación de RDD. La identidad de memoria del runtime sigue sin confirmarse; no se ejecutaron llamadas persistentes atribuidas a este agente durante estas últimas verificaciones, sin afectar el resultado funcional.