"""
============================================================================
RECURSO COMPARTIDO PRINCIPAL - AQUI ESTA LA SECCION CRITICA
============================================================================
"""

import threading
import time


class Inventario:
    """
    El enunciado exige: "La verificacion de existencias y el descuento del
    inventario deben ejecutarse como una sola operacion protegida. Entre ambas
    acciones ningun otro hilo debe poder alterar el mismo inventario."

    CONDICION DE CARRERA QUE SE EVITA (patron check-then-act):
      Sin candado, dos trabajadores pueden leer "quedan 4 monitores" al mismo
      tiempo, los dos concluyen que alcanza, y los dos descuentan. Resultado:
      se venden 8 unidades habiendo 4, y la existencia queda en -4.

    SOLUCION: un unico threading.Lock envuelve validacion + descuento, de modo
    que ambas acciones son indivisibles frente a los demas hilos.

    QUE NO ESTA AQUI ADENTRO (a proposito):
      - La simulacion de trabajo de 0.5 a 2 s (esta en Trabajador, ANTES del
        candado). El enunciado prohibe mantener un lock durante esperas.
      - La escritura en consola (Registro tiene su propio candado).
      Manteniendo el candado solo unos microsegundos, los hilos si trabajan
      realmente en paralelo.
    """

    # Ventana artificial usada unicamente por --sin-lock (ver procesar).
    VENTANA_DEMOSTRACION_S = 0.4

    def __init__(self, productos, proteccion_activa=True):
        self._productos = dict(productos)
        self._existencia_inicial = {c: p.existencia for c, p in self._productos.items()}
        self._unidades_aprobadas = {c: 0 for c in self._productos}

        # El candado del enunciado: mutex/lock explicito.
        self._candado = threading.Lock()

        # False SOLO en el modo demostracion --sin-lock.
        self.proteccion_activa = proteccion_activa

    def procesar(self, pedido):
        """
        SECCION CRITICA. Valida TODAS las lineas del pedido y, solo si todas
        alcanzan, descuenta TODAS. Es todo-o-nada: si una sola linea no tiene
        existencias, no se toca ni un producto (RF-05).

        Devuelve None si el pedido fue APROBADO, o el motivo del RECHAZO.
        """
        if self.proteccion_activa:
            self._candado.acquire()
        try:
            # --- 1. Validar todas las lineas (fase de verificacion) ---
            for linea in pedido.lineas:
                producto = self._productos.get(linea.codigo_producto)
                if producto is None:
                    return "Producto inexistente {}".format(linea.codigo_producto)
                if producto.existencia < linea.cantidad:
                    return ("Stock insuficiente {} (disponible {}, solicitado {})"
                            .format(linea.codigo_producto, producto.existencia,
                                    linea.cantidad))

            # Solo en modo demostracion: ensancha la ventana entre verificar y
            # descontar para que la condicion de carrera se vea. No cambia la
            # logica, solo hace VISIBLE un error que igual existe: sin candado
            # la ventana real es de microsegundos y la corrupcion aparece de
            # forma intermitente, que es lo que hace tan peligrosas a las
            # condiciones de carrera.
            if not self.proteccion_activa:
                # COMPROBACION EXPLICITA de la regla tecnica del enunciado:
                # "No mantenga un lock durante esperas artificiales".
                # Esta espera SOLO existe en el modo demostracion, donde el
                # candado nunca llega a tomarse. La siguiente linea lo verifica
                # en tiempo de ejecucion: si alguna vez el candado estuviera
                # tomado aqui, el programa se detendria con un error en lugar
                # de violar la regla en silencio.
                assert not self._candado.locked(), \
                    "El candado no debe estar tomado durante una espera"
                time.sleep(self.VENTANA_DEMOSTRACION_S)

            # --- 2. Descontar todas las lineas (fase de accion) ---
            for linea in pedido.lineas:
                producto = self._productos[linea.codigo_producto]
                if self.proteccion_activa:
                    producto.descontar(linea.cantidad)
                else:
                    producto.descontar_forzado(linea.cantidad)
                self._unidades_aprobadas[linea.codigo_producto] += linea.cantidad
            return None

        finally:
            # La liberacion va en finally: aunque se lance una excepcion, el
            # candado se libera y ningun hilo queda bloqueado para siempre.
            if self.proteccion_activa:
                self._candado.release()

    def lineas_estado(self):
        """Copia consistente del estado, tomada bajo candado."""
        if self.proteccion_activa:
            self._candado.acquire()
        try:
            filas = []
            for codigo, producto in self._productos.items():
                filas.append(
                    "  {:<6} {:<26} inicial: {:>3}   vendidas: {:>3}   final: {:>3}"
                    .format(codigo, producto.nombre,
                            self._existencia_inicial[codigo],
                            self._unidades_aprobadas[codigo],
                            producto.existencia))
            return filas
        finally:
            if self.proteccion_activa:
                self._candado.release()

    def verificar_invariante(self):
        """
        CRITERIO DE INTEGRIDAD del enunciado:
        existencia final == existencia inicial - unidades realmente aprobadas.
        """
        for codigo, producto in self._productos.items():
            esperado = self._existencia_inicial[codigo] - self._unidades_aprobadas[codigo]
            if producto.existencia != esperado:
                return False
        return True

    def hay_existencias_negativas(self):
        return any(p.existencia < 0 for p in self._productos.values())

    def total_unidades_aprobadas(self):
        return sum(self._unidades_aprobadas.values())
