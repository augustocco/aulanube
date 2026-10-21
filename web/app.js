"use strict";

/* AulaNube: interfaz de una sola página. Todo pasa por /api, que nginx envía al gateway. */

const sesion = {
  get token() { try { return sessionStorage.getItem("aulanube.token"); } catch { return null; } },
  get usuario() { try { return JSON.parse(sessionStorage.getItem("aulanube.usuario") || "null"); } catch { return null; } },
  guardar(token, usuario) {
    try {
      sessionStorage.setItem("aulanube.token", token);
      sessionStorage.setItem("aulanube.usuario", JSON.stringify(usuario));
    } catch { /* sin almacenamiento: la sesión dura lo que la pestaña */ }
    memoria = { token, usuario };
  },
  cerrar() {
    try { sessionStorage.clear(); } catch { /* nada */ }
    memoria = null;
  },
};
let memoria = null;
const token = () => sesion.token || memoria?.token;
const usuario = () => sesion.usuario || memoria?.usuario;
const esAdmin = () => usuario()?.rol === "admin";

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const vista = $("#vista");
let temporizador = null;

function esc(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fecha(iso) {
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

function avisar(texto, error = false) {
  const el = $("#aviso");
  el.textContent = texto;
  el.classList.toggle("error", error);
  el.classList.add("visible");
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => el.classList.remove("visible"), 3500);
}

class ErrorApi extends Error {
  constructor(estado, mensaje) { super(mensaje); this.estado = estado; }
}

async function api(ruta, { metodo = "GET", cuerpo, crudo = false } = {}) {
  const cabeceras = {};
  if (token()) cabeceras.Authorization = `Bearer ${token()}`;
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  const r = await fetch(`/api/${ruta}`, { method: metodo, headers: cabeceras, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
  if (r.status === 401 && token()) {
    sesion.cerrar();
    location.hash = "#/ingresar";
    throw new ErrorApi(401, "Su sesión terminó, ingrese de nuevo");
  }
  if (!r.ok) {
    let mensaje = `Error ${r.status}`;
    try {
      const datos = await r.json();
      mensaje = typeof datos.detalle === "string" ? datos.detalle
        : typeof datos.detail === "string" ? datos.detail
        : Array.isArray(datos.detail) ? "Revise los datos del formulario" : mensaje;
    } catch { /* respuesta sin JSON */ }
    throw new ErrorApi(r.status, mensaje);
  }
  return crudo ? r : r.json();
}

/* Navegación ------------------------------------------------------------- */

const rutas = [
  [/^#\/ingresar$/, vistaIngreso, false],
  [/^#\/verificar(?:\/([\w-]+))?$/, vistaVerificar, false],
  [/^#\/cursos$/, vistaCursos, true],
  [/^#\/curso\/(\d+)$/, vistaCurso, true],
  [/^#\/certificados$/, vistaCertificados, true],
  [/^#\/notificaciones$/, vistaNotificaciones, true],
  [/^#\/gestion$/, vistaGestion, true],
  [/^#\/arquitectura$/, vistaArquitectura, true],
];

async function navegar() {
  clearInterval(temporizador);
  const hash = location.hash || (token() ? "#/cursos" : "#/ingresar");
  const ruta = rutas.find(([patron]) => patron.test(hash));
  if (!ruta) { location.hash = token() ? "#/cursos" : "#/ingresar"; return; }
  const [patron, render, privada] = ruta;
  if (privada && !token()) { location.hash = "#/ingresar"; return; }
  pintarBarra(hash);
  vista.classList.remove("sin-margen");
  try {
    await render(...(hash.match(patron).slice(1)));
  } catch (e) {
    vista.innerHTML = `<div class="tarjeta vacio"><h2>No se pudo cargar</h2><p>${esc(e.message)}</p></div>`;
  }
  vista.focus({ preventScroll: true });
}

function pintarBarra(hash) {
  const u = usuario();
  const barra = $("#barra");
  barra.hidden = !u || hash.startsWith("#/ingresar");
  if (barra.hidden) return;
  const enlaces = [["#/cursos", "Cursos"], ["#/certificados", "Certificados"], ["#/notificaciones", 'Avisos <span class="insignia" id="sin-leer" hidden></span>']];
  if (u.rol === "admin") enlaces.push(["#/gestion", "Gestión"], ["#/arquitectura", "Arquitectura"]);
  $("#menu").innerHTML = enlaces.map(([h, t]) => `<a href="${h}" class="${hash.startsWith(h) || (h === "#/cursos" && hash.startsWith("#/curso/")) ? "activo" : ""}">${t}</a>`).join("");
  $("#empresa").innerHTML = `${esc(u.nombre)} · <strong>${esc(u.empresa)}</strong>`;
  actualizarInsignia();
}

async function actualizarInsignia() {
  try {
    const { sin_leer } = await api("notificaciones/notificaciones");
    const el = $("#sin-leer");
    if (el) { el.hidden = !sin_leer; el.textContent = sin_leer; }
  } catch { /* el servicio de avisos puede estar caído: la página sigue funcionando */ }
}

$("#salir").addEventListener("click", () => { sesion.cerrar(); location.hash = "#/ingresar"; });
window.addEventListener("hashchange", navegar);

/* Ingreso ----------------------------------------------------------------- */

const CUENTAS_DEMO = [
  ["carlos@andes.demo", "Carlos Rincón", "Estudiante · Constructora Los Andes"],
  ["admin@andes.demo", "Laura Méndez", "Administradora · Constructora Los Andes"],
  ["andres@santalucia.demo", "Andrés Pabón", "Estudiante · Clínica Santa Lucía"],
  ["admin@santalucia.demo", "Diana Ortiz", "Administradora · Clínica Santa Lucía"],
];

function vistaIngreso() {
  vista.classList.add("sin-margen");
  vista.innerHTML = `
    <div class="ingreso">
      <section class="ingreso-portada">
        <div>
          <div class="marca"><img src="icono.svg" alt="" width="32" height="32"><span>AulaNube</span></div>
        </div>
        <div>
          <h1>Capacitación corporativa que escala con cada cliente</h1>
          <p>CapacitaPro S.A.S. atiende a sus empresas cliente desde una sola plataforma en la nube, con datos aislados por empresa.</p>
          <ul>
            <li>Cursos y progreso por empresa</li>
            <li>Certificados emitidos en segundo plano, con código verificable</li>
            <li>Avisos al terminar cada curso</li>
          </ul>
        </div>
        <p class="ayuda" style="color:#9fbcbc">Prototipo académico · Arquitectura de Software · Tecnológica del Oriente</p>
      </section>
      <section class="ingreso-formulario">
        <div class="tarjeta">
          <h2>Ingresar</h2>
          <form class="pila" id="form-ingreso">
            <label>Correo <input name="correo" type="email" autocomplete="username" required></label>
            <label>Clave <input name="clave" type="password" autocomplete="current-password" required></label>
            <p class="error" id="error-ingreso"></p>
            <button class="boton" type="submit">Ingresar</button>
          </form>
          <div class="demo">
            <span class="ayuda">Cuentas de demostración (clave <code>AulaNube-2026</code>):</span>
            ${CUENTAS_DEMO.map(([c, n, d]) => `<button type="button" data-correo="${c}">${esc(n)}<br><small>${esc(d)}</small></button>`).join("")}
          </div>
          <p class="ayuda" style="margin-top:1rem">¿Recibió un certificado? <a href="#/verificar">Verifique su autenticidad</a>.</p>
        </div>
      </section>
    </div>`;
  const form = $("#form-ingreso");
  vista.querySelectorAll("[data-correo]").forEach((b) => b.addEventListener("click", () => {
    form.correo.value = b.dataset.correo;
    form.clave.value = "AulaNube-2026";
    form.requestSubmit();
  }));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const boton = form.querySelector("button[type=submit]");
    boton.disabled = true;
    try {
      const r = await api("identidad/login", { metodo: "POST", cuerpo: { correo: form.correo.value, clave: form.clave.value } });
      sesion.guardar(r.token, r.usuario);
      vista.classList.remove("sin-margen");
      location.hash = "#/cursos";
    } catch (e) {
      $("#error-ingreso").textContent = e.message;
    } finally {
      boton.disabled = false;
    }
  });
}

/* Cursos ------------------------------------------------------------------ */

function etiquetaEstado(i) {
  if (!i) return '<span class="etiqueta gris">Sin inscribir</span>';
  if (i.estado === "completado") return '<span class="etiqueta">Completado</span>';
  return `<span class="etiqueta ambar">En curso · ${i.progreso}%</span>`;
}

async function vistaCursos() {
  vista.classList.remove("sin-margen");
  const cursos = await api("cursos/cursos");
  const admin = esAdmin();
  vista.innerHTML = `
    <div class="encabezado">
      <div><h1>Cursos de ${esc(usuario().empresa)}</h1>
      <p>${admin ? "Catálogo de la empresa con el avance de sus colaboradores." : "Inscríbase, avance por las lecciones y obtenga su certificado."}</p></div>
      ${admin ? '<a class="boton" href="#/gestion">Crear curso</a>' : ""}
    </div>
    <div class="rejilla">
      ${cursos.map((c) => `
        <article class="tarjeta curso">
          <div class="meta"><span>${c.horas} h</span><span>${c.lecciones} lecciones</span></div>
          <h2>${esc(c.titulo)}</h2>
          <p>${esc(c.descripcion)}</p>
          ${admin
            ? `<div class="meta"><span><strong>${c.inscritos.total}</strong> inscritos</span><span><strong>${c.inscritos.completados}</strong> completados</span></div>`
            : `${etiquetaEstado(c.inscripcion)}<div class="progreso"><span style="width:${c.inscripcion?.progreso ?? 0}%"></span></div>`}
          <a class="boton ${c.inscripcion ? "secundario" : ""}" href="#/curso/${c.id}">${admin ? "Ver contenido" : c.inscripcion ? (c.inscripcion.estado === "completado" ? "Repasar" : "Continuar") : "Ver curso"}</a>
        </article>`).join("") || '<p class="vacio">Esta empresa aún no tiene cursos.</p>'}
    </div>`;
}

async function vistaCurso(id, leccionActual) {
  const curso = await api(`cursos/cursos/${id}`);
  const insc = curso.inscripcion;
  const actual = curso.lecciones.find((l) => String(l.id) === String(leccionActual))
    || curso.lecciones.find((l) => !l.vista) || curso.lecciones[0];
  const admin = esAdmin();

  vista.innerHTML = `
    <p><a href="#/cursos">← Volver a cursos</a></p>
    <div class="encabezado">
      <div><h1>${esc(curso.titulo)}</h1><p>${esc(curso.descripcion)}</p></div>
      ${insc ? etiquetaEstado(insc) : ""}
    </div>
    ${insc?.estado === "completado" ? `<div class="banda"><strong>Curso completado.</strong> Su certificado se genera en segundo plano; lo verá en <a href="#/certificados">Certificados</a> en unos segundos.</div>` : ""}
    ${!insc && !admin ? `<div class="banda ambar fila" style="justify-content:space-between;align-items:center"><span>Inscríbase para registrar su avance.</span><button class="boton" id="inscribirme">Inscribirme</button></div>` : ""}
    <div class="columna-lateral">
      <aside class="tarjeta">
        <h3>Lecciones</h3>
        ${insc ? `<div class="progreso" style="margin:.5rem 0 1rem"><span style="width:${insc.progreso}%"></span></div>` : ""}
        <ol class="lecciones">
          ${curso.lecciones.map((l) => `<li><button data-leccion="${l.id}" class="${l.id === actual.id ? "actual" : ""}">
            <span class="marca-leccion ${l.vista ? "hecha" : ""}">${l.vista ? "✓" : l.orden}</span>${esc(l.titulo)}</button></li>`).join("")}
        </ol>
      </aside>
      <article class="tarjeta">
        <span class="ayuda">Lección ${actual.orden} de ${curso.lecciones.length}</span>
        <h2>${esc(actual.titulo)}</h2>
        <div class="contenido-leccion"><p>${esc(actual.contenido || "Sin contenido.")}</p></div>
        ${insc && insc.estado !== "completado" && !actual.vista ? '<button class="boton" id="completar">Marcar como vista</button>' : ""}
        ${actual.vista ? '<span class="etiqueta">Lección vista</span>' : ""}
      </article>
    </div>`;

  vista.querySelectorAll("[data-leccion]").forEach((b) => b.addEventListener("click", () => vistaCurso(id, b.dataset.leccion)));
  $("#inscribirme")?.addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    try { await api(`cursos/cursos/${id}/inscripcion`, { metodo: "POST" }); avisar("Inscripción registrada"); vistaCurso(id); }
    catch (e) { avisar(e.message, true); ev.target.disabled = false; }
  });
  $("#completar")?.addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    try {
      const r = await api(`cursos/cursos/${id}/lecciones/${actual.id}/completar`, { metodo: "POST" });
      if (r.estado === "completado") avisar("¡Curso completado! Su certificado está en camino.");
      await vistaCurso(id);
      setTimeout(actualizarInsignia, 1500);
    } catch (e) { avisar(e.message, true); ev.target.disabled = false; }
  });
}

/* Certificados ------------------------------------------------------------ */

async function vistaCertificados() {
  const lista = await api("certificados/certificados");
  const admin = esAdmin();
  vista.innerHTML = `
    <div class="encabezado">
      <div><h1>${admin ? "Certificados emitidos" : "Mis certificados"}</h1>
      <p>Cada certificado tiene un código que cualquier tercero puede verificar.</p></div>
      <button class="boton secundario" id="recargar">Actualizar</button>
    </div>
    <div class="tarjeta tabla-contenedor">
      ${lista.length ? `<table>
        <thead><tr><th>Código</th>${admin ? "<th>Colaborador</th>" : ""}<th>Curso</th><th>Emitido</th>${admin ? "<th>Trabajador</th>" : ""}<th></th></tr></thead>
        <tbody>${lista.map((c) => `<tr>
          <td class="mono">${esc(c.codigo)}</td>${admin ? `<td>${esc(c.usuario_nombre)}</td>` : ""}
          <td>${esc(c.curso_titulo)} <span class="ayuda">· ${c.horas} h</span></td>
          <td>${fecha(c.emitido_en)}</td>${admin ? `<td class="mono ayuda">${esc(c.emitido_por)}</td>` : ""}
          <td class="fila" style="flex-wrap:nowrap"><button class="boton peque" data-pdf="${esc(c.codigo)}">PDF</button>
            <a class="boton peque secundario" href="#/verificar/${esc(c.codigo)}">Verificar</a></td>
        </tr>`).join("")}</tbody></table>`
        : '<p class="vacio">Aún no hay certificados. Complete un curso para obtener el primero.</p>'}
    </div>`;
  $("#recargar").addEventListener("click", vistaCertificados);
  vista.querySelectorAll("[data-pdf]").forEach((b) => b.addEventListener("click", async () => {
    try {
      const r = await api(`certificados/certificados/${b.dataset.pdf}/pdf`, { crudo: true });
      const url = URL.createObjectURL(await r.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: `certificado-${b.dataset.pdf}.pdf` });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) { avisar(e.message, true); }
  }));
}

async function vistaVerificar(codigo) {
  vista.classList.toggle("sin-margen", false);
  $("#barra").hidden = !usuario();
  vista.innerHTML = `
    <div style="max-width:560px;margin:2rem auto" class="pila">
      <div class="marca" style="color:var(--tinta)"><img src="icono.svg" alt="" width="28" height="28"><strong>AulaNube</strong></div>
      <div class="tarjeta">
        <h1>Verificar un certificado</h1>
        <form class="fila" id="form-verificar">
          <label>Código <input name="codigo" placeholder="AN-XXXXXXXX" value="${esc(codigo || "")}" required></label>
          <button class="boton" type="submit">Verificar</button>
        </form>
        <div id="resultado" style="margin-top:1rem"></div>
      </div>
      ${usuario() ? "" : '<p class="ayuda"><a href="#/ingresar">Ingresar a la plataforma</a></p>'}
    </div>`;
  const form = $("#form-verificar");
  form.addEventListener("submit", (ev) => { ev.preventDefault(); location.hash = `#/verificar/${form.codigo.value.trim().toUpperCase()}`; });
  if (!codigo) return;
  const salida = $("#resultado");
  try {
    const c = await api(`certificados/verificar/${encodeURIComponent(codigo)}`);
    salida.innerHTML = `<div class="banda"><strong>Certificado válido.</strong><br>
      ${esc(c.usuario_nombre)} (${esc(c.empresa_nombre)}) completó «${esc(c.curso_titulo)}», ${c.horas} h, el ${fecha(c.emitido_en)}.</div>`;
  } catch (e) {
    salida.innerHTML = `<div class="banda ambar">${esc(e.estado === 404 ? "No existe un certificado con ese código." : e.message)}</div>`;
  }
}

/* Avisos ------------------------------------------------------------------ */

async function vistaNotificaciones() {
  const { avisos } = await api("notificaciones/notificaciones");
  vista.innerHTML = `
    <div class="encabezado">
      <div><h1>Avisos</h1><p>Se generan a partir de los eventos de la plataforma.</p></div>
      <button class="boton secundario" id="todas">Marcar todo como leído</button>
    </div>
    ${avisos.length ? `<ul class="avisos">${avisos.map((a) => `
      <li class="tarjeta ${a.leida ? "" : "nuevo"}">
        <div style="flex:1"><h3>${esc(a.titulo)}</h3><p style="margin:0">${esc(a.mensaje)}</p>
        ${a.enlace ? `<a href="${esc(a.enlace)}" data-aviso="${a.id}">Ir</a>` : ""}</div>
        <time>${fecha(a.creada_en)}</time>
      </li>`).join("")}</ul>` : '<div class="tarjeta vacio">No tiene avisos.</div>'}`;
  $("#todas").addEventListener("click", async () => { await api("notificaciones/notificaciones/leidas", { metodo: "POST" }); vistaNotificaciones(); actualizarInsignia(); });
  vista.querySelectorAll("[data-aviso]").forEach((a) => a.addEventListener("click", () => {
    api(`notificaciones/notificaciones/${a.dataset.aviso}/leida`, { metodo: "POST" }).catch(() => {});
  }));
}

/* Gestión (administrador) ------------------------------------------------- */

async function vistaGestion() {
  if (!esAdmin()) { location.hash = "#/cursos"; return; }
  const [cursos, usuarios] = await Promise.all([api("cursos/cursos"), api("identidad/usuarios")]);
  vista.innerHTML = `
    <div class="encabezado"><div><h1>Gestión de ${esc(usuario().empresa)}</h1><p>Cursos, colaboradores y campañas de capacitación.</p></div></div>
    <div class="dos-columnas">
      <div class="pila">
        <section class="tarjeta">
          <h2>Simular cierre de campaña</h2>
          <p class="ayuda">Inscribe y completa el curso para N participantes de una vez. El servicio de cursos responde enseguida y los certificados se generan detrás, al ritmo de los trabajadores. Mire la cola en <a href="#/arquitectura">Arquitectura</a>.</p>
          <form class="fila" id="form-campana">
            <label>Curso <select name="curso_id">${cursos.map((c) => `<option value="${c.id}">${esc(c.titulo)}</option>`).join("")}</select></label>
            <label style="max-width:130px">Participantes <input name="participantes" type="number" min="1" max="500" value="60"></label>
            <button class="boton" type="submit">Lanzar</button>
          </form>
        </section>
        <section class="tarjeta">
          <h2>Cursos</h2>
          <div class="tabla-contenedor"><table><thead><tr><th>Curso</th><th>Inscritos</th><th>Completados</th></tr></thead>
          <tbody>${cursos.map((c) => `<tr><td><a href="#/curso/${c.id}">${esc(c.titulo)}</a></td><td>${c.inscritos.total}</td><td>${c.inscritos.completados}</td></tr>`).join("")}</tbody></table></div>
        </section>
        <section class="tarjeta">
          <h2>Colaboradores</h2>
          <div class="tabla-contenedor"><table><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th></tr></thead>
          <tbody>${usuarios.map((u) => `<tr><td>${esc(u.nombre)}</td><td>${esc(u.correo)}</td><td>${u.rol === "admin" ? "Administrador" : "Estudiante"}</td></tr>`).join("")}</tbody></table></div>
          <form class="pila" id="form-usuario" style="margin-top:1rem">
            <h3>Agregar colaborador</h3>
            <div class="fila">
              <label>Nombre <input name="nombre" required minlength="3"></label>
              <label>Correo <input name="correo" type="email" required></label>
            </div>
            <label>Clave inicial <input name="clave" type="text" minlength="8" required></label>
            <button class="boton secundario" type="submit">Agregar</button>
          </form>
        </section>
      </div>
      <section class="tarjeta">
        <h2>Nuevo curso</h2>
        <form class="pila" id="form-curso">
          <label>Título <input name="titulo" required minlength="3" maxlength="160"></label>
          <label>Descripción <textarea name="descripcion" rows="2"></textarea></label>
          <label style="max-width:140px">Horas <input name="horas" type="number" min="1" max="200" value="2"></label>
          <div id="lecciones-form" class="pila"></div>
          <button class="boton secundario" type="button" id="otra-leccion">Agregar lección</button>
          <p class="error" id="error-curso"></p>
          <button class="boton" type="submit">Crear curso</button>
        </form>
      </section>
    </div>`;

  const contenedor = $("#lecciones-form");
  const agregarLeccion = () => {
    const n = contenedor.children.length + 1;
    contenedor.insertAdjacentHTML("beforeend", `<fieldset class="pila" style="border:1px solid var(--linea);border-radius:8px;padding:.75rem">
      <legend class="ayuda">Lección ${n}</legend>
      <input name="leccion-titulo" placeholder="Título de la lección" required>
      <textarea name="leccion-contenido" rows="2" placeholder="Contenido"></textarea></fieldset>`);
  };
  agregarLeccion();
  $("#otra-leccion").addEventListener("click", agregarLeccion);

  $("#form-curso").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const titulos = [...f.querySelectorAll("[name=leccion-titulo]")];
    const contenidos = [...f.querySelectorAll("[name=leccion-contenido]")];
    try {
      await api("cursos/cursos", { metodo: "POST", cuerpo: {
        titulo: f.titulo.value, descripcion: f.descripcion.value, horas: Number(f.horas.value),
        lecciones: titulos.map((t, i) => ({ titulo: t.value, contenido: contenidos[i].value })),
      } });
      avisar("Curso creado");
      vistaGestion();
    } catch (e) { $("#error-curso").textContent = e.message; }
  });

  $("#form-campana").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const boton = f.querySelector("button");
    boton.disabled = true;
    try {
      const r = await api("cursos/campanas", { metodo: "POST", cuerpo: { curso_id: Number(f.curso_id.value), participantes: Number(f.participantes.value) } });
      avisar(`${r.eventos} cursos completados: certificados en cola`);
      location.hash = "#/arquitectura";
    } catch (e) { avisar(e.message, true); boton.disabled = false; }
  });

  $("#form-usuario").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    try {
      await api("identidad/usuarios", { metodo: "POST", cuerpo: { nombre: f.nombre.value, correo: f.correo.value, clave: f.clave.value } });
      avisar("Colaborador agregado");
      vistaGestion();
    } catch (e) { avisar(e.message, true); }
  });
}

/* Panel de arquitectura ---------------------------------------------------- */

const NOMBRES = { identidad: "Identidad", cursos: "Cursos", certificados: "Certificados", notificaciones: "Notificaciones" };

function pillCircuito(c) {
  if (c.estado === "abierto") return `<span class="etiqueta rojo">Circuito abierto · ${c.segundos_para_reintento}s</span>`;
  if (c.estado === "semiabierto") return '<span class="etiqueta ambar">Semiabierto · en prueba</span>';
  return '<span class="etiqueta">Circuito cerrado</span>';
}

async function vistaArquitectura() {
  if (!esAdmin()) { location.hash = "#/cursos"; return; }
  vista.innerHTML = `
    <div class="encabezado">
      <div><h1>Arquitectura en vivo</h1><p>Estado que reporta el API Gateway; se actualiza cada 2 segundos.</p></div>
      <span class="ayuda" id="hora"></span>
    </div>
    <div class="pila">
      <section class="tarjeta">
        <h2>Servicios detrás del gateway</h2>
        <div class="servicios" id="servicios"></div>
      </section>
      <section class="tarjeta">
        <h2>Cola de eventos</h2>
        <p class="ayuda">Cursos publica <code>curso.completado</code> en <code>aulanube.cursos</code> y certificados publica <code>certificado.emitido</code> en <code>aulanube.certificados</code>. Cada servicio suscrito lee con su propio grupo de consumidores. «Por procesar» es lo que espera turno: con una campaña masiva sube y baja a medida que los trabajadores la procesan.</p>
        <div class="cifras" id="cola"></div>
      </section>
    </div>`;
  let maximo = 1;
  const pintar = async () => {
    let e;
    try { e = await api("estado"); } catch (err) { $("#servicios").innerHTML = `<p class="error">${esc(err.message)}</p>`; return; }
    $("#hora").textContent = `Actualizado ${new Date().toLocaleTimeString("es-CO")}`;
    $("#servicios").innerHTML = e.servicios.map((s) => `
      <div class="tarjeta servicio">
        <span class="nombre"><span class="punto ${s.disponible ? "" : "caido"}"></span>${NOMBRES[s.servicio] || s.servicio}</span>
        ${pillCircuito(s.circuito)}
        <span class="ayuda">${s.disponible ? "Responde /salud" : "No responde"} · ${s.circuito.rechazadas} rechazadas</span>
      </div>`).join("");
    const cola = e.cola;
    if (!cola || cola.disponible === false) { $("#cola").innerHTML = '<p class="ayuda" style="grid-column:1/-1">La cola no está disponible (el servicio de certificados o Redis no responde).</p>'; return; }
    const grupos = cola.grupos || [];
    grupos.forEach((g) => { maximo = Math.max(maximo, g.sin_leer + g.pendientes); });
    $("#cola").innerHTML = `
      <div><div class="cifra">${cola.certificados_emitidos}</div><span class="ayuda">certificados emitidos</span></div>
      <div><div class="cifra">${cola.longitud}</div><span class="ayuda">eventos publicados</span></div>
      ${grupos.map((g) => `<div>
        <div class="cifra">${g.sin_leer + g.pendientes}</div>
        <span class="ayuda">por procesar en <strong>${esc(g.grupo)}</strong> desde <code>${esc(g.flujo)}</code> · ${g.consumidores} consumidor(es)</span>
        <div class="barra-cola"><span style="width:${Math.round(100 * (g.sin_leer + g.pendientes) / maximo)}%"></span></div>
      </div>`).join("")}
      <div><div class="cifra">${cola.fallidos ?? 0}</div><span class="ayuda">eventos apartados (fallidos)</span></div>`;
  };
  await pintar();
  temporizador = setInterval(pintar, 2000);
}

navegar();
