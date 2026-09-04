# H&S Gestión

Piloto V1 para gestionar Higiene y Seguridad en obras civiles con datos sintéticos.
La obra es el agregado operativo principal y el circuito objetivo es:

`obra → legajos/vencimientos → maquinaria → auditoría online/offline → desvío → corrección → verificación independiente → cierre → PDF → dashboard`

## Estado

El repositorio está en **Hito 0 — blueprint y gobierno**. No está autorizado para
datos personales ni operación real. El gate vigente está documentado en
[`docs/blueprint/README.md`](docs/blueprint/README.md).

## Límites innegociables de la V1

- Una organización activa; aislamiento preparado para múltiples organizaciones.
- Hasta tres obras, 25 usuarios internos y aproximadamente 200 GB.
- Contratistas gestionados como entidades, sin acceso autenticado.
- MFA obligatorio y acceso público exclusivamente por HTTPS.
- Auditoría online y paquete offline cifrado con vigencia de siete días.
- Reglas jurídicas reales siempre inactivas y marcadas
  `PENDIENTE_VALIDACION_NORMATIVA` hasta revisión H&S/legal.
- Datos exclusivamente sintéticos hasta contar con backup cifrado externo y un
  restore completo probado.
- Sin firma digital certificada, IA decisoria, OCR, portal de contratistas ni
  afirmaciones de cumplimiento legal.

## Estructura prevista

```text
apps/api/          FastAPI y monolito modular
apps/web/          Next.js/PWA
docs/              Blueprint, arquitectura, ADR y operación
infra/             Caddy y artefactos de despliegue
.github/workflows/ CI reproducible
```

El paquete de traspaso que contiene fuentes restringidas vive fuera de este
repositorio y no debe copiarse, versionarse ni usarse como fixture.

## Validación y ejecución local

La CI ejecuta la política de fuentes, formato, lint, tipos, pruebas unitarias y
de contrato, migraciones desde una base vacía, aislamiento RLS, build web y un
smoke del stack completo. Las dependencias de Python y Node se instalan
exclusivamente desde `apps/api/uv.lock` y `apps/web/package-lock.json`.

Para validar con Docker Compose en un servidor o VM compatible:

1. Copiar `.env.example` a `.env` y reemplazar todos los valores `CHANGE_ME`.
2. Ejecutar `docker compose config --quiet`.
3. Ejecutar `docker compose up --detach --build`.
4. Ejecutar `HYS_SMOKE_INSECURE_LOCAL_TLS=1 sh scripts/smoke.sh` para el dominio
   local, o definir `HYS_SMOKE_BASE_URL` con el dominio HTTPS del entorno.
5. Inspeccionar `docker compose ps --all`; el servicio `migrate` debe finalizar
   con código cero y `api`, `web`, PostgreSQL, SeaweedFS y ClamAV deben estar
   saludables.

Alembic usa `HYS_MIGRATION_DATABASE_URL` con el rol propietario. La API usa
`HYS_DATABASE_URL` con el rol fijo `hys_app`, sin privilegios de superusuario ni
`BYPASSRLS`; no deben intercambiarse esas credenciales.
