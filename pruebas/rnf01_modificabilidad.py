"""Verificación del RNF01 (modificabilidad del contenido).

Requisito: agregar una escena nueva con dos opciones a una historia existente exige
modificar solo el archivo de historia (0 archivos de código cambiados) y toma 10 minutos
o menos siguiendo el README.

Qué comprueba este script (la parte automática):
  1. Parte de la historia original y le agrega UNA escena nueva con DOS opciones, editando
     solo el JSON (copia temporal).
  2. El motor, sin tocarlo, carga, valida y recorre esa historia modificada.
  3. El archivo main.py tiene el mismo hash SHA-256 antes y después (0 archivos de código
     cambiados).

Qué NO puede comprobar: el tiempo (<= 10 minutos). Se mide a mano, siguiendo el README, y
se anota en el informe. Para la parte de Git se usa, además:
    git diff --stat        (debe listar solo el archivo .json)

Ejecutar desde la carpeta del proyecto:
    python pruebas/rnf01_modificabilidad.py
"""
import copy
import hashlib
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import main as motor  # noqa: E402


def sha256(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    ruta_motor = os.path.join(RAIZ, "main.py")
    ruta_historia = os.path.join(RAIZ, "la_ultima_transmision.json")
    hash_antes = sha256(ruta_motor)

    with open(ruta_historia, "r", encoding="utf-8") as f:
        datos = json.load(f)

    modificada = copy.deepcopy(datos)
    modificada["escenas"].append({
        "id": "E7",
        "texto": "Antes de decidir, la operadora escucha una segunda grabación en la cinta.",
        "final": False,
        "opciones": [
            {"id": "escuchar_cinta", "texto": "Escuchar la cinta completa",
             "destino": "E4", "condiciones": {}, "efectos": {"conoce_origen": True}},
            {"id": "apagar_cinta", "texto": "Apagar la cinta",
             "destino": "E6", "condiciones": {}, "efectos": {}},
        ],
    })
    for opcion in modificada["escenas"][1]["opciones"]:  # E2: ambas rutas pasan por E7
        if opcion["id"] == "continuar":
            opcion["destino"] = "E7"

    with tempfile.TemporaryDirectory() as carpeta:
        ruta_modificada = os.path.join(carpeta, "historia_modificada.json")
        with open(ruta_modificada, "w", encoding="utf-8") as f:
            json.dump(modificada, f, ensure_ascii=False, indent=2)

        datos_cargados, errores = motor.cargar_historia(ruta_modificada)
        carga_ok = errores == []

        sesion = motor.Sesion(datos_cargados)
        sesion.iniciar()
        for id_opcion in ("revisar", "continuar"):
            sesion.elegir(id_opcion)
        llega_a_e7 = sesion.escena_actual_id == "E7"
        dos_opciones = len(sesion.opciones_habilitadas()) == 2
        sesion.elegir("escuchar_cinta")
        llega_a_final = sesion.escena_actual_id == "E4" and sesion.escena_actual()["final"]

    hash_despues = sha256(ruta_motor)
    codigo_sin_cambios = hash_antes == hash_despues

    print("RNF01 - Modificabilidad del contenido")
    print(f"  Escena nueva agregada: E7 (2 opciones), editando solo el JSON")
    print(f"  El motor carga y valida la historia modificada: {'sí' if carga_ok else 'NO'}")
    print(f"  La nueva escena es alcanzable y muestra 2 opciones: {'sí' if llega_a_e7 and dos_opciones else 'NO'}")
    print(f"  Se llega a un final desde la escena nueva: {'sí' if llega_a_final else 'NO'}")
    print(f"  main.py SHA-256 antes:   {hash_antes}")
    print(f"  main.py SHA-256 después: {hash_despues}")
    print(f"  Archivos de código cambiados: {0 if codigo_sin_cambios else 1}")
    print("  Tiempo (<= 10 min): se mide a mano siguiendo el README (no lo mide este script).")

    ok = carga_ok and llega_a_e7 and dos_opciones and llega_a_final and codigo_sin_cambios
    print(f"  RESULTADO (parte automática): {'CUMPLE' if ok else 'NO CUMPLE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
