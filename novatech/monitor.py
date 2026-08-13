"""
Hilo monitor: reporta periodicamente el estado del sistema.
"""

import threading


class MonitorEstado(threading.Thread):
    """
    HILO MONITOR (1).

    Muestra cada 1.5 s: pendientes, aprobados, rechazados, errores y
    trabajadores activos (RF-07).

    COMO SE LE AVISA QUE DEBE TERMINAR:
      Con un threading.Event que funciona como senal. El hilo principal, al
      terminar el join de todos los trabajadores, llama a senal_fin.set().

      La clave esta en senal_fin.wait(1.5):
        - devuelve False si se cumplio el tiempo  -> imprime otra vez
        - devuelve True  si llego la senal        -> sale del bucle de inmediato

      Por eso NO se usa time.sleep(1.5): con sleep el monitor seguiria
      dormido hasta 1.5 s despues de que todo termino, retrasando el cierre.
      Tampoco se usa un hilo daemon abandonado: el enunciado exige cierre
      limpio, y a este hilo tambien se le hace join().
    """

    INTERVALO_S = 1.5  # dentro del rango de 1 a 2 s que pide el enunciado

    def __init__(self, cola, contadores, registro, senal_fin):
        super().__init__(name="MONITOR")
        self.cola = cola
        self.contadores = contadores
        self.registro = registro
        self.senal_fin = senal_fin
        self.reportes = 0

    def run(self):
        while not self.senal_fin.wait(self.INTERVALO_S):
            self.reportes += 1
            self.registro.plano(
                "[MONITOR] Pendientes: {} | Aprobados: {} | Rechazados: {} "
                "| Errores: {} | Activos: {}".format(
                    self.cola.qsize(),
                    self.contadores.aprobados,
                    self.contadores.rechazados,
                    self.contadores.fallidos,
                    self.contadores.trabajadores_activos))

        self.registro.plano(
            "[MONITOR] Senal de finalizacion recibida. "
            "Monitor detenido tras {} reportes.".format(self.reportes))
