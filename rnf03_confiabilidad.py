"""Verificación del RNF03 (confiabilidad).

Requisito: en 1.000 secuencias aleatorias de entradas válidas e inválidas (incluidas vacías)
sobre ambas historias hay 0 excepciones no controladas, y las entradas inválidas no cambian
escena ni variables.

Procedimiento (semilla fija, reproducible):
  * 1.000 secuencias en total: 500 sobre la_ultima_transmision.json y 500 sobre
    segunda_historia.json.
  * Cada secuencia tiene 40 entradas elegidas al azar entre: ids de opciones reales, números,
    entradas vacías o con espacios, texto sin sentido, caracteres raros, y los comandos
    'reiniciar', 'deshacer' y 'salir'.
  * Verificación A (reglas de la sesión): cada entrada inválida se prueba contra Sesion y se
    compara el estado completo (escena, variables e historial) antes y después.
  * Verificación B (consola): la misma secuencia se ejecuta por el bucle de consola real
    (jugar); no debe lanzar ninguna excepción. El fin de la entrada (EOFError) es el cierre
    esperado de la secuencia, no un fallo.

Ejecutar desde la carpeta del proyecto:
    python pruebas/rnf03_confiabilidad.py
"""
import contextlib
import copy
import io
import json
import os
import random
import sys
import traceback
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import main as motor  # noqa: E402

SEMILLA = 2026
SECUENCIAS_POR_HISTORIA = 500
LARGO_SECUENCIA = 40
HISTORIAS = ["la_ultima_transmision.json", "segunda_historia.json"]
RUIDO = ["", " ", "   ", "abc", "xyz", "0", "1", "2", "3", "9", "99", "-1", "²", "١", "1.5",
         "Revisar señal", "REINICIAR", "Deshacer", "\t", "'; DROP TABLE", "ñandú", "é" * 50]
COMANDOS = ["reiniciar", "deshacer", "salir"]


def generar_secuencia(rnd, ids_opciones):
    pool = ids_opciones * 3 + RUIDO + COMANDOS * 2
    return [rnd.choice(pool) for _ in range(LARGO_SECUENCIA)]


def lector(entradas):
    iterador = iter(entradas)

    def leer(prompt=""):
        try:
            return next(iterador)
        except StopIteration:
            raise EOFError from None

    return leer


def verificar_sesion(datos, secuencia):
    """Devuelve (entradas inválidas comprobadas, lista de fallos)."""
    sesion = motor.Sesion(datos)
    sesion.iniciar()
    escenas = set(sesion.escenas)
    comprobadas, fallos = 0, []
    for paso, entrada in enumerate(secuencia):
        if entrada == "reiniciar":
            sesion.reiniciar()
        elif entrada == "deshacer":
            sesion.deshacer()
        elif entrada == "salir":
            continue
        else:
            antes = (sesion.escena_actual_id, copy.deepcopy(sesion.variables), copy.deepcopy(sesion.instantanea))
            exito, _ = sesion.elegir(entrada)
            if not exito:
                comprobadas += 1
                despues = (sesion.escena_actual_id, sesion.variables, sesion.instantanea)
                if antes != despues:
                    fallos.append(f"paso {paso}: la entrada inválida {entrada!r} alteró el estado")
        if sesion.escena_actual_id not in escenas:
            fallos.append(f"paso {paso}: escena inexistente {sesion.escena_actual_id!r}")
        if not all(isinstance(v, bool) for v in sesion.variables.values()):
            fallos.append(f"paso {paso}: una variable dejó de ser booleana")
    return comprobadas, fallos


def verificar_consola(datos, secuencia):
    """Devuelve None si la consola no lanzó excepciones, o el texto del error."""
    with mock.patch("builtins.input", lector(secuencia)):
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                motor.jugar(datos)
            except EOFError:
                return None  # fin de la entrada: cierre esperado
            except Exception:  # noqa: BLE001 - justamente lo que se quiere detectar
                return traceback.format_exc()
    return None


def main():
    rnd = random.Random(SEMILLA)
    secuencias = excepciones = invalidas_comprobadas = pasos = 0
    fallos_estado = []
    errores_consola = []

    for nombre in HISTORIAS:
        with open(os.path.join(RAIZ, nombre), "r", encoding="utf-8") as f:
            datos = json.load(f)
        ids_opciones = [op["id"] for e in datos["escenas"] for op in e["opciones"]]
        for _ in range(SECUENCIAS_POR_HISTORIA):
            secuencia = generar_secuencia(rnd, ids_opciones)
            secuencias += 1
            pasos += len(secuencia)

            comprobadas, fallos = verificar_sesion(copy.deepcopy(datos), secuencia)
            invalidas_comprobadas += comprobadas
            fallos_estado.extend(f"{nombre} {f}" for f in fallos)

            error = verificar_consola(copy.deepcopy(datos), secuencia)
            if error:
                excepciones += 1
                errores_consola.append(f"{nombre}: {secuencia}\n{error}")

    print("RNF03 - Confiabilidad")
    print(f"  Semilla: {SEMILLA}")
    print(f"  Secuencias ejecutadas: {secuencias} ({SECUENCIAS_POR_HISTORIA} por historia, {len(HISTORIAS)} historias)")
    print(f"  Entradas simuladas: {pasos}")
    print(f"  Entradas inválidas verificadas contra el estado: {invalidas_comprobadas}")
    print(f"  Entradas inválidas que alteraron escena, variables o historial: {len(fallos_estado)}")
    print(f"  Excepciones no controladas en la consola: {excepciones}")
    for texto in fallos_estado[:5]:
        print("   -", texto)
    for texto in errores_consola[:2]:
        print(texto)

    ok = secuencias == 1000 and not fallos_estado and excepciones == 0
    print(f"  RESULTADO: {'CUMPLE' if ok else 'NO CUMPLE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
