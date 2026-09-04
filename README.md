# H&S Gestión

Piloto funcional para gestionar Higiene y Seguridad en obras civiles con datos
exclusivamente sintéticos.

## Primer flujo vertical

El alcance implementado es:

`obra → documentación/vencimientos → auditoría → desvío → cierre → dashboard → PDF`

El recorrido se apoya en contratistas, personal, etapas y maquinarias sintéticas
cuando la obra los necesita.

La interfaz permite crear y volver a abrir una obra. Cada operación persiste en
PostgreSQL y aplica el contexto de organización, las asignaciones funcionales y
las políticas RLS. Los cinco actores seleccionables son identidades fijas del
piloto para recorrer los permisos de Técnico, Auditor y Responsable H&S; no
constituyen autenticación de producción.

Reglas verificables de este corte:

- `NO_CUMPLE` crea y enlaza un desvío en la misma transacción.
- `NO_APLICA` y `NO_VERIFICADO` requieren motivo.
- La vigencia documental se deriva en hora local de Buenos Aires, con una
  ventana de aviso de 30 días.
- El estado inicial de una maquinaria queda respaldado por una inspección y un
  motivo.
- Una auditoría finalizada no acepta nuevos controles.
- El creador del desvío y el autor de la última corrección no pueden verificarlo
  ni cerrarlo.

La auditoría llega a `FINALIZADA`; el cierre operativo de este piloto es el
desvío `CERRADO`. El botón de PDF genera una respuesta síncrona desde el estado
persistido de la obra.

## Límites del piloto

- Sin datos personales reales: no ingresar DNI, CUIL, correo, teléfono ni
  nombres reales.
- La documentación guarda metadatos y vencimientos, no archivos binarios.
- Catálogos, controles, severidades y referencias son sintéticos; no expresan
  cumplimiento legal.
- Sin autenticación productiva, MFA, offline, IA/OCR, analítica avanzada,
  portal externo ni integraciones.
- No apto para producción.

El blueprint completo sigue documentado en
[`docs/blueprint/README.md`](docs/blueprint/README.md); este flujo es un recorte
deliberado para validación de piloto.

## Estructura

```text
apps/api/          FastAPI y monolito modular
apps/web/          Next.js
docs/              Blueprint, arquitectura, ADR y operación
infra/             Caddy y artefactos locales existentes
scripts/           Validaciones y smoke test
```

## Ejecución local

1. Copiar `.env.example` a `.env` y reemplazar todos los valores `CHANGE_ME`.
2. Ejecutar `docker compose config --quiet`.
3. Ejecutar `docker compose up --detach --build`.
4. Abrir `https://localhost` y aceptar únicamente el certificado local del
   entorno de desarrollo.
5. Ejecutar `HYS_SMOKE_INSECURE_LOCAL_TLS=1 sh scripts/smoke.sh` para comprobar
   frontend, backend, PostgreSQL y puertos privados.

Para cargar el recorrido reproducible en la base configurada, ejecutar desde la
raíz con `HYS_MIGRATION_DATABASE_URL` disponible:

```text
uv run --project apps/api python -m hys_api.modules.pilot.demo_seed
```

El comando es idempotente por UUID: repara las filas sintéticas fijas y su
metadato de auditoría sin reiniciar la historia de correcciones y verificaciones.

Alembic usa `HYS_MIGRATION_DATABASE_URL` con el rol propietario. La API usa
`HYS_DATABASE_URL` con el rol fijo `hys_app`, sin superusuario ni `BYPASSRLS`;
esas credenciales no deben intercambiarse.

## Validación local

El baseline exige formato, lint, tipos, pruebas unitarias/contrato/integración,
migraciones desde base vacía, aislamiento RLS, cliente OpenAPI, build web y smoke
del stack completo. Python y Node se instalan desde `apps/api/uv.lock` y
`apps/web/package-lock.json`.
