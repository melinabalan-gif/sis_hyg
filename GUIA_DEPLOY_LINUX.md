# Hoja de guía: desplegar H&S Gestión en Linux

**Fecha de revisión: 2026-10-07 · Alcance: piloto privado con datos sintéticos.**

Esta guía organiza el despliegue del repositorio actual en un servidor Linux. No ejecuta instalaciones ni convierte el piloto en un producto listo para producción. Primero se valida un entorno privado; la publicación y los datos reales tienen un gate independiente al final.

## Ruta rápida

1. Aprobar una versión que incluya las correcciones locales y preparar una VM Ubuntu.
2. Instalar Docker, restringir el acceso y configurar secretos propios del servidor.
3. Desplegar el Compose actual mediante un override **sólo loopback**, migrar y cargar datos sintéticos.
4. Acceder por túnel SSH, validar persistencia/permisos y ensayar recuperación.
5. Mantener el piloto privado hasta implementar y aprobar los controles productivos pendientes.

Para Hostinger, completar también [GUIA_DEPLOY_HOSTINGER.md](GUIA_DEPLOY_HOSTINGER.md).

## 1. Punto de partida y decisiones

| Tema | Situación actual / decisión |
|---|---|
| Aplicación | Next.js/React + FastAPI, monolito modular; no es una web estática para subir por FTP. |
| Stack | `db`, `db-provision`, `migrate`, `api`, `web`, `seaweedfs`, `clamav`, `caddy` en `compose.yaml`. No agregar un worker inexistente. |
| Versiones | Imágenes fijadas por digest; Dockerfiles usan Python 3.14.7 y Node 24.20.0; `uv.lock` y `package-lock.json` son obligatorios. No actualizar dependencias durante el deploy. |
| Persistencia | PostgreSQL, SeaweedFS, firmas ClamAV y estado Caddy en volúmenes nombrados. Reiniciar un contenedor no debe borrar datos. |
| Seguridad del piloto | `X-Pilot-Actor` selecciona identidades sintéticas. No acredita identidad real. TLS, RLS, CORS o un selector de usuario no sustituyen autenticación. |
| Release | Al redactar, existen correcciones locales sin commit/publicación. Clonar GitHub por sí solo **no garantiza incluirlas**. |
| Entrada actual | Caddy publica 80/443 TCP y 443 UDP en todas las interfaces. **No ejecutar el Compose base sin restricción de red en un servidor público.** |

### Gate 0 — elegir los bytes que se desplegarán

- [ ] Revisar `git status --short`, `git diff --stat` y el informe `resultado_audit_sistema2026-10-06.md`.
- [ ] Con autorización separada, integrar/publicar los fixes y obtener un SHA aprobado; no suponer que `main` ya los contiene.
- [ ] Alternativa para una demostración antes de publicar: paquete revisado con manifiesto/hashes que incluya los archivos nuevos de migración y excluya `.env`, respaldos, `.atl`, `.tools`, `.git`, `node_modules`, `.next` y `.venv`. Esto permite el piloto, pero no sustituye una release trazable.
- [ ] Registrar SHA o hash del paquete, fecha, responsable, locks y digests. No desplegar una rama móvil mediante `git pull` automático.

Para la ruta Git, una vez que exista el SHA aprobado:

```bash
# En el servidor; reemplazar RELEASE_SHA con el SHA aprobado.
git clone https://github.com/melinabalan-gif/sis_hyg.git /opt/hys-gestion
cd /opt/hys-gestion
git checkout --detach RELEASE_SHA
git rev-parse HEAD
git status --short
```

Preparar previamente `/opt` con permisos del usuario operador; no usar un token dentro de la URL. Un repositorio privado requiere clave de despliegue de sólo lectura o mecanismo equivalente.

## 2. Preparar el host Linux

**Base propuesta: Ubuntu Server 24.04 LTS, arquitectura compatible con los digests de las imágenes.** Docker publica su instalación oficial y sistemas admitidos en [Docker Engine para Ubuntu](https://docs.docker.com/engine/install/ubuntu/) (consultado 2026-10-07).

| Recurso | Planificación, no benchmark |
|---|---|
| Piloto pequeño | Evaluar inicialmente 4 vCPU, 8 GB RAM y 80–100 GB SSD; medir, no garantizar capacidad. Build Next y carga inicial de firmas ClamAV pueden exigir más RAM. |
| Objetivo histórico del proyecto | `docs/operations/entorno.md` propone 8 vCPU, 24 GB RAM y 1 TB cifrado para la VM objetivo. Reducirlo requiere una decisión registrada, no presentarlo como el baseline aprobado. |
| Disponibilidad | Un host es un punto único de falla. No prometer alta disponibilidad. |
| Disco | Reservar margen para imágenes, DB, objetos y copias temporales; alertar antes de agotar espacio. |

Lista de preparación:

- [ ] Usuario nominal con clave SSH; comprobar una segunda sesión antes de deshabilitar login root/contraseña.
- [ ] Hora del host en UTC y sincronización NTP; la aplicación presenta fechas en Buenos Aires.
- [ ] Parches del SO y política de reinicios; volumen cifrado/gestión de claves según política.
- [ ] Docker Engine, Buildx y plugin Compose desde repositorio oficial; fijar y registrar versiones elegidas.
- [ ] `git`, `curl` y cliente SSH disponibles; no se necesita instalar Node/Python en el host para construir las imágenes.
- [ ] Compose **2.24.4 o posterior** para el `!override` de puertos que usa esta guía; versiones posteriores compatibles también sirven.
- [ ] Restringir SSH a IP administrativa/VPN en firewall perimetral. Durante el piloto, **no abrir 80/443 de Internet**.

```bash
docker version
docker compose version
docker info
df -h
free -h
ss -lntup
```

Los permisos del socket/grupo Docker equivalen prácticamente a control root del host: no tratar al usuario de deploy como de mínimo privilegio por el solo hecho de no llamarse root. Definir un modelo operativo acorde.

**Advertencia de firewall:** los puertos publicados por Docker pueden eludir reglas normales UFW. Usar enlaces loopback y validar firewall externo/reglas Docker según el backend de red, no desactivar iptables ni confiar sólo en `ufw deny`. Ver [Docker y filtrado de paquetes](https://docs.docker.com/engine/network/packet-filtering-firewalls/) (consultado 2026-10-07).

## 3. Configuración del piloto privado

### 3.1 Crear secretos del servidor

En una instalación nueva, copiar `.env.example` a `.env` con permisos 600. **No sobrescribir un `.env` existente.** Guardar secretos en un gestor custodiado; no copiarlos a tickets, capturas o Git.

```bash
cd /opt/hys-gestion
umask 077
test ! -e .env && cp .env.example .env
chmod 600 .env
```

Editar el archivo mediante un canal seguro. Generar valores aleatorios distintos; contraseñas hexadecimales facilitan evitar caracteres reservados en URLs. Si se usan otros caracteres, codificarlos correctamente en la URL PostgreSQL.

| Variable de `.env.example` | Valor / regla del piloto |
|---|---|
| `HYS_ENVIRONMENT` | `staging`; esto etiqueta el entorno, **no activa seguridad productiva**. |
| `HYS_DOMAIN` | `localhost`, sin esquema/puerto, para la ruta SSH de esta guía. |
| `ACME_EMAIL` | Correo operativo custodiado; no publicar su valor en el informe. |
| `POSTGRES_DB`, `POSTGRES_USER` | `hys`, `hys_owner` en una base **nueva del piloto**, no una base operativa existente. |
| `POSTGRES_PASSWORD` | Secreto propio del propietario/migraciones. |
| `HYS_DB_APP_PASSWORD` | Otro secreto para el rol fijo `hys_app`. |
| `HYS_MIGRATION_DATABASE_URL` | `postgresql+asyncpg://hys_owner:CHANGE_ME_OWNER_SECRET@db:5432/hys`. |
| `HYS_DATABASE_URL` | `postgresql+asyncpg://hys_app:CHANGE_ME_APP_SECRET@db:5432/hys`. Nunca intercambiar con la URL propietaria. |
| `HYS_PUBLIC_ORIGIN` | `https://localhost:8443` para el túnel cliente descrito abajo. Cambiarlo exige reconstruir `web`, pues se pasa como build arg. |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Dos valores aleatorios nuevos; no reutilizar credenciales DB. |
| `S3_BUCKET`, `S3_ENDPOINT` | `hys-private`, `http://seaweedfs:8333`; son nombres internos de Docker, no URLs del navegador. |
| `HYS_LOG_LEVEL` | `INFO`; no activar logs SQL/headers/bodies con datos sensibles. |
| `HYS_TRUSTED_HOSTS` | `localhost,api` según el ejemplo; variable declarada, **sin validación TrustedHost efectiva en el `Settings`/`main.py` actual**. Implementar/probar ese control antes de atribuirle protección. |
| `HYS_CORS_ORIGINS` | Vacío para mismo origen. Variable declarada, **sin middleware CORS configurado actualmente**; no asumir allowlist efectiva ni usar `*` como solución de proxy. |

`compose.yaml` traduce las variables S3 a `HYS_S3_*` para API, fija ClamAV `clamav:3310` y declara `API_INTERNAL_URL=http://api:8000` para web. La UI actual usa `/api` relativo y el proxy Caddy; declarar variables no prueba que la aplicación las consuma. La carga binaria S3/AV es un requisito futuro, no una función habilitada por estas variables. No inventar variables de JWT/MFA/KMS: esos controles todavía no están implementados. No mostrar la salida completa de `docker compose config`, que contiene secretos; usar `--quiet`.

### 3.2 Sustituir los puertos abiertos por loopback

**Archivo operativo a crear durante el despliegue, no incluido hoy en el repositorio:** `/opt/hys-gestion/compose.private.yaml`.

```yaml
services:
  caddy:
    ports: !override
      - "127.0.0.1:8080:80"
      - "127.0.0.1:8443:443"
```

`!override` reemplaza la lista; un override normal puede **agregar** puertos y dejar los públicos activos. Ver [reglas de merge Compose](https://docs.docker.com/reference/compose-file/merge/) (consultado 2026-10-07).

Mantener estas variables en la sesión del servidor, incluidas las sesiones de operación y smoke:

```bash
cd /opt/hys-gestion
export COMPOSE_FILE="$PWD/compose.yaml:$PWD/compose.private.yaml"
export COMPOSE_PROJECT_NAME=hys-pilot
docker compose config --quiet
```

El nombre estable conserva la identidad de los volúmenes. Un proyecto distinto con `.env` propio sirve para pruebas aisladas, pero **no cambia por sí solo los puertos**. No perder `COMPOSE_FILE` al abrir otra sesión ni ejecutar después el Compose base accidentalmente.

## 4. Desplegar, migrar y cargar el piloto

**Sólo sobre el host privado y base nueva verificados arriba:**

```bash
docker compose build
docker compose up --detach
docker compose ps -a
docker compose logs --tail=50 db-provision migrate
```

La cadena real del Compose es:

1. `db` queda healthy.
2. `db-provision` ejecuta `infra/postgres/init-app-role.sh`: crea/ajusta `hys_app` sin superusuario ni `BYPASSRLS`.
3. `migrate` ejecuta `alembic upgrade head` con propietario.
4. `api` espera migración exitosa, SeaweedFS y ClamAV healthy.
5. `web` y Caddy esperan API/web healthy.

`db-provision` y `migrate` deben terminar con código 0; **exited es normal para ellos**, no para servicios permanentes. ClamAV puede tardar varios minutos al descargar firmas. Si algo falla, detener el avance y diagnosticar; no omitir AV, cambiar permisos RLS ni ejecutar `create_all()` para arrancar.

Para inspeccionar revisión aplicada sin mutar esquema:

```bash
docker compose run --rm --no-deps migrate alembic current
docker compose run --rm --no-deps migrate alembic heads
```

Antes de cargar datos, confirmar el nombre/proyecto de la DB y que está destinada exclusivamente al piloto. La imagen API runtime no contiene `uv`; usar Python del contenedor `migrate`, que sí recibe la URL propietaria:

```bash
docker compose run --rm --no-deps migrate python -m hys_api.modules.pilot.demo_seed
```

El seed usa UUID fijos e inserción/actualización idempotente: **no es un comando de producción ni una migración**. No ejecutarlo sobre datos reales o una DB existente sin revisión explícita; puede alterar filas sintéticas preexistentes.

## 5. Abrir y comprobar el sitio sin publicarlo

Desde la computadora autorizada, reemplazar usuario/IP del servidor:

```bash
ssh -N -L 127.0.0.1:8443:127.0.0.1:8443 deploy@SERVER_IP
```

Abrir `https://localhost:8443`. El navegador manda UI y `/api/*` al mismo origen; Caddy enruta API a `api:8000` y el resto a `web:3000`. No abrir API 8000 o web 3000 al exterior para resolver conectividad.

**TLS:** el Caddyfile actual no contiene `tls internal`: Caddy usa certificados de CA local automáticamente para `localhost`. Extraer la CA desde el servidor a un destino privado y verificar su huella por SSH antes de confiar en ella en el equipo de prueba:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt /tmp/hys-pilot-root.crt
```

Transferir **sólo el certificado público** por SSH/SCP; jamás `root.key`. Usar un perfil de navegador de prueba y retirar esa confianza cuando termine el piloto. No aceptar certificados desconocidos ni desactivar TLS globalmente. Ver [HTTPS automático de Caddy](https://caddyserver.com/docs/automatic-https) (consultado 2026-10-07).

En el servidor, con las mismas variables Compose:

```bash
# Excepción acotada del smoke: únicamente HTTPS loopback sintético.
HYS_SMOKE_BASE_URL=https://localhost:8443 \
HYS_SMOKE_INSECURE_LOCAL_TLS=1 sh scripts/smoke.sh
docker compose ps -a
ss -lntup
```

El smoke comprueba live/ready, marcador sintético, migrador y ausencia de publicación DB/S3/AV. No sustituye pruebas de negocio. Registrar resultados mínimos, sin secretos ni logs completos.

### Gate 1 — piloto desplegado

- [ ] `db-provision`/`migrate` exit 0; revisión DB igual al único head.
- [ ] API, web, DB, SeaweedFS, ClamAV y Caddy healthy.
- [ ] Sólo 8080/8443 **loopback**; 5432, 8000, 3000, 3310, 8333, 8888, 9333 y 8080 de SeaweedFS no publicados hacia Internet.
- [ ] Comprobación externa autorizada confirma que nadie sin SSH/VPN llega al piloto, también por IPv6.
- [ ] Crear obra sintética, recargar/reabrir y comprobar dirección/documentación persistida; probar rechazo de acciones no autorizadas y separación creador/verificador.
- [ ] Validar escritorio/móvil, teclado, PDF y reinicio controlado sin pérdida de datos.
- [ ] Conservar evidencias del release y las verificaciones; no copiar PII al reporte.

## 6. Backup, operación y actualizaciones

**Todavía por implementar y ensayar:** backup externo cifrado, scheduler, retención, alertas y recuperación completa. `scripts/restore_drill.py` sólo acredita un ensayo lógico sintético bajo restricciones; no es un sistema de backup productivo ni restaura objetos.

Plan de recuperación mínimo:

1. Definir RPO/RTO y responsable; los 24 h/8 h del documento operativo son objetivos sujetos a aprobación, no una garantía.
2. Tomar dump PostgreSQL consistente y preservar roles/grants/esquema/migraciones.
3. Respaldar SeaweedFS completo: objetos y metadatos/filer/volumen necesarios, no sólo archivos elegidos. Coordinar un punto de recuperación DB/objetos; no copiar un volumen activo sin método consistente.
4. Preservar manifests, versión de aplicación y configuración; custodiar secretos y futuras claves de cifrado por separado. Caddy contiene claves privadas: cifrar y restringir su respaldo. Firmas AV se pueden reconstruir según política.
5. Enviar copias cifradas fuera del servidor; comprobar integridad, retención y capacidad de recuperar claves.
6. Restaurar en entorno aislado con DB/volúmenes/puertos nuevos, validar RLS, metadata+objetos y aplicación compatible; medir tiempos. Nunca probar restore sobre el entorno operativo.

Operación semanal: revisar memoria/CPU/disco, salud, firmas AV, certificados, edad del backup y alertas. No habilitar access logs sin probar redacción; no publicar `docker inspect`/config/env porque pueden contener secretos.

### Actualizar sin destruir información

- [ ] Congelar release e imágenes nuevas; validar CI/contratos/migraciones en una copia sintética.
- [ ] Backup verificado y plan de mantenimiento, compatibilidad de esquema y recuperación aprobado.
- [ ] Construir antes de cortar tráfico; detener escrituras durante el cambio si la migración lo requiere.
- [ ] Aplicar migración una sola vez con propietario; comprobar head y recrear API/web del release aprobado.
- [ ] Ejecutar smoke/journeys y confirmar integridad antes de reabrir acceso.

**Rollback:** volver a las imágenes anteriores sólo si admiten el esquema actual. Si no, usar recuperación documentada desde copias compatibles con pérdida potencial limitada por RPO. Un `alembic downgrade` exitoso en tests no autoriza degradar una DB con datos reales. No ejecutar `down --volumes`, `docker volume rm`, `system prune --volumes` ni reinstalar el SO para actualizar.

Las credenciales DB de `.env` no rotan mágicamente sobre un volumen existente: `POSTGRES_PASSWORD` inicializa la DB nueva; cambiar el propietario exige rotación SQL coordinada. `db-provision` sí ajusta `hys_app` al ejecutarse: coordinar el secreto de la API y su reinicio.

## 7. Gate 2 — habilitar producción y dominio público (no aprobado)

**El piloto actual se detiene antes de este gate.** Publicar un dominio con HTTPS no corrige `X-Pilot-Actor`. Antes de acceso público o datos reales:

- [ ] Autenticación real, MFA, sesiones/revocación y recuperación; identidad servidor confiable en lugar del selector sintético. Probar autorización tenant/obra y no confiar en headers enviados por el cliente.
- [ ] Privacidad formal: cifrado autenticado/KMS, claves separadas HMAC, trazabilidad, políticas de datos y aprobación legal/H&S.
- [ ] Upload binario/cuarentena/AV/offline y demás requisitos V1 que efectivamente se prometan; no anunciar funciones del blueprint que el piloto no implementa.
- [ ] Backup externo y restore DB+objetos+claves aprobado, monitoreo/alertas y runbooks.
- [ ] CSP nonce/hash, rate limiting en componente soportado, scans OS/imágenes/provenance, CI remoto y protecciones/aprobación de release.
- [ ] UAT, accesibilidad y capacidad medidas; responsable operativo firma autorización.

Después de aprobarlo, diseñar/revisar un perfil productivo: `HYS_DOMAIN=app.example.com`, `HYS_PUBLIC_ORIGIN=https://app.example.com`, control TrustedHost realmente implementado/probado, secretos propios y rebuild web. DNS A/AAAA correctos, 80/443 TCP y opcional 443 UDP sólo a Caddy. Caddy actual puede obtener ACME para un dominio real si se cumplen sus requisitos de validación; no hace falta afirmar que existe un `tls internal` para retirarlo. Validar certificados, redirecciones/HSTS y todos los endpoints antes de abrir acceso. Este perfil aún **no está creado ni probado** por esta guía.

## Referencias del proyecto

- `compose.yaml`, `.env.example`, `infra/caddy/Caddyfile`, `infra/postgres/init-app-role.sh` — topología y arranque.
- `apps/api/Dockerfile`, `apps/web/Dockerfile`, `apps/api/migrations/env.py` — builds/migraciones.
- `apps/api/src/hys_api/api/dependencies.py` — identidad sintética y autorización.
- `scripts/smoke.sh`, `scripts/restore_drill.py` — verificaciones con alcance limitado.
- `docs/operations/calidad-y-operacion.md`, `docs/operations/entorno.md`, `docs/blueprint/roadmap.md` y `resultado_audit_sistema2026-10-06.md` — gates, decisiones y evidencia. El diagnóstico histórico de estación en `entorno.md` no debe tomarse como estado actual.

## Aprendizajes y próximo paso

1. Desplegar contenedores, probar un piloto y autorizar producción son tres hitos distintos.
2. El túnel SSH protege el acceso al piloto, pero no implementa identidad de negocio.
3. La siguiente acción es aprobar la release que incluye los fixes, elegir host y asignar responsable; después ejecutar fases 2–5 en un entorno privado.
