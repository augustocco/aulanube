# AulaNube

Prototipo de la actividad **«Orquestando Códigos: La Sinfonía de los Sistemas»** (Arquitectura de Software, Unidad 1, Tecnológica del Oriente).

AulaNube es la plataforma de capacitación corporativa multiempresa que propone el equipo para **CapacitaPro S.A.S.**, una empresa ficticia que vende cursos virtuales obligatorios (SG-SST, trabajo en alturas, protección de datos) a otras empresas. La arquitectura combina **microservicios**, un **API Gateway** y **eventos asíncronos** sobre Redis Streams, y se despliega en **Oracle Cloud Infrastructure** sobre un clúster K3s de nodos Ampere A1 (capa Always Free).

- Aplicación en la nube: **https://aulanube.149-130-191-139.sslip.io**
- Caso de estudio y requisitos: [docs/caso-de-estudio.md](docs/caso-de-estudio.md), [docs/requisitos.md](docs/requisitos.md)
- Diagramas UML (fuente PlantUML e imágenes): [docs/uml/](docs/uml/)
- Patrones de diseño y su justificación: [docs/patrones.md](docs/patrones.md)
- Informe técnico y presentación: [docs/informe/](docs/informe/), [docs/presentacion/](docs/presentacion/)

## Arquitectura

```
navegador ─HTTPS─► Traefik ─► web (nginx) ─/api─► API Gateway ─┬─► identidad ──────► BD identidad
                                                    JWT, límite ├─► cursos ─────────► BD cursos
                                                    por empresa,├─► certificados ───► BD certificados
                                                    circuitos   └─► notificaciones ─► BD notificaciones
                                                                        ▲  ▲
  cursos ──(outbox)── XADD ──► aulanube.cursos ────────► grupos «certificados» y «notificaciones»
  certificados ─────── XADD ──► aulanube.certificados ──► grupo «notificaciones»
```

| Componente | Responsabilidad | Tecnología |
|---|---|---|
| `web` | Interfaz de una sola página; envía `/api` al gateway | nginx sin privilegios, JavaScript sin dependencias |
| `gateway` | Única entrada: valida el JWT, reenvía la identidad, limita solicitudes por empresa, circuit breaker y reintentos | FastAPI, httpx |
| `identidad` | Empresas (inquilinos), usuarios, ingreso y emisión de tokens | FastAPI, SQLAlchemy, bcrypt, PyJWT |
| `cursos` | Catálogo por empresa, inscripciones, progreso; publica `curso.completado` con bandeja de salida | FastAPI, SQLAlchemy, Redis |
| `certificados` | Trabajadores que consumen la cola, generan el PDF y publican `certificado.emitido`; verificación pública | FastAPI, ReportLab, Redis |
| `notificaciones` | Suscriptor de ambos eventos: avisos en la plataforma y correo simulado | FastAPI, Redis |
| `postgres` | Una base y un usuario por servicio | PostgreSQL 16 |
| `redis` | Flujos `aulanube.cursos` y `aulanube.certificados` (uno por publicador) con grupos de consumidores | Redis 7.4 (AOF) |

Patrones aplicados: API Gateway, Gateway Offloading, Database per Service, Publisher/Subscriber, Transactional Outbox, Competing Consumers, Queue-Based Load Leveling, Circuit Breaker, Retry, Health Endpoint Monitoring, Repository y External Configuration Store. El detalle está en [docs/patrones.md](docs/patrones.md).

## Ejecución local

Requisitos: Docker Desktop con Compose v2.

```bash
cd infra
docker compose up -d --build
```

Abra http://localhost:8080. Cuentas de demostración, todas con la clave `AulaNube-2026`:

| Cuenta | Rol | Empresa |
|---|---|---|
| `carlos@andes.demo` | Estudiante | Constructora Los Andes S.A.S. |
| `admin@andes.demo` | Administradora | Constructora Los Andes S.A.S. |
| `andres@santalucia.demo` | Estudiante | Clínica Santa Lucía |
| `admin@santalucia.demo` | Administradora | Clínica Santa Lucía |

Para cambiar credenciales copie `infra/.env.ejemplo` como `infra/.env`.

```bash
docker compose down        # detiene y conserva los datos
docker compose down -v     # detiene y borra PostgreSQL y Redis
```

## Pruebas

Cada servicio tiene sus pruebas (28 en total) y se ejecutan en la etapa `pruebas` de su Dockerfile, con SQLite en memoria y Redis simulado:

```bash
docker build --target pruebas -t aulanube/cursos:pruebas servicios/cursos
docker run --rm aulanube/cursos:pruebas
```

La prueba de humo recorre el flujo completo contra un despliegue real (ingreso, curso completado, certificado, aviso, verificación y una campaña de 40 participantes):

```bash
python scripts/prueba_humo.py                                       # local
python scripts/prueba_humo.py https://aulanube.149-130-191-139.sslip.io   # nube
```

## Demostración de los patrones

| Qué mostrar | Cómo |
|---|---|
| Nivelación de carga y consumidores en competencia | Ingrese como administradora → **Gestión** → «Simular cierre de campaña» con 150 participantes. La respuesta es inmediata y en **Arquitectura** se ve la cola subir y bajar; en **Certificados** la columna «Trabajador» muestra qué réplica emitió cada uno. |
| Circuit breaker y aislamiento de fallos | `kubectl -n aulanube scale deploy certificados --replicas=0`. Tras tres fallos el circuito de certificados se abre (respuesta en milisegundos, cabecera `X-Circuito: abierto`) y los cursos siguen funcionando. Al volver a escalar, el circuito pasa a semiabierto y se cierra. |
| Entrega garantizada | Con certificados apagado complete un curso: el evento espera en Redis y el certificado se emite apenas vuelve el servicio. |
| Aislamiento entre empresas | Ingrese con las dos empresas: cada una ve solo su catálogo, sus colaboradores y sus certificados. |

## Despliegue en OCI

Infraestructura: dos instancias `VM.Standard.A1.Flex` (1 OCPU y 6 GB, arm64) en `sa-bogota-1` con K3s; Traefik viene con K3s y emite el certificado de Let's Encrypt. AulaNube vive en su propio namespace, `aulanube`.

```bash
# 1. Secretos (el archivo real está excluido del repositorio)
cp infra/k8s/00-namespace-secretos.ejemplo.yaml infra/k8s/00-namespace-secretos.yaml

# 2. Imágenes arm64, importadas en cada nodo (no se usa registro)
for s in gateway identidad cursos certificados notificaciones; do
  docker buildx build --platform linux/arm64 -t aulanube/$s:v1 --load servicios/$s
done
docker buildx build --platform linux/arm64 -t aulanube/web:v1 --load web
for ip in <IP_NODO_1> <IP_NODO_2>; do
  docker save aulanube/{gateway,identidad,cursos,certificados,notificaciones,web}:v1 \
    | ssh ubuntu@$ip "sudo k3s ctr -n k8s.io images import -"
done

# 3. Manifiestos
kubectl apply -f infra/k8s/00-namespace-secretos.yaml
kubectl apply -f infra/k8s/01-datos.yaml
kubectl apply -f infra/k8s/02-servicios.yaml
kubectl apply -f infra/k8s/03-web-ingress.yaml
kubectl apply -f infra/k8s/04-politicas-red.yaml
```

## Estructura

```
servicios/gateway         API Gateway (FastAPI)
servicios/identidad       Empresas, usuarios y tokens
servicios/cursos          Catálogo, inscripciones, progreso y bandeja de salida
servicios/certificados    Trabajadores de la cola, PDF y verificación pública
servicios/notificaciones  Suscriptor de eventos y avisos
web                       Interfaz (nginx + JavaScript)
infra                     Docker Compose y manifiestos de Kubernetes
scripts                   Prueba de humo de punta a punta
docs                      Caso de estudio, requisitos, UML, patrones, informe y presentación
```

Cada servicio es independiente: tiene su `requirements.txt`, su Dockerfile y sus pruebas. El código común (conexión a la base, contexto de identidad, consumidor de eventos) se copia en cada servicio en lugar de compartirse como librería, para que ninguno dependa del ciclo de versiones de otro.
