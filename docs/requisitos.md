# Análisis de requisitos

## Técnicas empleadas

| Técnica | Cómo se aplicó |
|---|---|
| Análisis documental | Lectura del caso de estudio y de los reclamos e incidentes descritos (cierre de campaña de marzo, certificados no generados). |
| Entrevista simulada con los interesados | El equipo representó tres papeles: gerencia de CapacitaPro, administradora de un cliente y colaborador que toma un curso. De cada uno salieron necesidades y prioridades. |
| Historias de usuario | Cada requisito funcional se redactó como «Como… quiero… para…» y se le asignó prioridad MoSCoW. |
| Escenarios de atributos de calidad | Los requisitos no funcionales se expresaron como escenarios medibles (fuente, estímulo, entorno, respuesta y medida), según Bass et al. (2012). |
| Priorización MoSCoW | Must (debe), Should (debería), Could (podría). Lo marcado como «Debe» entra al prototipo. |

## Interesados

| Interesado | Interés principal |
|---|---|
| Gerencia de CapacitaPro | Reducir costo de operación y atender más clientes sin crecer el equipo. |
| Administrador de la empresa cliente | Crear cursos, inscribir colaboradores, ver avance y certificados de su empresa. |
| Colaborador (estudiante) | Tomar el curso desde cualquier dispositivo y obtener su certificado sin demoras. |
| Verificador externo (auditor, contratante) | Confirmar que un certificado es auténtico. |
| Equipo técnico de CapacitaPro | Desplegar y mantener una sola plataforma, por partes. |

## Requisitos funcionales

| ID | Historia de usuario | Prioridad | Caso de uso |
|---|---|---|---|
| RF01 | Como usuario quiero iniciar sesión con correo y clave para acceder a la plataforma de mi empresa. | Debe | CU01 |
| RF02 | Como estudiante quiero ver solo los cursos de mi empresa, con mi avance, para saber qué me falta. | Debe | CU02 |
| RF03 | Como estudiante quiero inscribirme en un curso para que se registre mi avance. | Debe | CU03 |
| RF04 | Como estudiante quiero marcar lecciones como vistas y ver mi porcentaje de avance. | Debe | CU04 |
| RF05 | Como estudiante quiero que al ver la última lección el curso quede completado. | Debe | CU05 |
| RF06 | Como estudiante quiero recibir un certificado en PDF con código único cuando complete un curso. | Debe | CU06, CU07 |
| RF07 | Como estudiante quiero recibir un aviso cuando completo un curso y cuando mi certificado está listo. | Debe | CU08 |
| RF08 | Como verificador externo quiero consultar un certificado por su código, sin cuenta, para confirmar su autenticidad. | Debe | CU09 |
| RF09 | Como administrador quiero crear cursos con sus lecciones para mi empresa. | Debe | CU10 |
| RF10 | Como administrador quiero registrar colaboradores de mi empresa. | Debería | CU11 |
| RF11 | Como administrador quiero ver inscritos, completados y certificados de mi empresa. | Debe | CU12 |
| RF12 | Como administrador quiero cerrar una campaña masiva (muchos participantes a la vez) sin que la plataforma se degrade. | Debe | CU13 |
| RF13 | Como equipo técnico quiero ver en vivo la salud de cada servicio, el estado de sus circuitos y la cola de eventos. | Debería | CU14 |
| RF14 | Como administrador quiero cargar colaboradores desde un archivo. | Podría | — (fuera del prototipo) |

## Requisitos no funcionales (escenarios de calidad)

| ID | Atributo | Escenario | Medida de aceptación | Táctica / patrón |
|---|---|---|---|---|
| RNF01 | Escalabilidad | Un cliente cierra una campaña: 150 colaboradores terminan el curso en el mismo minuto. | La finalización responde en menos de 1 s y todos los certificados se emiten sin errores. | Queue-Based Load Leveling, Competing Consumers, HPA |
| RNF02 | Rendimiento | Un estudiante completa la última lección en operación normal. | Respuesta < 500 ms (p95); certificado disponible en < 10 s. | Procesamiento asíncrono, Outbox |
| RNF03 | Disponibilidad y resiliencia | El servicio de certificados se cae. | Catálogo, cursos y avisos siguen respondiendo; tras 3 fallos el gateway responde en < 100 ms sin esperar al servicio caído. | Circuit Breaker, aislamiento por servicio |
| RNF04 | Confiabilidad de mensajes | Redis o el trabajador de certificados no está disponible cuando un curso se completa. | Ningún certificado se pierde: se emite cuando el componente vuelve, y un evento repetido no genera duplicados. | Transactional Outbox, ACK tras procesar, idempotencia |
| RNF05 | Seguridad y privacidad (Ley 1581) | Un usuario de la empresa A intenta leer datos de la empresa B o falsificar su rol. | Respuesta 404/403; las cabeceras de identidad del cliente se descartan; claves con bcrypt; servicios internos no expuestos. | Gateway Offloading, NetworkPolicy, filtro por empresa en el repositorio |
| RNF06 | Equidad entre inquilinos | Un cliente genera ráfagas de solicitudes. | Por encima de 20 solicitudes/s (ráfaga de 40) recibe 429; los demás clientes no se afectan. | Rate limiting por empresa |
| RNF07 | Mantenibilidad / modificabilidad | Se cambia la forma de enviar avisos (correo real). | El cambio toca solo el servicio de notificaciones; ningún otro servicio se recompila. | Publisher/Subscriber, bajo acoplamiento |
| RNF08 | Desplegabilidad | Se publica una nueva versión de un servicio. | Se despliega ese servicio solo, sin detener los demás. | Microservicios, contenedores, Kubernetes |
| RNF09 | Costo | Operación del piloto. | Infraestructura dentro de la capa Always Free de OCI. | K3s en nodos Ampere A1 |
| RNF10 | Observabilidad | Una solicitud falla en un servicio interno. | Se puede seguir con el identificador de correlación en los registros de cada servicio. | Correlation ID, Health Endpoint Monitoring |

## Trazabilidad requisito → componente

| Requisito | Gateway | Identidad | Cursos | Certificados | Notificaciones |
|---|:-:|:-:|:-:|:-:|:-:|
| RF01 | ● | ● | | | |
| RF02–RF05 | ● | | ● | | |
| RF06, RF08 | ● | | | ● | |
| RF07 | | | | | ● |
| RF09, RF11 | ● | | ● | ● | |
| RF10 | ● | ● | | | |
| RF12 | ● | | ● | ● | ● |
| RF13 | ● | | | ● | |
| RNF01, RNF04 | | | ● | ● | ● |
| RNF03, RNF06 | ● | | | | |
| RNF05 | ● | ● | ● | ● | ● |
