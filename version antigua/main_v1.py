import json
import copy

# ==========================================
# 1. CLASE EVALUADOR
# ==========================================
class Evaluador:
    def cumple(self, condiciones, variables):
        """Devuelve verdadero o falso según si se cumplen todas las condiciones."""
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
        """Lee el archivo y devuelve la estructura de la historia (diccionarios/datos base)."""
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos


# ==========================================
# 3. CLASE VALIDADOR
# ==========================================
class Validador:
    def validar(self, datos):
        """Devuelve la lista de errores del contenido."""
        errores = []
        
        if not isinstance(datos, dict):
            return ["El archivo JSON raíz debe ser un objeto."]
            
        if "titulo" not in datos:
            errores.append("Falta el campo obligatorio: 'titulo'.")
        if "inicio" not in datos:
            errores.append("Falta el campo obligatorio: 'inicio'.")
        if "escenas" not in datos or not isinstance(datos["escenas"], list):
            errores.append("Falta el campo obligatorio: 'escenas' (debe ser una lista).")
            return errores

        ids_escenas = {escena.get("id") for escena in datos["escenas"] if "id" in escena}
        escena_inicial = datos.get("inicio")

        if escena_inicial and escena_inicial not in ids_escenas:
            errores.append(f"La escena inicial '{escena_inicial}' no existe en la lista de escenas.")

        for index, escena in enumerate(datos.get("escenas", [])):
            escena_id = escena.get("id", f"Índice {index}")
            if "id" not in escena:
                errores.append(f"Una escena en el índice {index} no tiene ID.")
            if "texto" not in escena:
                errores.append(f"La escena '{escena_id}' no tiene texto.")
            
            opciones = escena.get("opciones", [])
            for op in opciones:
                destino = op.get("destino")
                if destino and destino not in ids_escenas:
                    errores.append(f"La opción '{op.get('id')}' en la escena '{escena_id}' apunta a un destino inexistente: '{destino}'.")

        return errores


# ==========================================
# 4. CLASE INTERFAZ CONSOLA
# ==========================================
class InterfazConsola:
    def mostrar(self, escena, opciones):
        """Muestra el texto de la escena y sus opciones."""
        print(f"\n--- {escena.get('id', '')} ---")
        print(escena.get("texto", ""))
        print("\nOpciones:")
        for idx, op in enumerate(opciones, 1):
            print(f"  {idx}. {op['texto']} [ID: {op['id']}]")

    def leer_entrada(self):
        """Lee lo que escribe el lector."""
        return input("\nElige una opción (o escribe 'reiniciar'): ").strip()


# ==========================================
# 5. CLASE SESION (Versión 1 - Sin Deshacer)
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
        """Pone la escena inicial y las variables iniciales."""
        self.variables = copy.deepcopy(self.variables_iniciales)
        self.escena_actual_id = self.inicio

    def opciones_habilitadas(self):
        """Devuelve las opciones cuyas condiciones se cumplen."""
        escena = self.escenas.get(self.escena_actual_id, {})
        opciones = escena.get("opciones", [])
        habilitadas = []
        
        for op in opciones:
            condiciones = op.get("condiciones", {})
            if self.evaluador.cumple(condiciones, self.variables):
                habilitadas.append(op)
        return habilitadas

    def elegir(self, id_opcion):
        """Aplica los efectos y pasa al destino. Rechaza la opción si no existe o no está habilitada."""
        opciones_validas = self.opciones_habilitadas()
        opcion_elegida = None
        
        for op in opciones_validas:
            if op["id"] == id_opcion or op["texto"].lower() == id_opcion.lower():
                opcion_elegida = op
                break
                
        if not opcion_elegida:
            return False, "Opción inválida o no habilitada."

        # Aplicar efectos
        efectos = opcion_elegida.get("efectos", {})
        for clave, valor in efectos.items():
            self.variables[clave] = valor

        # Cambiar al destino
        self.escena_actual_id = opcion_elegida["destino"]
        return True, "Avanzado con éxito."

    def reiniciar(self):
        """Restaura la escena y las variables iniciales."""
        self.iniciar()


# ==========================================
# EJECUCIÓN DE PRUEBA (Main)
# ==========================================
if __name__ == "__main__":
    ruta_archivo = "la_ultima_transmision.json"
    
    cargador = CargadorHistoria()
    validador = Validador()
    
    try:
        datos_json = cargador.cargar(ruta_archivo)
        errores = validador.validar(datos_json)
        
        if errores:
            print("Se encontraron errores en el formato de la historia:")
            for err in errores:
                print(f" - {err}")
        else:
            print(f"¡Historia '{datos_json.get('titulo')}' cargada y validada exitosamente (Versión 1)![cite: 1]")
            
            sesion = Sesion(datos_json)
            sesion.iniciar()
            interfaz = InterfazConsola()
            
            while True:
                escena_actual = sesion.escenas.get(sesion.escena_actual_id)
                opciones = sesion.opciones_habilitadas()
                
                interfaz.mostrar(escena_actual, opciones)
                
                if escena_actual.get("final", False):
                    print("\n--- FIN DE LA HISTORIA ---")
                    break
                
                entrada = interfaz.leer_entrada()
                
                if entrada.lower() == "reiniciar":
                    sesion.reiniciar()
                    print("\n[Juego reiniciado]")
                    continue
                
                id_a_probar = entrada
                if entrada.isdigit() and 1 <= int(entrada) <= len(opciones):
                    id_a_probar = opciones[int(entrada) - 1]["id"]
                
                exito, mensaje = sesion.elegir(id_a_probar)
                if not exito:
                    print(f"\n[Error]: {mensaje}")

    except FileNotFoundError:
        print(f"No se encontró el archivo '{ruta_archivo}'.")