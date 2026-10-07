# Hoja de guía: montar H&S Gestión en Hostinger

**Fecha de revisión: 2026-10-07 · Destino recomendado: VPS Linux · Primera entrega: piloto privado sintético.**

Para conservar este proyecto completo, la ruta es un VPS con Docker Compose. No basta con subir Next.js como una web aislada: también se requieren FastAPI, PostgreSQL con RLS, migraciones, SeaweedFS, ClamAV y Caddy. Este documento es un plan; no se contrató ni desplegó infraestructura.

## Ruta rápida

1. Confirmar presupuesto, región, operador y tamaño del VPS; no comprar un plan sólo por su nombre.
2. Aprovisionar Ubuntu, configurar clave SSH y firewall del proveedor **antes** de levantar servicios.
3. Aprobar/publicar una versión con los fixes locales; clonar GitHub hoy no asegura tenerlos.
4. Ejecutar las fases 2–5 de [GUIA_DEPLOY_LINUX.md](GUIA_DEPLOY_LINUX.md), con puertos loopback y túnel SSH.
5. Configurar recuperación externa y validar el piloto; mantener el acceso privado hasta cerrar el gate productivo.

## 1. Elegir el producto adecuado

| Producto / ruta | Evaluación para este repositorio |
|---|---|
| VPS Ubuntu + Docker Compose | Ruta recomendada para ejecutar la topología actual sin repartir servicios ni rediseñarla. Requiere administrar SO, Docker, datos, secretos y disponibilidad. |
| Business/Cloud con apps Node.js administradas | Hostinger **sí ofrece Node.js** en esos productos. Eso no acredita soporte para toda esta composición Python/PostgreSQL/S3/AV/Caddy. Podría servir para frontend tras un rediseño de integración, no como reemplazo directo del stack actual. |
| Hosting estático/WordPress/FTP | No aloja por sí solo los servicios persistentes requeridos. Este Next.js usa `output: "standalone"`, no una exportación estática. |

La oferta Node.js y el criterio de acceso root/Python se verificaron en [opciones Node.js de Hostinger](https://www.hostinger.com/support/node-js-hosting-options-at-hostinger/) y [tecnologías admitidas](https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/) (consultadas 2026-10-07). La recomendación VPS es una **inferencia técnica a partir del stack**, no una promesa comercial sobre cualquier plan.

### Antes de contratar

- [ ] Confirmar recursos/digests/arquitectura disponibles, almacenamiento y margen para builds/ClamAV.
- [ ] Evaluar 4 vCPU/8 GB/80–100 GB como punto de partida de piloto, **no como capacidad medida**. El baseline documental de la VM objetivo es 8 vCPU/24 GB/1 TB cifrado; cualquier reducción debe registrarse y validarse.
- [ ] Revisar renovación, impuestos, backups, disco/banda y costo de destino externo; esta guía no fija precios.
- [ ] Elegir ubicación por latencia y obligaciones de residencia de datos. Brasil figura entre las ubicaciones, pero verificar disponibilidad del plan antes de pagar y medir latencia desde los usuarios argentinos. La ubicación VPS queda fijada tras la configuración inicial. [Ubicaciones oficiales](https://www.hostinger.com/support/1583267-where-are-hostinger-servers-located/) (consultado 2026-10-07).
- [ ] Nombrar quién administra parches/incidentes/backups; no confundir asistencia/panel con administración integral de la aplicación.
- [ ] Reconocer que un solo VPS sigue siendo un punto único de falla.

## 2. Aprovisionar el VPS desde el panel

Los nombres pueden cambiar; corroborar el panel de la cuenta. El [dashboard VPS oficial](https://www.hostinger.com/support/5726606-how-to-use-the-vps-dashboard-in-hostinger/) documenta Overview, OS & Panel, Security, Docker Manager y Backups & Monitoring (consultado 2026-10-07).

1. Crear VPS nuevo, seleccionar región y Ubuntu Server 24.04 LTS si está disponible y compatible con Docker/imágenes.
2. Preferir SO limpio para esta ruta. La plantilla Docker/Docker Manager es opcional: puede facilitar administración, pero hay que verificar versiones y acceso a los archivos/build contexts del repositorio.
3. Evitar paneles Apache/Nginx/Caddy adicionales que ocupen puertos o administren certificados sin necesidad.
4. Registrar IP, versión SO y recursos en inventario privado; añadir clave pública SSH y validar huella del servidor por un canal confiable.
5. Preparar usuario operador; mantener sesión/console de rescate hasta verificar una segunda sesión. Restringir y después deshabilitar acceso root por contraseña conforme a política.

**No reinstalar OS/plantilla sobre un VPS con datos para “activar Docker”: puede borrar el servidor.** Tampoco exponer paneles administrativos. La ruta CLI es preferible aquí por trazabilidad de migraciones, locks, secretos y override privado; si se adopta Docker Manager después, debe conservar esos mismos controles.

## 3. Firewall antes de arrancar

En Security → Firewall, crear un grupo, añadir reglas y **activarlo/aplicarlo** al VPS. Conservar acceso de recuperación; confirmar IPv4 e IPv6. El firewall de Hostinger filtra antes del host y su política predeterminada es denegar lo no autorizado. Ver [firewall VPS administrado](https://www.hostinger.com/support/8172641-how-to-use-a-managed-vps-firewall-at-hostinger/) (consultado 2026-10-07).

| Tráfico entrante | Piloto privado por SSH | Futuro público, sólo tras gate |
|---|---|---|
| SSH TCP 22 o puerto configurado | Sólo IP administrativa/VPN, con clave | Mantener restringido |
| HTTP TCP 80 | Cerrado hacia Internet | Sólo Caddy; validar requisitos ACME |
| HTTPS TCP 443 | Cerrado hacia Internet | Sólo Caddy |
| UDP 443 | Cerrado | Opcional para HTTP/3 |
| PostgreSQL 5432 | Cerrado | Cerrado |
| API 8000 / web 3000 | Cerrado | Cerrado |
| S3/filer/master/volume 8333/8888/9333/8080 y AV 3310 | Cerrado | Cerrado |

El host todavía necesita salida para repositorios/imágenes, ACME cuando corresponda, DNS/NTP y firmas AV. No abrir puertos privados para conseguir healthchecks: éstos usan redes Docker internas.

Aplicar también controles del host. Docker puede eludir reglas normales UFW: la defensa inicial incluye **reemplazar los ports públicos por loopback con `!override`** según la guía Linux, además del firewall del proveedor. Ver [advertencia oficial Docker](https://docs.docker.com/engine/network/packet-filtering-firewalls/) (consultado 2026-10-07). Un grupo de firewall sin prueba externa no demuestra aislamiento.

## 4. Desplegar el stack completo, todavía privado

Seguir la guía Linux, sin saltar estas condiciones:

- **Release aprobada:** integrar fixes y obtener SHA publicado con autorización separada; no usar ciegamente `main`, ni un clon sin migraciones nuevas.
- **Docker/Compose:** instalación oficial, versiones registradas, Compose compatible con `!override`; no instalar Node/Python del hosting administrado como sustitutos del build Docker.
- **Archivos:** checkout/paquete aprobado en `/opt/hys-gestion`, `.env` del VPS con permisos 600 y secretos exclusivos. Nunca trasladar `.env` local ni respaldos privados.
- **Origen piloto:** `HYS_DOMAIN=localhost`, `HYS_PUBLIC_ORIGIN=https://localhost:8443`, mismo origen `/api`; no crear aún un DNS público del piloto.
- **Red:** `compose.private.yaml` descrito en Linux, `COMPOSE_FILE` y `COMPOSE_PROJECT_NAME=hys-pilot` conservados en cada sesión.
- **Orden real:** DB healthy → rol `hys_app` → Alembic head → API/S3/AV → web/Caddy. Verificar ambos one-shots exit 0.
- **Seed:** únicamente sobre la base nueva sintética, desde el contenedor `migrate`; nunca reparar una DB real con demo seed.

Desde el equipo autorizado:

```bash
ssh -N -L 127.0.0.1:8443:127.0.0.1:8443 deploy@VPS_IP
```

Abrir `https://localhost:8443`, confiar sólo en la CA pública del Caddy de este VPS después de verificarla por SSH, y ejecutar el smoke en el servidor con el perfil privado. El Caddyfile actual no impone `tls internal`: para localhost usa CA local automáticamente. Un certificado válido no autentica a los usuarios de la aplicación.

### Gate A — piloto en Hostinger

- [ ] Recursos y versiones registrados; sin errores OOM ni disco al límite.
- [ ] Migración/head y servicios healthy; smoke correcto.
- [ ] Ningún servicio del piloto accesible desde Internet sin túnel/VPN, comprobado también por IPv6.
- [ ] Obra sintética creada, recargada y persistida; documento versionado y permisos negativos comprobados.
- [ ] Reinicio controlado conserva datos; puertos y override siguen privados.
- [ ] Se conocen responsable, ventana de mantenimiento y costo operativo.

## 5. Backup y recuperación: dos capas

### Capa proveedor

Consultar Backups & Monitoring → Snapshots & Backups, comprobar calendario/retención reales de la cuenta y costos de backups diarios. La documentación distingue backups programados de snapshots temporales; **no asumir retención ilimitada ni permanente del snapshot**. Restaurar/reinstalar puede reemplazar datos del VPS. [Backups y restore VPS](https://www.hostinger.com/support/1583232-how-to-back-up-or-restore-a-vps-at-hostinger/) (consultado 2026-10-07).

El backup del VPS ayuda ante fallos generales, pero no demuestra consistencia transaccional DB/objetos ni protege de pérdida de cuenta/credenciales. No reemplaza la siguiente capa.

### Capa aplicación — pendiente de implementar

- PostgreSQL: dump consistente, roles/grants y versión Alembic.
- SeaweedFS: objetos **y metadatos del servicio**, con recovery point coordinado; hoy el piloto documenta metadatos de documentos, no carga binaria productiva.
- Configuración/release, manifiestos y digests; secretos/futuras claves de cifrado custodiados aparte. Los volúmenes de Caddy contienen claves privadas.
- Destino externo cifrado, retención, acceso mínimo y alertas; no usar solamente otro directorio del mismo VPS.
- Restore completo en entorno aislado, datos sintéticos, puertos/volúmenes nuevos y comprobación funcional. `scripts/restore_drill.py` no sustituye este proceso.

RPO/RTO, legalidad/residencia del respaldo y responsable deben aprobarse. No habilitar datos reales sin una restauración demostrada. Revertir una aplicación o snapshot exige conocer compatibilidad de esquema y pérdida potencial; nunca hacer downgrade/down-v/prune como recuperación improvisada.

## 6. Dominio/HTTPS público: fase futura bloqueada por seguridad

**No ejecutar esta fase con el piloto actual.** `X-Pilot-Actor` es identidad sintética elegible por el cliente. Mantener el túnel/VPN hasta cerrar el gate productivo de la guía Linux: autenticación/MFA, privacidad/KMS, backup completo, CSP/rate limits, hardening/scanners, CI remoto, UAT y autorización operativa.

Cuando exista aprobación:

1. Elegir subdominio `app.example.com`; DNS A a IPv4 del VPS y AAAA sólo si IPv6/routing/firewall están configurados. No hace falta transferir dominio: editar en el DNS autoritativo.
2. Preparar y revisar **nuevo perfil productivo**, no reutilizar el override loopback cambiando reglas a ciegas. Sólo Caddy publica 80/443; DB/API/web/S3/AV continúan privados.
3. Actualizar dominio y origen exacto; implementar/probar trusted hosts y CORS según topología, pues las variables declaradas en Compose no instalan esos controles hoy. Reconstruir `web` porque el origen se pasa al build. No inventar secretos auth sin su implementación.
4. Comprobar requisitos ACME y certificados; el Caddy actual admite HTTPS automático para dominios elegibles. No instalar otro proxy o SSL de panel encima sin diseñar terminación/forwarding.
5. Verificar `/api` mismo origen, redirects/HSTS, cookies/sesiones, denegación sin login y aislamiento. No activar CDN/cache de datos autenticados sin revisión.
6. Abrir firewall público **sólo después** de estas comprobaciones; monitorear y conservar plan de rollback compatible.

La distinción Hostinger VPS / Cloud hosting es comercial: que un producto diga “Cloud” no significa que admita este Compose. Una migración futura a frontend administrado + API/DB externas requerirá revisar CORS/origen, identidad, secretos, latencia y respaldo; no está implementada en estas hojas de guía.

## 7. Checklist de entrega y siguiente acción

- [ ] VPS y cuenta con acceso administrativo protegido; región/recursos/costo confirmados.
- [ ] SHA/paquete exacto incluye correcciones; secretos excluidos de Git.
- [ ] Piloto desplegado por guía Linux y aislado de Internet.
- [ ] Backup proveedor revisado y plan externo/restore con responsable.
- [ ] Evidencia de salud, persistencia y denegaciones guardada sin datos sensibles.
- [ ] Gates públicos/productivos permanecen abiertos explícitamente; no se anuncia producción.

**Siguiente acción:** aprobar versión, presupuesto y operador; después crear un VPS nuevo para el piloto privado. No contratar ni abrir un dominio público automáticamente.

## Aprendizajes

1. Hostinger ofrece Node.js administrado, pero el stack completo actual requiere control de servidor y servicios adicionales.
2. El VPS aloja la aplicación; su panel no implementa autenticación ni privacidad de negocio.
3. Un snapshot de proveedor y una recuperación coherente de DB/objetos/claves son controles diferentes.
