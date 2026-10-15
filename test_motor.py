"""Pruebas automatizadas del motor (unittest).

Cubre: U1 a U6, I1 y la escena no final sin opciones habilitadas.

Ejecutar desde la carpeta del proyecto:
    python -m unittest discover pruebas -v
"""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import main as motor  # noqa: E402

RUTA_HISTORIA = os.path.join(RAIZ, "la_ultima_transmision.json")
RUTA_SEGUNDA = os.path.join(RAIZ, "segunda_historia.json")


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def leer_json(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def nueva_sesion(datos=None):
    sesion = motor.Sesion(datos if datos is not None else leer_json(RUTA_HISTORIA))
    sesion.iniciar()
    return sesion


def estado(sesion):
    """Foto completa del estado observable: escena, variables e historial."""
    return (
        sesion.escena_actual_id,
        copy.deepcopy(sesion.variables),
        copy.deepcopy(sesion.instantanea),
    )


def ids(opciones):
    return [op["id"] for op in opciones]


def elegir_todas(sesion, *ids_opcion):
    for id_opcion in ids_opcion:
        exito, mensaje = sesion.elegir(id_opcion)
        assert exito, f"No se pudo elegir '{id_opcion}': {mensaje}"


def _lector_de_entradas(entradas):
    iterador = iter(entradas)

    def leer(prompt=""):
        try:
            return next(iterador)
        except StopIteration:
            raise EOFError from None

    return leer


def ejecutar_jugar(datos, entradas):
    """Corre el bucle de consola con entradas simuladas y devuelve lo que se imprimió."""
    salida = io.StringIO()
    with mock.patch("builtins.input", _lector_de_entradas(entradas)):
        with contextlib.redirect_stdout(salida):
            try:
                motor.jugar(datos)
            except EOFError:
                pass
    return salida.getvalue()


# ----------------------------------------------------------------------
# U1. Condiciones cumplidas y no cumplidas
# ----------------------------------------------------------------------
class PruebaU1Condiciones(unittest.TestCase):
    def test_evaluador_con_condiciones_cumplidas_y_no_cumplidas(self):
        casos = [
            ("mapa vacío habilita", {}, {"a": True}, True),
            ("igualdad cumplida (verdadero)", {"a": True}, {"a": True}, True),
            ("igualdad cumplida (falso)", {"a": False}, {"a": False}, True),
            ("igualdad no cumplida", {"a": True}, {"a": False}, False),
            ("todas deben cumplirse: una falla", {"a": True, "b": False}, {"a": True, "b": True}, False),
            ("todas deben cumplirse: todas ok", {"a": True, "b": False}, {"a": True, "b": False}, True),
            ("variable ausente no cumple", {"a": True}, {}, False),
        ]
        evaluador = motor.Evaluador()
        for nombre, condiciones, variables, esperado in casos:
            with self.subTest(nombre):
                self.assertEqual(evaluador.cumple(condiciones, variables), esperado)

    def test_sesion_muestra_solo_opciones_compatibles_en_e3(self):
        casos = [
            ("conoce_origen verdadero", True, ["activar_codigo", "cortar"]),
            ("conoce_origen falso", False, ["activar_sin_verificar", "cortar"]),
        ]
        for nombre, conoce, esperadas in casos:
            with self.subTest(nombre):
                sesion = nueva_sesion()
                sesion.escena_actual_id = "E3"
                sesion.variables["conoce_origen"] = conoce
                habilitadas = ids(sesion.opciones_habilitadas())
                self.assertEqual(len(habilitadas), 2)
                self.assertEqual(sorted(habilitadas), sorted(esperadas))

    def test_ca01_revisar_senal_e_investigar_deja_dos_opciones(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar", "investigar")
        self.assertEqual(sesion.escena_actual_id, "E3")
        self.assertTrue(sesion.variables["conoce_origen"])
        self.assertEqual(sorted(ids(sesion.opciones_habilitadas())), ["activar_codigo", "cortar"])


# ----------------------------------------------------------------------
# U2. Elección válida: efectos y destino
# ----------------------------------------------------------------------
class PruebaU2Elegir(unittest.TestCase):
    def test_eleccion_valida_aplica_efectos_y_avanza(self):
        casos = [
            # (nombre, camino previo, opción a elegir, escena esperada, variables esperadas)
            ("revisar avanza a E2 sin efectos", [], "revisar", "E2",
             {"conoce_origen": False, "confia_en_la_voz": False}),
            ("investigar activa conoce_origen", ["revisar"], "investigar", "E3",
             {"conoce_origen": True, "confia_en_la_voz": False}),
            ("continuar conserva las variables", ["revisar"], "continuar", "E3",
             {"conoce_origen": False, "confia_en_la_voz": False}),
            ("activar con código lleva a E4", ["revisar", "investigar"], "activar_codigo", "E4",
             {"conoce_origen": True, "confia_en_la_voz": True}),
            ("activar sin verificar lleva a E5", ["revisar", "continuar"], "activar_sin_verificar", "E5",
             {"conoce_origen": False, "confia_en_la_voz": True}),
            ("cortar lleva a E6", ["revisar", "continuar"], "cortar", "E6",
             {"conoce_origen": False, "confia_en_la_voz": False}),
        ]
        for nombre, camino, opcion, escena, variables in casos:
            with self.subTest(nombre):
                sesion = nueva_sesion()
                elegir_todas(sesion, *camino)
                exito, _ = sesion.elegir(opcion)
                self.assertTrue(exito)
                self.assertEqual(sesion.escena_actual_id, escena)
                self.assertEqual(sesion.variables, variables)

    def test_las_variables_del_archivo_no_se_modifican(self):
        datos = leer_json(RUTA_HISTORIA)
        sesion = nueva_sesion(datos)
        elegir_todas(sesion, "revisar", "investigar")
        self.assertEqual(datos["variables"], {"conoce_origen": False, "confia_en_la_voz": False})


# ----------------------------------------------------------------------
# U3. Opción inexistente o no habilitada deja intacto el estado
# ----------------------------------------------------------------------
class PruebaU3EntradaInvalida(unittest.TestCase):
    def test_opcion_inexistente_o_no_habilitada_no_cambia_nada(self):
        casos = [
            # (nombre, camino previo, entrada inválida)
            ("id inexistente", ["revisar"], "xyz"),
            ("entrada vacía", ["revisar"], ""),
            ("solo espacios", ["revisar"], "   "),
            ("el texto de la opción no es un id", [], "Revisar señal"),
            ("valor no textual", ["revisar"], 5),
            ("None", ["revisar"], None),
            ("CA02: activar_codigo sin conocer el origen", ["revisar", "continuar"], "activar_codigo"),
            ("activar_sin_verificar conociendo el origen", ["revisar", "investigar"], "activar_sin_verificar"),
            ("opción de otra escena", ["revisar", "continuar"], "revisar"),
            ("desde un final no hay opciones", ["revisar", "continuar", "cortar"], "revisar"),
        ]
        for nombre, camino, entrada in casos:
            with self.subTest(nombre):
                sesion = nueva_sesion()
                elegir_todas(sesion, *camino)
                antes = estado(sesion)
                exito, mensaje = sesion.elegir(entrada)
                self.assertFalse(exito)
                self.assertTrue(mensaje)
                self.assertEqual(estado(sesion), antes)

    def test_escena_no_final_sin_opciones_habilitadas_informa_bloqueo(self):
        datos = {
            "titulo": "Bloqueo",
            "inicio": "A",
            "variables": {"x": False},
            "escenas": [
                {"id": "A", "texto": "Inicio", "final": False, "opciones": [
                    {"id": "o", "texto": "Seguir", "destino": "B", "condiciones": {}, "efectos": {}}]},
                {"id": "B", "texto": "Sin salida", "final": False, "opciones": [
                    {"id": "p", "texto": "Imposible", "destino": "A", "condiciones": {"x": True}, "efectos": {}}]},
            ],
        }
        self.assertEqual(motor.Validador().validar(datos), [])  # el contenido es válido
        salida = ejecutar_jugar(datos, ["1", "reiniciar", "salir"])
        self.assertIn("[BLOQUEO]", salida)
        self.assertEqual(salida.count("Escena: A"), 2)  # tras reiniciar vuelve a A
        # y también se puede deshacer desde el bloqueo
        salida = ejecutar_jugar(datos, ["1", "deshacer", "salir"])
        self.assertIn("[BLOQUEO]", salida)
        self.assertIn("[Se deshizo la última elección.]", salida)
        self.assertEqual(salida.count("Escena: A"), 2)


# ----------------------------------------------------------------------
# U4. Errores de contenido (9 categorías), con datos parametrizados
# ----------------------------------------------------------------------
def _sin(campo):
    def modificar(d):
        del d[campo]
        return d
    return modificar


def _escena(indice, **cambios):
    def modificar(d):
        for clave, valor in cambios.items():
            if valor is _BORRAR:
                del d["escenas"][indice][clave]
            else:
                d["escenas"][indice][clave] = valor
        return d
    return modificar


def _opcion(escena, opcion, **cambios):
    def modificar(d):
        for clave, valor in cambios.items():
            if valor is _BORRAR:
                del d["escenas"][escena]["opciones"][opcion][clave]
            else:
                d["escenas"][escena]["opciones"][opcion][clave] = valor
        return d
    return modificar


_BORRAR = object()


def _escena_duplicada(d):
    d["escenas"].append(copy.deepcopy(d["escenas"][0]))
    return d


def _opcion_duplicada(d):
    d["escenas"][1]["opciones"].append(copy.deepcopy(d["escenas"][1]["opciones"][0]))
    return d


def _final_con_opciones(d):
    d["escenas"][3]["opciones"] = [copy.deepcopy(d["escenas"][0]["opciones"][0])]
    return d


def _variable_inicial(valor):
    def modificar(d):
        d["variables"]["conoce_origen"] = valor
        return d
    return modificar


# (categoría, nombre, función que daña una copia de la historia, fragmentos que debe nombrar el mensaje)
CASOS_U4 = [
    ("1 estructura incorrecta", "la raíz no es un objeto", lambda d: [], ["raíz"]),
    ("2 campo obligatorio ausente", "sin titulo", _sin("titulo"), ["titulo"]),
    ("2 campo obligatorio ausente", "sin inicio", _sin("inicio"), ["inicio"]),
    ("2 campo obligatorio ausente", "sin variables", _sin("variables"), ["variables"]),
    ("2 campo obligatorio ausente", "sin escenas", _sin("escenas"), ["escenas"]),
    ("2 campo obligatorio ausente", "escena sin texto", _escena(0, texto=_BORRAR), ["E1", "texto"]),
    ("2 campo obligatorio ausente", "escena sin final", _escena(0, final=_BORRAR), ["E1", "final"]),
    ("2 campo obligatorio ausente", "escena sin opciones", _escena(0, opciones=_BORRAR), ["E1", "opciones"]),
    ("2 campo obligatorio ausente", "opción sin destino", _opcion(0, 0, destino=_BORRAR), ["revisar", "destino"]),
    ("2 campo obligatorio ausente", "opción sin texto", _opcion(0, 0, texto=_BORRAR), ["revisar", "texto"]),
    ("3 escena inicial inexistente", "inicio E77", lambda d: dict(d, inicio="E77"), ["E77"]),
    ("4 id de escena repetido", "E1 dos veces", _escena_duplicada, ["E1", "duplicado"]),
    ("5 id de opción repetido", "investigar dos veces en E2", _opcion_duplicada, ["investigar", "E2", "duplicado"]),
    ("6 destino inexistente", "destino E99 (CA03)", _opcion(0, 0, destino="E99"), ["revisar", "E1", "E99"]),
    ("7 variable no declarada", "en efectos", _opcion(1, 0, efectos={"variable_x": True}), ["variable_x", "investigar", "efectos"]),
    ("7 variable no declarada", "en condiciones", _opcion(2, 0, condiciones={"variable_x": True}), ["variable_x", "activar_codigo", "condiciones"]),
    ("8 valor no booleano", "efecto con texto", _opcion(1, 0, efectos={"conoce_origen": "si"}), ["conoce_origen", "investigar", "booleano"]),
    ("8 valor no booleano", "condición con número", _opcion(2, 0, condiciones={"conoce_origen": 1}), ["conoce_origen", "activar_codigo", "booleano"]),
    ("8 valor no booleano", "variable inicial con texto", _variable_inicial("no"), ["conoce_origen", "booleano"]),
    ("9 finales y opciones", "final con opciones", _final_con_opciones, ["E4", "final", "no debe tener opciones"]),
    ("9 finales y opciones", "no final sin opciones", _escena(0, opciones=[]), ["E1", "al menos una opción"]),
    ("tipos erróneos", "destino que es una lista", _opcion(0, 0, destino=["E2"]), ["revisar", "destino", "texto"]),
    ("tipos erróneos", "inicio que es una lista", lambda d: dict(d, inicio=["E1"]), ["inicio"]),
]


class PruebaU4ErroresDeContenido(unittest.TestCase):
    def test_el_validador_detecta_cada_error_y_nombra_causa_e_id(self):
        base = leer_json(RUTA_HISTORIA)
        self.assertEqual(motor.Validador().validar(copy.deepcopy(base)), [])  # la historia buena es válida
        for categoria, nombre, danar, fragmentos in CASOS_U4:
            with self.subTest(f"{categoria}: {nombre}"):
                datos = danar(copy.deepcopy(base))
                errores = motor.Validador().validar(datos)
                self.assertTrue(errores, "debería haber detectado el error")
                texto = " ".join(errores)
                for fragmento in fragmentos:
                    self.assertIn(fragmento, texto)

    def test_archivo_ilegible_se_rechaza_con_mensaje_controlado(self):
        casos = [
            ("JSON mal formado", b'{"titulo": "x", ', ["no es un JSON válido"]),
            ("mala codificación", b"\xff\xfe\x00 no es utf-8", ["UTF-8"]),
        ]
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre, contenido, fragmentos in casos:
                with self.subTest(nombre):
                    ruta = os.path.join(carpeta, "historia.json")
                    with open(ruta, "wb") as f:
                        f.write(contenido)
                    with self.assertRaises(motor.ErrorCarga) as contexto:
                        motor.CargadorHistoria().cargar(ruta)
                    for fragmento in fragmentos:
                        self.assertIn(fragmento, str(contexto.exception))
            with self.subTest("archivo inexistente"):
                with self.assertRaises(motor.ErrorCarga) as contexto:
                    motor.CargadorHistoria().cargar(os.path.join(carpeta, "no_existe.json"))
                self.assertIn("No se encontró", str(contexto.exception))
            with self.subTest("la ruta es una carpeta"):
                with self.assertRaises(motor.ErrorCarga):
                    motor.CargadorHistoria().cargar(carpeta)

    def test_archivo_invalido_nunca_abre_sesion_y_sale_con_codigo_controlado(self):
        """CA03 y RF18: destino E99 -> mensaje, sin sesión jugable, código de salida 1."""
        base = leer_json(RUTA_HISTORIA)
        base["escenas"][0]["opciones"][0]["destino"] = "E99"
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "con_e99.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(base, f)
            salida = io.StringIO()
            with mock.patch.object(motor, "jugar") as jugar, contextlib.redirect_stdout(salida):
                codigo = motor.main(["main.py", ruta])
        self.assertEqual(codigo, 1)
        jugar.assert_not_called()
        for fragmento in ("revisar", "E1", "E99"):
            self.assertIn(fragmento, salida.getvalue())

    def test_todas_las_categorias_terminan_con_codigo_controlado(self):
        """RNF02: ningún error de contenido termina con una excepción no controlada."""
        base = leer_json(RUTA_HISTORIA)
        with tempfile.TemporaryDirectory() as carpeta:
            for categoria, nombre, danar, fragmentos in CASOS_U4:
                with self.subTest(f"{categoria}: {nombre}"):
                    ruta = os.path.join(carpeta, "historia.json")
                    with open(ruta, "w", encoding="utf-8") as f:
                        json.dump(danar(copy.deepcopy(base)), f)
                    salida = io.StringIO()
                    with mock.patch.object(motor, "jugar") as jugar, contextlib.redirect_stdout(salida):
                        codigo = motor.main(["main.py", ruta])
                    self.assertEqual(codigo, 1)
                    jugar.assert_not_called()


# ----------------------------------------------------------------------
# U5. Reiniciar (extendida: también elimina el historial)
# ----------------------------------------------------------------------
class PruebaU5Reiniciar(unittest.TestCase):
    def test_reiniciar_restaura_escena_y_variables_iniciales(self):
        casos = [
            ("desde E3 con variables cambiadas", ["revisar", "investigar"]),
            ("desde el final E4", ["revisar", "investigar", "activar_codigo"]),
            ("desde el final E5", ["revisar", "continuar", "activar_sin_verificar"]),
            ("sin haber jugado", []),
        ]
        for nombre, camino in casos:
            with self.subTest(nombre):
                sesion = nueva_sesion()
                elegir_todas(sesion, *camino)
                sesion.reiniciar()
                self.assertEqual(sesion.escena_actual_id, "E1")
                self.assertEqual(sesion.variables, {"conoce_origen": False, "confia_en_la_voz": False})

    def test_reiniciar_elimina_el_historial(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar", "investigar")
        self.assertTrue(sesion.puede_deshacer())
        sesion.reiniciar()
        self.assertFalse(sesion.puede_deshacer())
        antes = estado(sesion)
        exito, _ = sesion.deshacer()
        self.assertFalse(exito)
        self.assertEqual(estado(sesion), antes)


# ----------------------------------------------------------------------
# U6. Deshacer de un solo nivel
# ----------------------------------------------------------------------
class PruebaU6Deshacer(unittest.TestCase):
    def test_deshacer_restaura_escena_y_variables_y_consume_el_retroceso(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar")
        antes_de_elegir = (sesion.escena_actual_id, copy.deepcopy(sesion.variables))
        elegir_todas(sesion, "investigar")
        self.assertEqual(sesion.escena_actual_id, "E3")
        self.assertTrue(sesion.variables["conoce_origen"])

        exito, _ = sesion.deshacer()
        self.assertTrue(exito)
        self.assertEqual((sesion.escena_actual_id, sesion.variables), antes_de_elegir)
        self.assertEqual(sesion.escena_actual_id, "E2")
        self.assertFalse(sesion.variables["conoce_origen"])
        self.assertFalse(sesion.puede_deshacer())  # consume la posibilidad de retroceder

    def test_ejemplo_de_la_solicitud_de_cambio(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar", "investigar")
        sesion.deshacer()
        self.assertEqual(sesion.escena_actual_id, "E2")
        self.assertFalse(sesion.variables["conoce_origen"])
        # un segundo intento de deshacer no cambia nada
        antes = estado(sesion)
        exito, _ = sesion.deshacer()
        self.assertFalse(exito)
        self.assertEqual(estado(sesion), antes)
        # al continuar sin investigar, E3 muestra activar sin verificar y cortar
        elegir_todas(sesion, "continuar")
        self.assertEqual(sesion.escena_actual_id, "E3")
        self.assertEqual(sorted(ids(sesion.opciones_habilitadas())), ["activar_sin_verificar", "cortar"])

    def test_al_comenzar_no_hay_retroceso(self):
        sesion = nueva_sesion()
        antes = estado(sesion)
        exito, mensaje = sesion.deshacer()
        self.assertFalse(exito)
        self.assertTrue(mensaje)
        self.assertEqual(estado(sesion), antes)

    def test_variante_entrada_invalida_conserva_el_historial(self):
        entradas_invalidas = ["xyz", "", "Investigar archivo", "activar_codigo", None, 7]
        for entrada in entradas_invalidas:
            with self.subTest(repr(entrada)):
                sesion = nueva_sesion()
                elegir_todas(sesion, "revisar", "continuar")  # ahora en E3 sin conocer el origen
                historial = copy.deepcopy(sesion.instantanea)
                exito, _ = sesion.elegir(entrada)
                self.assertFalse(exito)
                self.assertEqual(sesion.instantanea, historial)  # no sustituye el historial
                sesion.deshacer()
                self.assertEqual(sesion.escena_actual_id, "E2")  # sigue restaurando la última válida

    def test_variante_una_nueva_eleccion_vuelve_a_habilitar_el_retroceso(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar", "investigar")
        sesion.deshacer()
        self.assertFalse(sesion.puede_deshacer())
        elegir_todas(sesion, "continuar")
        self.assertTrue(sesion.puede_deshacer())
        exito, _ = sesion.deshacer()
        self.assertTrue(exito)
        self.assertEqual(sesion.escena_actual_id, "E2")

    def test_variante_solo_se_deshace_la_ultima_eleccion(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar", "investigar")  # dos elecciones válidas
        sesion.deshacer()
        self.assertEqual(sesion.escena_actual_id, "E2")  # solo revirtió la última (investigar)
        self.assertFalse(sesion.puede_deshacer())  # y no hay otro nivel

    def test_variante_desde_cada_final_se_regresa_a_e3_con_las_variables_previas(self):
        casos = [
            ("E4", ["revisar", "investigar"], "activar_codigo",
             {"conoce_origen": True, "confia_en_la_voz": False}),
            ("E5", ["revisar", "continuar"], "activar_sin_verificar",
             {"conoce_origen": False, "confia_en_la_voz": False}),
            ("E6", ["revisar", "investigar"], "cortar",
             {"conoce_origen": True, "confia_en_la_voz": False}),
        ]
        for final, camino, opcion, variables_previas in casos:
            with self.subTest(final):
                sesion = nueva_sesion()
                elegir_todas(sesion, *camino)
                elegir_todas(sesion, opcion)
                self.assertEqual(sesion.escena_actual_id, final)
                self.assertTrue(sesion.escena_actual()["final"])
                exito, _ = sesion.deshacer()
                self.assertTrue(exito)
                self.assertEqual(sesion.escena_actual_id, "E3")
                self.assertEqual(sesion.variables, variables_previas)

    def test_deshacer_no_comparte_referencias_con_el_estado_posterior(self):
        sesion = nueva_sesion()
        elegir_todas(sesion, "revisar", "investigar")
        sesion.deshacer()
        sesion.variables["conoce_origen"] = True  # se modifica a mano tras deshacer
        elegir_todas(sesion, "investigar")
        sesion.deshacer()
        self.assertTrue(sesion.variables["conoce_origen"])  # la instantánea guardó el valor de ese momento


# ----------------------------------------------------------------------
# I1. Integración: archivo real + motor (+ consola)
# ----------------------------------------------------------------------
class PruebaI1Integracion(unittest.TestCase):
    def test_carga_de_archivo_real_y_recorrido_hasta_un_final_con_deshacer(self):
        datos, errores = motor.cargar_historia(RUTA_HISTORIA)
        self.assertEqual(errores, [])
        sesion = motor.Sesion(datos)
        sesion.iniciar()
        self.assertEqual(sesion.escena_actual_id, "E1")

        elegir_todas(sesion, "revisar", "investigar", "activar_codigo")
        self.assertEqual(sesion.escena_actual_id, "E4")
        self.assertTrue(sesion.escena_actual()["final"])
        self.assertEqual(sesion.opciones_habilitadas(), [])

        # deshacer desde el final, después de cargar el archivo y recorrer la historia
        exito, _ = sesion.deshacer()
        self.assertTrue(exito)
        self.assertEqual(sesion.escena_actual_id, "E3")
        self.assertEqual(sesion.variables, {"conoce_origen": True, "confia_en_la_voz": False})
        # y desde ahí se puede alcanzar otro final
        elegir_todas(sesion, "cortar")
        self.assertEqual(sesion.escena_actual_id, "E6")

    def test_consola_recorre_los_tres_finales(self):
        datos = leer_json(RUTA_HISTORIA)
        caminos = {"E4": ["1", "1", "1"], "E5": ["1", "2", "1"], "E6": ["1", "2", "2"]}
        for final, entradas in caminos.items():
            with self.subTest(final):
                salida = ejecutar_jugar(datos, entradas + ["salir"])
                self.assertIn(f"Escena: {final}", salida)
                self.assertIn("FIN DE LA HISTORIA", salida)

    def test_consola_deshacer_desde_un_final_y_continuar(self):
        datos = leer_json(RUTA_HISTORIA)
        salida = ejecutar_jugar(datos, ["1", "1", "1", "deshacer", "2", "salir"])
        self.assertLess(salida.index("Escena: E4"), salida.index("[Se deshizo la última elección.]"))
        self.assertLess(salida.index("[Se deshizo la última elección.]"), salida.rindex("Escena: E6"))
        # tras volver a E3 se vuelven a ver las dos opciones (con conoce_origen verdadero)
        self.assertEqual(salida.count("Activar con código"), 2)

    def test_consola_un_segundo_deshacer_seguido_no_cambia_nada(self):
        datos = leer_json(RUTA_HISTORIA)
        salida = ejecutar_jugar(datos, ["1", "2", "deshacer", "deshacer", "salir"])
        self.assertIn("[Se deshizo la última elección.]", salida)
        self.assertIn("[No hay una elección anterior para deshacer.]", salida)

    def test_la_consola_rechaza_entradas_invalidas_sin_alterar_la_partida(self):
        datos = leer_json(RUTA_HISTORIA)
        salida = ejecutar_jugar(datos, ["", "abc", "9", "0", "²", "1", "salir"])
        self.assertEqual(salida.count("[Error]"), 5)
        self.assertIn("Escena: E2", salida)  # solo la entrada válida avanzó

    def test_segunda_historia_funciona_con_el_mismo_motor(self):
        """RF10: otra historia, con otros IDs y variables, sin editar el motor."""
        datos, errores = motor.cargar_historia(RUTA_SEGUNDA)
        self.assertEqual(errores, [])
        self.assertGreaterEqual(len(datos["escenas"]), 3)

        con_llave = motor.Sesion(datos)
        con_llave.iniciar()
        elegir_todas(con_llave, "tomar_llave")
        self.assertEqual(sorted(ids(con_llave.opciones_habilitadas())), ["abrir_con_llave", "volver_a_casa"])
        elegir_todas(con_llave, "abrir_con_llave")
        self.assertEqual(con_llave.escena_actual_id, "archivo")

        sin_llave = motor.Sesion(datos)
        sin_llave.iniciar()
        elegir_todas(sin_llave, "ir_sin_llave")
        self.assertEqual(sorted(ids(sin_llave.opciones_habilitadas())), ["forzar_puerta", "volver_a_casa"])
        elegir_todas(sin_llave, "forzar_puerta")
        self.assertEqual(sin_llave.escena_actual_id, "alarma")
        self.assertTrue(sin_llave.variables["alarma_activa"])
        sin_llave.deshacer()  # el deshacer también funciona en la segunda historia
        self.assertEqual(sin_llave.escena_actual_id, "pasillo")
        self.assertFalse(sin_llave.variables["alarma_activa"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
