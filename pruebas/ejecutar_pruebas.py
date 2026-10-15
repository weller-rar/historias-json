"""Ejecuta todas las pruebas y guarda el registro de la ejecución en registro_pruebas.txt.

Incluye: pruebas automatizadas U1 a U6 e I1 (unittest), RNF01 (parte automática) y RNF03.
El RNF02 está cubierto por las pruebas U4.

Uso, desde la carpeta del proyecto:
    python pruebas/ejecutar_pruebas.py

El archivo registro_pruebas.txt describe la ejecución real en el equipo donde se corrió
(fecha, versión de Python y sistema operativo quedan registrados al inicio).
"""
import datetime
import os
import platform
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "registro_pruebas.txt")

PASOS = [
    ("PRUEBAS AUTOMATIZADAS U1 a U6 e I1 (unittest)  |  RNF02 se verifica en U4",
     ["-m", "unittest", "discover", "pruebas", "-v"]),
    ("RNF01 - MODIFICABILIDAD DEL CONTENIDO (parte automática)",
     [os.path.join("pruebas", "rnf01_modificabilidad.py")]),
    ("RNF03 - CONFIABILIDAD (1.000 secuencias aleatorias)",
     [os.path.join("pruebas", "rnf03_confiabilidad.py")]),
]


def correr(args):
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    proceso = subprocess.run(
        [sys.executable] + args, cwd=RAIZ, env=entorno,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, encoding="utf-8", errors="replace",
    )
    return proceso.returncode, proceso.stdout


def main():
    lineas = [
        "REGISTRO DE EJECUCIÓN DE PRUEBAS - La última transmisión",
        f"Fecha y hora: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Python: {platform.python_version()}",
        f"Sistema operativo: {platform.platform()}",
        f"Carpeta: {RAIZ}",
        "",
    ]
    resumen = []
    for titulo, args in PASOS:
        codigo, salida = correr(args)
        lineas += ["=" * 78, titulo, "=" * 78, salida.rstrip(), ""]
        resumen.append((titulo.split("  |")[0], codigo))

    lineas += ["=" * 78, "RESUMEN", "=" * 78]
    for titulo, codigo in resumen:
        lineas.append(f"{'PASA ' if codigo == 0 else 'FALLA'}  {titulo}")
    todo_ok = all(codigo == 0 for _, codigo in resumen)
    lineas.append(f"RESULTADO GENERAL: {'TODO PASA' if todo_ok else 'HAY FALLOS'}")

    texto = "\n".join(lineas) + "\n"
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)
    print(f"Registro guardado en: {SALIDA}")
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
