"""Catálogo de demostración para las dos empresas sembradas en identidad."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .modelos import Curso
from .repositorio import RepositorioCursos

CURSOS = {
    1: [
        (
            "Trabajo seguro en alturas: nivel básico",
            "Conceptos de la Resolución 4272 de 2021, sistemas de protección contra caídas y procedimientos de rescate.",
            8,
            [
                ("Marco normativo", "La Resolución 4272 de 2021 fija los requisitos mínimos de seguridad para trabajo en alturas en Colombia. Se considera trabajo en alturas toda labor con riesgo de caída de 2 metros o más."),
                ("Medidas de prevención", "Antes de cualquier tarea se diligencia el permiso de trabajo, se delimita el área y se verifican las condiciones de los puntos de anclaje."),
                ("Equipos de protección", "El arnés de cuerpo completo, la eslinga con absorbedor y el conector se inspeccionan antes de cada uso. Un equipo que detuvo una caída se retira del servicio."),
                ("Plan de rescate", "Todo trabajo en alturas exige un plan de rescate escrito y personal entrenado disponible durante la tarea."),
            ],
        ),
        (
            "Inducción al SG-SST",
            "Política de seguridad y salud en el trabajo de la empresa, reporte de incidentes y comité paritario.",
            2,
            [
                ("Política y objetivos", "El Sistema de Gestión de Seguridad y Salud en el Trabajo (Decreto 1072 de 2015) busca prevenir lesiones y enfermedades laborales."),
                ("Reporte de actos y condiciones inseguras", "Cualquier trabajador puede reportar una condición insegura al supervisor o por el canal del COPASST, sin represalias."),
                ("Emergencias", "Conozca la ruta de evacuación de su frente de obra y el punto de encuentro."),
            ],
        ),
    ],
    2: [
        (
            "Protección de datos personales (Ley 1581 de 2012)",
            "Tratamiento de datos sensibles de pacientes, autorización, derechos del titular y manejo de incidentes.",
            4,
            [
                ("Principios del tratamiento", "La Ley 1581 de 2012 establece principios como legalidad, finalidad, libertad, veracidad, transparencia, seguridad y confidencialidad."),
                ("Datos sensibles en salud", "La historia clínica contiene datos sensibles: solo se tratan con autorización explícita o por obligación legal, y su acceso se limita al personal autorizado."),
                ("Derechos del titular", "El paciente puede conocer, actualizar, rectificar y solicitar la supresión de sus datos, salvo deber legal de conservarlos."),
                ("Incidentes de seguridad", "Un acceso no autorizado a datos se reporta de inmediato al oficial de protección de datos y a la Superintendencia de Industria y Comercio."),
            ],
        ),
        (
            "Atención humanizada al paciente",
            "Comunicación empática, trato digno y manejo de situaciones difíciles en la atención.",
            3,
            [
                ("Comunicación empática", "Escuchar sin interrumpir, validar la emoción del paciente y explicar con palabras sencillas."),
                ("Trato digno", "Llamar al paciente por su nombre, respetar su intimidad y explicar cada procedimiento antes de realizarlo."),
                ("Situaciones difíciles", "Ante un paciente o familiar alterado, mantener la calma, ofrecer un espacio privado y escalar al coordinador cuando sea necesario."),
            ],
        ),
    ],
}


def sembrar(sesion: Session) -> None:
    if sesion.scalar(select(Curso.id).limit(1)) is not None:
        return
    repo = RepositorioCursos(sesion)
    for empresa_id, cursos in CURSOS.items():
        for titulo, descripcion, horas, lecciones in cursos:
            repo.crear(empresa_id, titulo, descripcion, horas, lecciones)
    sesion.commit()
