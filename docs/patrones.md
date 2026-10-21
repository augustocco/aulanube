# Patrones de diseño seleccionados

Los patrones se escogieron a partir de los escenarios de calidad de [requisitos.md](requisitos.md). Para cada uno se indica qué problema del caso resuelve, dónde está en el código y qué costo se acepta.

## Estilo arquitectónico

**Microservicios con comunicación híbrida**: REST síncrono para las consultas del usuario y eventos asíncronos para los procesos que pueden ocurrir después (certificado, aviso). Se descartó un monolito modular porque el caso exige escalar y aislar fallos **por partes** (RNF01, RNF03, RNF08): la emisión de certificados necesita varias réplicas en un cierre de campaña, mientras identidad no. Se descartó también una arquitectura totalmente orientada a eventos porque las consultas del estudiante necesitan respuesta inmediata.

## Patrones de nube

| Patrón | Problema del caso | Implementación | Costo aceptado |
|---|---|---|---|
| **API Gateway** | El navegador no debe conocer ni alcanzar los servicios internos. | `servicios/gateway/app/main.py`: única ruta `/api/{servicio}/...` | Un salto de red más; el gateway corre con 2 réplicas para no ser punto único de falla. |
| **Gateway Offloading** | Validar el token, limitar solicitudes y correlacionar trazas en cada servicio duplicaría código. | El gateway valida el JWT, borra las cabeceras de identidad del cliente y reenvía `X-Usuario-*`, `X-Empresa-*`, `X-Rol`. | Los servicios confían en el gateway; se compensa con NetworkPolicy. |
| **Database per Service** | Con una base compartida, un cambio de esquema de cursos podría romper certificados (alto acoplamiento). | Una base y un usuario por servicio (`infra/postgres/crear-bases.sh`); ningún servicio lee tablas ajenas. | Consultas entre dominios por API o eventos; en el piloto las cuatro bases comparten instancia de PostgreSQL. |
| **Publisher / Subscriber** | Cursos no debe saber quién reacciona cuando un curso termina (hoy certificados y avisos, mañana facturación o analítica). | Redis Streams con un flujo por publicador (`aulanube.cursos`, `aulanube.certificados`); cada servicio suscrito tiene su grupo de consumidores y solo lee los flujos que le interesan. | Consistencia eventual: el certificado aparece segundos después. |
| **Transactional Outbox** | Si Redis falla justo después de guardar el curso completado, el evento se perdería (RNF04). | `cursos/app/modelos.py` (`EventoSalida`) y `cursos/app/relevo.py`: el evento se guarda en la misma transacción y un hilo lo publica. | Entrega «al menos una vez»: los consumidores deben ser idempotentes. |
| **Queue-Based Load Leveling** | El cierre de campaña generaba picos que tumbaban el servidor (RNF01). | `POST /campanas` responde 202 al instante; la cola absorbe el pico y los trabajadores la vacían a su ritmo. | El usuario no recibe el certificado en la misma respuesta. |
| **Competing Consumers** | Un solo trabajador tardaría demasiado con cientos de certificados. | Varias réplicas de certificados en el mismo grupo; Redis entrega cada evento a una sola. HPA de 2 a 4 réplicas. | Orden de procesamiento no garantizado entre réplicas (no se necesita). |
| **Circuit Breaker** | Un servicio caído hacía esperar cada solicitud hasta agotar el tiempo y arrastraba al resto (RNF03). | `gateway/app/interruptor.py`: tras 3 fallos seguidos se abre 15 s, luego deja pasar una prueba (semiabierto). | Durante 15 s se rechazan solicitudes aunque el servicio ya se haya recuperado. |
| **Retry** | Fallos de red transitorios entre pods. | El gateway reintenta una vez las lecturas (GET), que son idempotentes. | Latencia extra en el caso de fallo. |
| **Health Endpoint Monitoring** | Kubernetes y el panel necesitan saber si cada servicio está vivo. | `/salud` en cada servicio, sondas `readiness` y `liveness`, panel `/api/estado`. | — |
| **External Configuration Store** | Credenciales y direcciones distintas entre local y nube. | Variables de entorno desde Secrets de Kubernetes o `.env`. | — |
| **Dead Letter (eventos fallidos)** | Un evento malformado no debe bloquear la cola para siempre. | Tras 3 intentos se aparta en `aulanube.fallidos`. | Requiere revisión manual de esos eventos. |

## Patrones de diseño de bajo nivel

| Patrón | Dónde | Por qué |
|---|---|---|
| **Repository** | `cursos/app/repositorio.py` | Separa la lógica de negocio del acceso a datos e impone el filtro por empresa en un solo lugar (aislamiento entre inquilinos, RNF05). |
| **Value Object** | `Contexto` en `*/app/contexto.py` | Identidad inmutable del usuario que viaja por la solicitud. |
| **Idempotent Receiver** | Restricciones únicas `inscripcion_id` (certificados) y `evento_id` (notificaciones) | Hace segura la entrega «al menos una vez». |
| **Token Bucket** | `gateway/app/limitador.py` | Límite de solicitudes por empresa con ráfagas permitidas (RNF06). |

## Relación con los principios de la Unidad 1

- **Alta cohesión**: cada servicio agrupa un solo concepto del dominio (identidad, cursos, certificados, avisos).
- **Bajo acoplamiento**: los servicios no se llaman entre sí; se comunican por eventos con un contrato pequeño (`tipo`, `evento_id`, `datos`).
- **Ocultamiento de información** (Parnas, 1972): cada base de datos es un detalle interno de su servicio; cambiar cómo se guarda un certificado (por ejemplo, pasar el PDF a Object Storage) no afecta a nadie más.
- **Separación de responsabilidades**: el gateway resuelve los asuntos transversales; los servicios, solo su dominio.
