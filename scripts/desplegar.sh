#!/usr/bin/env bash
# Despliega AulaNube en el clúster K3s de OCI.
#
#   scripts/desplegar.sh                   # todos los componentes
#   scripts/desplegar.sh gateway web       # solo los indicados
#
# Las imágenes se construyen de forma nativa en el nodo 1 (arm64), se copian
# al nodo 2 y se importan en containerd de K3s; no se usa registro. Después se
# aplican los manifiestos y se reinician los Deployments reconstruidos.
set -euo pipefail

NODO1="${NODO1:-ubuntu@149.130.191.139}"
NODO2="${NODO2:-ubuntu@157.137.224.145}"
LLAVE="${LLAVE:-$HOME/.ssh/id_rsa}"
ETIQUETA="${ETIQUETA:-v1}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
COMPONENTES=("${@:-gateway identidad cursos certificados notificaciones web}")
read -r -a COMPONENTES <<< "${COMPONENTES[*]}"

ssh1() { ssh -i "$LLAVE" "$NODO1" "$@"; }
ssh2() { ssh -i "$LLAVE" "$NODO2" "$@"; }

echo "→ Copiando el código al nodo 1"
tar -C "$RAIZ" --exclude='__pycache__' --exclude='.pytest_cache' -czf - servicios web \
  | ssh1 "rm -rf ~/aulanube-build && mkdir -p ~/aulanube-build && tar -xzf - -C ~/aulanube-build"

imagenes=()
for c in "${COMPONENTES[@]}"; do
  ruta="servicios/$c"; [ "$c" = web ] && ruta=web
  echo "→ Construyendo aulanube/$c:$ETIQUETA (arm64 nativo)"
  ssh1 "cd ~/aulanube-build && sudo docker build -q -t aulanube/$c:$ETIQUETA $ruta >/dev/null"
  imagenes+=("aulanube/$c:$ETIQUETA")
done

echo "→ Importando en containerd de ambos nodos"
ssh1 "sudo docker save ${imagenes[*]} | sudo k3s ctr -n k8s.io images import - >/dev/null"
ssh1 "sudo docker save ${imagenes[*]}" | ssh2 "sudo k3s ctr -n k8s.io images import - >/dev/null"

echo "→ Aplicando manifiestos"
for f in 00-namespace-secretos 01-datos 02-servicios 03-web-ingress 04-politicas-red; do
  ssh1 "sudo k3s kubectl apply -f -" < "$RAIZ/infra/k8s/$f.yaml" >/dev/null
done

for c in "${COMPONENTES[@]}"; do
  ssh1 "sudo k3s kubectl -n aulanube rollout restart deploy/$c >/dev/null && sudo k3s kubectl -n aulanube rollout status deploy/$c --timeout=180s"
done
ssh1 "sudo k3s kubectl -n aulanube get pods -o wide"
