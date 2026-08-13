"""
Registro de eventos con marca de tiempo.
"""

import threading
from datetime import datetime


class Registro:
    """
    Escribe en consola en el formato que pide el enunciado:

        [10:14:02.351] [WORKER-2] Inicia pedido ORD-007 | Cliente: Ana Lopez

    DECISION IMPORTANTE:
    Esta clase usa su PROPIO candado (_candado_salida), separado del candado
    del inventario. Escribir en consola es una operacion de entrada/salida
    lenta, y la regla tecnica del enunciado prohibe mantener un lock durante
    operaciones lentas de E/S. Si se usara el mismo candado del inventario,
    cada impresion bloquearia a todos los trabajadores y el programa se
    volveria secuencial.

    El candado si es necesario aqui: sin el, dos hilos que imprimen a la vez
    pueden entremezclar sus lineas y la evidencia quedaria ilegible.
    """

    def __init__(self):
        self._candado_salida = threading.Lock()

    def linea(self, etiqueta, mensaje):
        """Linea con marca de tiempo y etiqueta de hilo."""
        hora = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # milisegundos
        with self._candado_salida:
            print("[{}] [{}] {}".format(hora, etiqueta, mensaje))

    def plano(self, mensaje):
        """Linea sin marca de tiempo (monitor, encabezados y resumen final)."""
        with self._candado_salida:
            print(mensaje)

    def separador(self):
        self.plano("-" * 68)
