# Caso de estudio: CapacitaPro S.A.S.

> Empresa ficticia creada por el equipo para la actividad. Los nombres de clientes, personas y cifras son inventados.

## La empresa

CapacitaPro S.A.S. es una empresa de Bucaramanga, fundada en 2017, que diseña y administra **capacitación virtual para otras empresas**. Su negocio son los cursos que la ley o los contratos hacen obligatorios: inducción al Sistema de Gestión de Seguridad y Salud en el Trabajo (SG-SST), trabajo seguro en alturas, protección de datos personales (Ley 1581 de 2012) y atención al usuario en salud. Tiene 38 empresas cliente, desde constructoras de 80 trabajadores hasta una red de clínicas con 2.600 colaboradores, y unos 14.000 usuarios activos.

## Situación actual

Cada cliente nuevo recibe **su propia instalación de WordPress con un plugin de LMS** en un servidor virtual alquilado. Hoy hay 38 instalaciones repartidas en cinco servidores. Este modelo funcionó con los primeros diez clientes, pero ya muestra sus límites:

| Problema | Evidencia |
|---|---|
| **Picos de carga en los cierres de campaña.** Cuando un cliente fija una fecha límite, cientos de trabajadores terminan el curso el mismo día. | En marzo, el cierre de la campaña de alturas de una constructora (1.100 trabajadores) dejó el servidor sin respuesta durante 40 minutos y afectó a los otros siete clientes alojados en la misma máquina. |
| **El certificado se genera dentro de la solicitud.** El PDF se arma mientras el usuario espera. | Tiempos de respuesta de 8 a 25 s al terminar un curso en horas pico; algunos usuarios cierran la página y el certificado nunca se genera. |
| **El correo de aviso bloquea la operación.** Si el servidor de correo tarda, falla la finalización del curso. | Doce reclamos en el último trimestre por cursos «terminados» que no aparecen como completados. |
| **Mantenimiento multiplicado.** Una actualización de seguridad o un ajuste de diseño se aplica 38 veces. | Dos personas del equipo técnico dedican cerca del 40 % de su tiempo a actualizaciones. |
| **Sin verificación de certificados.** Las empresas y los auditores del Ministerio del Trabajo piden confirmar que un certificado es auténtico. | Hoy se verifica por correo y tarda días. |
| **Datos dispersos.** No hay un panorama de avance por cliente. | Los informes se arman a mano en hojas de cálculo. |

## Lo que pide la gerencia

1. Una **sola plataforma multiempresa** en la nube, donde cada cliente vea solo sus cursos, sus colaboradores y sus certificados.
2. Que un cierre de campaña de un cliente **no afecte a los demás** ni haga esperar al usuario.
3. Certificados con **código verificable** por terceros, sin intervención del equipo.
4. Que la caída de una parte (por ejemplo, la generación de certificados o el correo) **no detenga** el resto de la plataforma.
5. Poder **crecer por partes**: agregar capacidad solo donde hace falta.
6. **Costo de infraestructura bajo** durante el piloto, idealmente en la capa gratuita de un proveedor de nube.
7. Cumplir la **Ley 1581 de 2012**: datos personales aislados por cliente, contraseñas cifradas y acceso solo para personal autorizado.

## Alcance del prototipo

El equipo de arquitectura propone **AulaNube** y construye un prototipo con el flujo central: ingreso, catálogo por empresa, avance de lecciones, finalización, emisión asíncrona del certificado, avisos, verificación pública, gestión básica de la empresa y un panel para observar la arquitectura. Quedan fuera del prototipo los pagos, la facturación, el contenido multimedia y la integración con el correo real.
