"""
Hilo trabajador: extrae pedidos de la cola y los procesa.
"""

import queue
import random
import threading
import time

from .cargador import PedidoInvalidoError


class Trabajador(threading.Thread):
    """
    HILO TRABAJADOR (se crean 3 como minimo).

    Ciclo de vida:
      1. Toma un pedido de la cola compartida.
      2. Simula entre 0.5 y 2 s de trabajo  <-- FUERA de la seccion critica.
      3. Valida y descuenta inventario      <-- DENTRO de la seccion critica.
      4. Registra el resultado.
      5. Termina cuando la cola queda vacia.

    COMO SE EVITA QUE DOS TRABAJADORES TOMEN EL MISMO PEDIDO:
      La cola es un queue.Queue, estructura thread-safe de la biblioteca
      estandar. Su operacion get() es atomica: si dos hilos la invocan a la
      vez, uno obtiene el pedido y el otro obtiene el siguiente o la
      excepcion Empty. Nunca el mismo objeto dos veces.
      Ademas se lleva un conjunto de ids ya tomados como segunda verificacion.

    COMO SE EVITA QUEDAR BLOQUEADO:
      Se usa get(timeout=...) en lugar de get() sin argumentos. Un get()
      bloqueante esperaria para siempre al vaciarse la cola y el programa
      nunca terminaria. Con timeout, si pasan 0.4 s sin pedidos se concluye
      que ya no quedan pendientes y el hilo sale de forma limpia.
    """

    ESPERA_COLA_S = 0.4
    SIMULACION_MINIMA_S = 0.5
    SIMULACION_MAXIMA_S = 2.0

    def __init__(self, nombre, cola, inventario, contadores, registro):
        super().__init__(name=nombre)
        self.cola = cola
        self.inventario = inventario
        self.contadores = contadores
        self.registro = registro
        self.pedidos_atendidos = 0
        self._azar = random.Random()

    def run(self):
        while True:
            try:
                pedido = self.cola.get(timeout=self.ESPERA_COLA_S)
            except queue.Empty:
                break  # cola vacia: no quedan pedidos pendientes
            try:
                self._atender(pedido)
            finally:
                self.cola.task_done()

        self.registro.linea(
            self.name,
            "Sin pedidos pendientes. Hilo finalizado. Atendidos: {}".format(
                self.pedidos_atendidos))

    def _atender(self, pedido):
        self.contadores.entra_trabajador()
        try:
            # Segunda barrera contra duplicados (RF-02).
            if not self.contadores.marcar_tomado(pedido.id):
                self.contadores.registrar_incidencia(
                    "Pedido duplicado detectado: " + pedido.id)
                self.registro.linea(
                    self.name, pedido.id + " DESCARTADO | Ya habia sido procesado")
                self.contadores.sumar_fallido()
                self.contadores.sumar_procesado()
                return

            self.registro.linea(
                self.name,
                "Inicia pedido {} | Cliente: {}".format(pedido.id, pedido.cliente))

            # ---- RF-04: simulacion de trabajo FUERA de la seccion critica ----
            duracion = self._azar.uniform(self.SIMULACION_MINIMA_S,
                                          self.SIMULACION_MAXIMA_S)
            time.sleep(duracion)
            # ------------------------------------------------------------------

            if not pedido.valido:
                raise PedidoInvalidoError(pedido.motivo_error)

            # ---- Seccion critica (dentro de Inventario.procesar) ----
            motivo_rechazo = self.inventario.procesar(pedido)
            # ---------------------------------------------------------

            if motivo_rechazo is None:
                self.contadores.sumar_aprobado()
                self.registro.linea(
                    self.name,
                    "{} APROBADO | Cliente: {} | {}".format(
                        pedido.id, pedido.cliente, pedido.detalle_lineas()))
            else:
                self.contadores.sumar_rechazado()
                self.registro.linea(
                    self.name, "{} RECHAZADO | Cliente: {} | Motivo: {}".format(
                        pedido.id, pedido.cliente, motivo_rechazo))

            self.contadores.sumar_procesado()
            self.pedidos_atendidos += 1

        except PedidoInvalidoError as error:
            # RF-08 / CP-04: el error se controla aqui y los demas hilos siguen.
            self.contadores.sumar_fallido()
            self.contadores.sumar_procesado()
            self.pedidos_atendidos += 1
            self.contadores.registrar_incidencia(
                "{}: {}".format(pedido.id, error))
            self.registro.linea(
                self.name,
                "{} ERROR | Cliente: {} | Pedido mal formado: {}".format(
                    pedido.id, pedido.cliente, error))

        except Exception as error:  # red de seguridad
            # Ninguna excepcion inesperada puede matar al hilo ni detener a
            # los demas trabajadores.
            self.contadores.sumar_fallido()
            self.contadores.sumar_procesado()
            self.pedidos_atendidos += 1
            self.contadores.registrar_incidencia(
                "{}: {}".format(pedido.id, error))
            self.registro.linea(
                self.name, "{} ERROR | Cliente: {} | {}".format(
                    pedido.id, pedido.cliente, error))

        finally:
            self.contadores.sale_trabajador()
