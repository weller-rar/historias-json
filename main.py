import copy
import json
import sys

RUTA_POR_DEFECTO = "la_ultima_transmision.json"


# ==========================================
# 0. ERROR CONTROLADO DE CARGA
# ==========================================
class ErrorCarga(Exception):
    """Error esperado al leer el archivo de la historia (no es un fallo del programa)."""


# ==========================================
# 1. CLASE EVALUADOR
# ==========================================
class Evaluador:
    def cumple(self, condiciones, variables):
        """Devuelve verdadero si se cumplen todas las condiciones (mapa vacío = habilitada)."""
        if not condiciones:
            return True
        for clave, valor_esperado in condiciones.items():
            if variables.get(clave) != valor_esperado:
                return False
        return True


# ==========================================
# 2. CLASE CARGADOR HISTORIA
# ==========================================
class CargadorHistoria:
    def cargar(self, ruta):
        """Lee el archivo y devuelve los datos. Lanza ErrorCarga con un mensaje claro si falla."""
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ErrorCarga(f"No se encontró el archivo '{ruta}'.") from None
        except PermissionError:
            raise ErrorCarga(f"No hay permiso para leer el archivo '{ruta}'.") from None
        except json.JSONDecodeError as e:
            raise ErrorCarga(
                f"El archivo '{ruta}' no es un JSON válido "
                f"(línea {e.lineno}, columna {e.colno}): {e.msg}."
            ) from None
        except UnicodeDecodeError:
            raise ErrorCarga(f"El archivo '{ruta}' no está codificado en UTF-8.") from None
        except OSError as e:
            raise ErrorCarga(f"No se pudo leer '{ruta}': {e.strerror or e}.") from None


# ==========================================
# 3. CLASE VALIDADOR
# ==========================================
class Validador:
    def validar(self, datos):
        """Devuelve la lista de errores del contenido. Lista vacía = historia válida."""
        errores = []

        if not isinstance(datos, dict):
            return ["El archivo JSON raíz debe ser un objeto."]

        # --- Campos obligatorios de la historia ---
        for campo in ("titulo", "inicio", "variables", "escenas"):
            if campo not in datos:
                errores.append(f"Falta el campo obligatorio raíz: '{campo}'.")

        if "titulo" in datos and not isinstance(datos["titulo"], str):
            errores.append("El campo 'titulo' debe ser texto.")

        # --- Variables declaradas ---
        declaradas = {}
        if "variables" in datos:
            if not isinstance(datos["variables"], dict):
                errores.append("El campo 'variables' debe ser un objeto (mapa de booleanos).")
            else:
                declaradas = datos["variables"]
                for nombre, valor in declaradas.items():
                    if not isinstance(valor, bool):
                        errores.append(
                            f"La variable inicial '{nombre}' debe tener un valor booleano (true/false)."
                        )

        if "escenas" not in datos:
            return errores
        escenas = datos["escenas"]
        if not isinstance(escenas, list):
            errores.append("El campo 'escenas' debe ser una lista.")
            return errores

        ids_escenas = {
            e["id"] for e in escenas if isinstance(e, dict) and isinstance(e.get("id"), str)
        }

        # --- Escena inicial ---
        if "inicio" in datos:
            if not isinstance(datos["inicio"], str):
                errores.append("El campo 'inicio' debe ser el ID de una escena (texto).")
            elif datos["inicio"] not in ids_escenas:
                errores.append(
                    f"La escena inicial '{datos['inicio']}' no existe en la lista de escenas."
                )

        # --- Escenas ---
        ids_vistos = set()
        for index, escena in enumerate(escenas):
            if not isinstance(escena, dict):
                errores.append(f"La escena en el índice {index} no es un objeto válido.")
                continue

            if "id" not in escena:
                errores.append(f"Una escena en el índice {index} no tiene el campo obligatorio 'id'.")
                continue
            if not isinstance(escena["id"], str):
                errores.append(f"El 'id' de la escena en el índice {index} debe ser texto.")
                continue

            escena_id = escena["id"]
            if escena_id in ids_vistos:
                errores.append(f"ID de escena duplicado: '{escena_id}'.")
            ids_vistos.add(escena_id)

            if "texto" not in escena:
                errores.append(f"La escena '{escena_id}' no tiene el campo obligatorio 'texto'.")
            elif not isinstance(escena["texto"], str):
                errores.append(f"El campo 'texto' de la escena '{escena_id}' debe ser texto.")

            es_final = None
            if "final" not in escena:
                errores.append(f"La escena '{escena_id}' no tiene el campo obligatorio 'final'.")
            elif not isinstance(escena["final"], bool):
                errores.append(f"El campo 'final' de la escena '{escena_id}' debe ser booleano.")
            else:
                es_final = escena["final"]

            if "opciones" not in escena:
                errores.append(f"La escena '{escena_id}' no tiene el campo obligatorio 'opciones'.")
                continue
            opciones = escena["opciones"]
            if not isinstance(opciones, list):
                errores.append(f"El campo 'opciones' de la escena '{escena_id}' debe ser una lista.")
                continue

            if es_final is True and len(opciones) > 0:
                errores.append(f"La escena final '{escena_id}' no debe tener opciones.")
            if es_final is False and len(opciones) == 0:
                errores.append(f"La escena no final '{escena_id}' debe tener al menos una opción.")

            self._validar_opciones(escena_id, opciones, ids_escenas, declaradas, errores)

        return errores

    def _validar_opciones(self, escena_id, opciones, ids_escenas, declaradas, errores):
        ids_opciones = set()
        for op_idx, op in enumerate(opciones):
            if not isinstance(op, dict):
                errores.append(f"Una opción de la escena '{escena_id}' (índice {op_idx}) no es un objeto válido.")
                continue

            op_id = op.get("id")
            etiqueta = op_id if isinstance(op_id, str) else f"índice {op_idx}"

            if "id" not in op:
                errores.append(f"Una opción de la escena '{escena_id}' (índice {op_idx}) no tiene el campo 'id'.")
            elif not isinstance(op_id, str):
                errores.append(f"El 'id' de la opción en el índice {op_idx} de la escena '{escena_id}' debe ser texto.")
            else:
                if op_id in ids_opciones:
                    errores.append(f"ID de opción duplicado '{op_id}' dentro de la escena '{escena_id}'.")
                ids_opciones.add(op_id)

            if "texto" not in op:
                errores.append(f"La opción '{etiqueta}' de la escena '{escena_id}' no tiene 'texto'.")
            elif not isinstance(op["texto"], str):
                errores.append(f"El 'texto' de la opción '{etiqueta}' de la escena '{escena_id}' debe ser texto.")

            if "destino" not in op:
                errores.append(f"La opción '{etiqueta}' de la escena '{escena_id}' no tiene 'destino'.")
            elif not isinstance(op["destino"], str):
                errores.append(f"El 'destino' de la opción '{etiqueta}' de la escena '{escena_id}' debe ser texto.")
            elif op["destino"] not in ids_escenas:
                errores.append(
                    f"La opción '{etiqueta}' de la escena '{escena_id}' apunta a un destino inexistente: '{op['destino']}'."
                )

            self._validar_mapa(op.get("condiciones", {}), "condiciones", etiqueta, escena_id, declaradas, errores)
            self._validar_mapa(op.get("efectos", {}), "efectos", etiqueta, escena_id, declaradas, errores)

    def _validar_mapa(self, mapa, campo, op_etiqueta, escena_id, declaradas, errores):
        """Valida un mapa de condiciones o de efectos (variables declaradas y valores booleanos)."""
        if not isinstance(mapa, dict):
            errores.append(f"El campo '{campo}' de la opción '{op_etiqueta}' (escena '{escena_id}') debe ser un objeto.")
            return
        for variable, valor in mapa.items():
            if variable not in declaradas:
                errores.append(
                    f"La variable '{variable}' usada en '{campo}' de la opción '{op_etiqueta}' "
                    f"(escena '{escena_id}') no está declarada en 'variables'."
                )
            if not isinstance(valor, bool):
                errores.append(
                    f"El valor de '{variable}' en '{campo}' de la opción '{op_etiqueta}' "
                    f"(escena '{escena_id}') debe ser booleano."
                )


# ==========================================
# 4. CLASE INTERFAZ CONSOLA
# ==========================================
class InterfazConsola:
    def mostrar(self, escena, opciones):
        """Muestra el texto de la escena y sus opciones."""
        print(f"\n--- Escena: {escena.get('id', '')} ---")
        print(escena.get("texto", ""))
        if opciones:
            print("\nOpciones:")
            for idx, op in enumerate(opciones, 1):
                print(f"  {idx}. {op['texto']} [ID: {op['id']}]")

    def leer_entrada(self):
        """Lee lo que escribe el lector."""
        return input("\nElige una opción (o escribe 'reiniciar' / 'salir'): ").strip()


# ==========================================
# 5. CLASE SESION
# ==========================================
class Sesion:
    def __init__(self, datos_historia):
        self.datos = datos_historia
        self.titulo = datos_historia.get("titulo", "")
        self.inicio = datos_historia.get("inicio", "")
        self.variables_iniciales = datos_historia.get("variables", {})

        self.escenas = {escena["id"]: escena for escena in datos_historia.get("escenas", [])}
        self.evaluador = Evaluador()

        self.escena_actual_id = None
        self.variables = {}

    def iniciar(self):
        """Pone la escena inicial y las variables iniciales (sin modificar las del archivo)."""
        self.variables = copy.deepcopy(self.variables_iniciales)
        self.escena_actual_id = self.inicio

    def escena_actual(self):
        return self.escenas[self.escena_actual_id]

    def opciones_habilitadas(self):
        """Devuelve las opciones de la escena actual cuyas condiciones se cumplen."""
        opciones = self.escena_actual().get("opciones", [])
        return [
            op for op in opciones
            if self.evaluador.cumple(op.get("condiciones", {}), self.variables)
        ]

    def elegir(self, id_opcion):
        """Aplica los efectos y pasa al destino usando el ID de la opción.

        Si la opción no existe o no está habilitada, no cambia nada.
        """
        opcion_elegida = None
        for op in self.opciones_habilitadas():
            if op["id"] == id_opcion:
                opcion_elegida = op
                break

        if opcion_elegida is None:
            return False, "Opción inválida, inexistente o no habilitada por condiciones."

        for clave, valor in opcion_elegida.get("efectos", {}).items():
            self.variables[clave] = valor

        self.escena_actual_id = opcion_elegida["destino"]
        return True, "Avanzado con éxito."

    def reiniciar(self):
        """Restaura la escena y las variables iniciales."""
        self.iniciar()


# ==========================================
# 6. BUCLE DE JUEGO Y MAIN
# ==========================================
def cargar_historia(ruta):
    """Carga y valida. Devuelve (datos, errores). Lanza ErrorCarga si el archivo no se puede leer."""
    datos = CargadorHistoria().cargar(ruta)
    return datos, Validador().validar(datos)


def jugar(datos):
    """Bucle de la partida por consola."""
    sesion = Sesion(datos)
    sesion.iniciar()
    interfaz = InterfazConsola()

    while True:
        escena = sesion.escena_actual()
        opciones = sesion.opciones_habilitadas()
        interfaz.mostrar(escena, opciones)

        if escena["final"]:
            print("\n--- FIN DE LA HISTORIA ---")
            decision = input("¿Iniciar otra partida? (escribe 'reiniciar' o 'salir'): ").strip().lower()
            if decision == "reiniciar":
                sesion.reiniciar()
                print("\n[Nueva partida iniciada]")
                continue
            print("\n¡Gracias por jugar!")
            return

        if not opciones:
            print("\n[BLOQUEO]: esta escena no es final, pero no hay opciones disponibles con las variables actuales.")
            decision = input("Escribe 'reiniciar' para empezar de nuevo o 'salir' para terminar: ").strip().lower()
            if decision == "reiniciar":
                sesion.reiniciar()
                print("\n[Juego reiniciado]")
                continue
            return

        entrada = interfaz.leer_entrada()
        comando = entrada.lower()

        if comando == "salir":
            print("\n¡Hasta luego!")
            return
        if comando == "reiniciar":
            sesion.reiniciar()
            print("\n[Juego reiniciado]")
            continue

        id_a_probar = entrada
        if entrada.isdecimal() and 1 <= int(entrada) <= len(opciones):
            id_a_probar = opciones[int(entrada) - 1]["id"]

        exito, mensaje = sesion.elegir(id_a_probar)
        if not exito:
            print(f"\n[Error]: {mensaje}")


def main(argv=None):
    argv = sys.argv if argv is None else argv
    ruta = argv[1] if len(argv) > 1 else RUTA_POR_DEFECTO

    try:
        datos, errores = cargar_historia(ruta)
    except ErrorCarga as e:
        print(f"Error: {e}")
        return 1

    if errores:
        print(f"La historia '{ruta}' no es válida y no se puede jugar. Corrige estos errores:")
        for err in errores:
            print(f" - {err}")
        return 1

    print(f"¡Historia '{datos['titulo']}' cargada y validada exitosamente!")
    try:
        jugar(datos)
    except (EOFError, KeyboardInterrupt):
        print("\n¡Hasta luego!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
