# Entorno de desarrollo y VM

## Topología requerida

Desarrollo/integración debe ejecutarse en Linux con Docker Engine y Compose. El
despliegue objetivo usa una VM Ubuntu Server LTS en Hyper-V, 8 vCPU, 24 GB RAM y
1 TB cifrado. Un único ambiente productivo permanente se complementa con stacks
efímeros de CI.

## Diagnóstico de la estación actual (2026-08-27)

| Recurso | Detectado | Requerido/impacto |
|---|---:|---|
| Windows | 10 Pro 10.0.19045 | no es el host Windows Server objetivo |
| CPU lógica | 4 | no puede asignar 8 vCPU a la VM |
| RAM | 7,9 GB | no puede asignar 24 GB |
| disco C | 446,5 GB total / 369 GB libre | no dispone de 1 TB |
| virtualización firmware | deshabilitada | Hyper-V/WSL2/Docker Linux bloqueados |
| Git | ausente | no permite repo/commits locales |
| Docker | ausente | no permite Compose/smoke |
| Node/npm | ausentes | no permite lock/build web |
| Python/uv | alias Store/no runtime | no permite lock/tests API |

Conclusión: esta estación permite editar artefactos pero no certificar los gates.
El 2026-09-02 la persona solicitante eligió la opción A: usar otro servidor/VM
compatible y conservar el baseline. Por ello no se instalarán herramientas del
sistema ni se cambiará BIOS/Windows en esta estación como sustituto del entorno.
Toolchains portables servirían para lint unitario, pero no prueban la arquitectura
Linux/PostgreSQL/S3/AV ni sustituyen el gate.

## Aprovisionamiento aprobado, ejecución pendiente

1. Confirmar host con virtualización, recursos y almacenamiento cifrado.
2. Crear switch/red y VM Ubuntu Server LTS con Secure Boot/TPM cuando aplique.
3. Aplicar parches, zona UTC, NTP, firewall y usuario administrador nominal.
4. Instalar Docker Engine/Compose desde repositorio oficial; fijar versiones.
5. Configurar volúmenes cifrados, directorios y cuotas; sólo 80/443 expuestos.
6. Crear deploy user de mínimo privilegio y acceso SSH por clave/MFA/bastion según
   política; deshabilitar password/root remoto.
7. Vincular GitHub/GHCR privado y secretos protegidos.
8. Desplegar stack sintético, migrar DB vacía y ejecutar smoke.
9. Configurar backup externo, métricas, logs y alertas.
10. Ejecutar y firmar restore de prueba antes de autorizar datos reales.

## Evidencia para cerrar gates

- inventario de host/VM sin seriales o secretos en repo;
- versiones/digests de SO, Docker y Compose;
- `docker compose config` y listado de puertos/redes;
- salida CI de locks, tests, migración empty/previous y smoke;
- health live/ready y schema version;
- prueba de que DB/S3/AV no son alcanzables desde Internet;
- backup/restore con hashes y tiempos;
- aprobación de owner operativo.

## Desarrollo diario previsto

1. copiar `.env.example` a `.env` y generar secretos locales;
2. `docker compose build` con locks;
3. `docker compose up db seaweedfs clamav`;
4. `docker compose run --rm migrate`;
5. levantar API/web/worker;
6. ejecutar tests/smoke y poblar sólo seed sintético;
7. purgar stack/volúmenes únicamente con comando explícito y confirmación.

Los comandos exactos se materializan en Hito 1 y se validan en el entorno real.
