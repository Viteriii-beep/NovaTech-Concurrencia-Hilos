"""
Contadores compartidos por todos los hilos.
"""

import threading


class Contadores:
    """
    Se protegen con un threading.Lock porque "contador += 1" NO es atomico:
    son tres operaciones (leer, sumar, escribir). Con tres trabajadores
    sumando a la vez se pueden perder incrementos y el resumen final saldria
    con totales menores a los reales.

    ids_procesados garantiza que ningun pedido se contabilice dos veces
    (RF-02): marcar_tomado devuelve False si el id ya estaba registrado.
    """

    def __init__(self):
        self._candado = threading.Lock()
        self._aprobados = 0
        self._rechazados = 0
        self._fallidos = 0
        self._procesados = 0
        self._trabajadores_activos = 0
        self._ids_procesados = set()
        self._incidencias = []

    def marcar_tomado(self, id_pedido):
        """Devuelve True si es la primera vez que se toma este pedido."""
        with self._candado:
            if id_pedido in self._ids_procesados:
                return False
            self._ids_procesados.add(id_pedido)
            return True

    def sumar_aprobado(self):
        with self._candado:
            self._aprobados += 1

    def sumar_rechazado(self):
        with self._candado:
            self._rechazados += 1

    def sumar_fallido(self):
        with self._candado:
            self._fallidos += 1

    def sumar_procesado(self):
        with self._candado:
            self._procesados += 1

    def entra_trabajador(self):
        with self._candado:
            self._trabajadores_activos += 1

    def sale_trabajador(self):
        with self._candado:
            self._trabajadores_activos -= 1

    def registrar_incidencia(self, texto):
        with self._candado:
            self._incidencias.append(texto)

    # ---- Lecturas (tambien bajo candado, para leer valores consistentes) ----

    @property
    def aprobados(self):
        with self._candado:
            return self._aprobados

    @property
    def rechazados(self):
        with self._candado:
            return self._rechazados

    @property
    def fallidos(self):
        with self._candado:
            return self._fallidos

    @property
    def procesados(self):
        with self._candado:
            return self._procesados

    @property
    def trabajadores_activos(self):
        with self._candado:
            return self._trabajadores_activos

    @property
    def ids_unicos(self):
        with self._candado:
            return len(self._ids_procesados)

    @property
    def incidencias(self):
        with self._candado:
            return list(self._incidencias)
