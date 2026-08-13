"""
============================================================================
 NOVATECH - PROCESAMIENTO CONCURRENTE DE PEDIDOS CON HILOS
 Sistemas Operativos - Tarea practica de concurrencia
============================================================================

 Estudiante : Vieri Alexander Ixtecoc Lopez
 Carne      : 1890-23-3479
 Seccion    : A
 Fecha      : 14 de agosto de 2026
 Lenguaje   : Python 3.14 (biblioteca estandar, sin dependencias externas)

----------------------------------------------------------------------------
 HILO PRINCIPAL: carga datos, crea los hilos, los inicia, espera con join,
 envia la senal de cierre al monitor y muestra el resumen final.

 Estructura de hilos:
     1 hilo principal (no cuenta como secundario)
     3 hilos trabajadores  (minimo exigido)
     1 hilo monitor
     -> 4 hilos secundarios en total

 Parametros de ejecucion:
     --workers N   cantidad de trabajadores (por defecto 3).
                   Se usa con 1 para la comparacion de rendimiento.
     --sin-lock    modo DEMOSTRACION: desactiva el candado del inventario
                   para evidenciar la condicion de carrera.
                   NUNCA es el modo normal de operacion.
============================================================================
"""

import argparse
import os
import queue
import threading
import time

from novatech.cargador import ErrorDeCarga, cargar_inventario, cargar_pedidos
from novatech.contadores import Contadores
from novatech.inventario import Inventario
from novatech.monitor import MonitorEstado
from novatech.registro import Registro
from novatech.trabajador import Trabajador

# Rutas relativas a la ubicacion de este archivo, para que el programa
# funcione sin importar desde que carpeta se invoque.
BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_INVENTARIO = os.path.join(BASE, "datos", "inventario.csv")
RUTA_PEDIDOS = os.path.join(BASE, "datos", "pedidos.csv")

TRABAJADORES_POR_DEFECTO = 3


def leer_argumentos():
    analizador = argparse.ArgumentParser(
        description="Simulador concurrente de pedidos NovaTech")
    analizador.add_argument(
        "--workers", type=int, default=TRABAJADORES_POR_DEFECTO,
        help="cantidad de hilos trabajadores (por defecto 3)")
    analizador.add_argument(
        "--sin-lock", action="store_true", dest="sin_lock",
        help="modo demostracion: desactiva el candado del inventario")
    argumentos = analizador.parse_args()
    if argumentos.workers < 1:
        argumentos.workers = 1
    return argumentos


def imprimir_encabezado(registro, inventario, total, validos, trabajadores,
                        proteccion_activa):
    registro.separador()
    registro.plano("  NOVATECH - PROCESAMIENTO CONCURRENTE DE PEDIDOS")
    registro.separador()
    registro.plano("  Trabajadores: {}   |   Monitor: 1   |   "
                   "Hilos secundarios: {}".format(trabajadores, trabajadores + 1))
    registro.plano("  Pedidos cargados: {}  (validos: {}, mal formados: {})"
                   .format(total, validos, total - validos))
    if not proteccion_activa:
        registro.plano("  *** MODO DEMOSTRACION --sin-lock: SIN PROTECCION ***")
        registro.plano("  *** Se espera inventario negativo. No es el modo normal. ***")
    registro.plano("  Inventario inicial:")
    for fila in inventario.lineas_estado():
        registro.plano(fila)
    registro.separador()


def marca(correcto):
    return "[OK]  " if correcto else "[FALLA]"


def imprimir_resumen(registro, inventario, contadores, hilos_secundarios,
                     pedidos_cargados, segundos, proteccion_activa):
    finalizados = sum(1 for hilo in hilos_secundarios if not hilo.is_alive())

    registro.separador()
    registro.plano("RESUMEN FINAL | Procesados: {} | Aprobados: {} | "
                   "Rechazados: {} | Error: {}".format(
                       contadores.procesados, contadores.aprobados,
                       contadores.rechazados, contadores.fallidos))
    registro.plano("Tiempo total: {:.2f} s | Hilos finalizados correctamente: {}/{}"
                   .format(segundos, finalizados, len(hilos_secundarios)))
    registro.separador()

    registro.plano("INVENTARIO FINAL:")
    for fila in inventario.lineas_estado():
        registro.plano(fila)

    registro.separador()
    registro.plano("VERIFICACION DE INTEGRIDAD")

    invariante = inventario.verificar_invariante()
    negativos = inventario.hay_existencias_negativas()
    suma_correcta = (contadores.procesados ==
                     contadores.aprobados + contadores.rechazados
                     + contadores.fallidos)
    sin_duplicados = (contadores.ids_unicos == pedidos_cargados
                      and contadores.procesados == pedidos_cargados)

    registro.plano("{} Invariante: existencia final = inicial - aprobadas   "
                   "(unidades aprobadas: {})".format(
                       marca(invariante), inventario.total_unidades_aprobadas()))
    registro.plano("{} Ningun producto quedo con existencia negativa"
                   .format(marca(not negativos)))
    registro.plano("{} Aprobados + Rechazados + Errores = Procesados"
                   .format(marca(suma_correcta)))
    registro.plano("{} Cada pedido se proceso exactamente una vez  "
                   "({} ids unicos de {} cargados)".format(
                       marca(sin_duplicados), contadores.ids_unicos,
                       pedidos_cargados))
    registro.plano("{} Todos los hilos secundarios finalizaron (cierre limpio)"
                   .format(marca(finalizados == len(hilos_secundarios))))

    incidencias = contadores.incidencias
    if incidencias:
        registro.plano("")
        registro.plano("INCIDENCIAS REGISTRADAS ({}):".format(len(incidencias)))
        for texto in incidencias:
            registro.plano("  - " + texto)

    registro.separador()
    registro.plano("Hilos de la aplicacion aun activos al finalizar:")
    vivos = [h.name for h in threading.enumerate()
             if h.name.startswith("WORKER-") or h.name == "MONITOR"]
    if vivos:
        for nombre in vivos:
            registro.plano("  ADVERTENCIA: sigue vivo el hilo " + nombre)
    else:
        registro.plano("  Ninguno. Total de hilos de la aplicacion activos: 0")
    registro.separador()

    if not proteccion_activa:
        registro.plano("NOTA: ejecucion en modo --sin-lock (demostracion de la")
        registro.plano("condicion de carrera). Los fallos de integridad de arriba")
        registro.plano("son el resultado esperado y prueban que el candado si es")
        registro.plano("necesario.")
        registro.separador()


def main():
    argumentos = leer_argumentos()
    registro = Registro()
    proteccion_activa = not argumentos.sin_lock

    try:
        # ---------- 1. CARGA DE DATOS ----------
        productos = cargar_inventario(RUTA_INVENTARIO)
        pedidos = cargar_pedidos(RUTA_PEDIDOS, set(productos.keys()))
    except ErrorDeCarga as error:
        registro.plano("ERROR DE CARGA: {}".format(error))
        return

    inventario = Inventario(productos, proteccion_activa)
    contadores = Contadores()
    validos = sum(1 for p in pedidos if p.valido)

    imprimir_encabezado(registro, inventario, len(pedidos), validos,
                        argumentos.workers, proteccion_activa)

    # ---------- 2. COLA COMPARTIDA THREAD-SAFE ----------
    cola = queue.Queue()
    for pedido in pedidos:
        cola.put(pedido)

    # ---------- 3. CREACION DE LOS HILOS ----------
    senal_fin = threading.Event()

    trabajadores = [
        Trabajador("WORKER-{}".format(i), cola, inventario, contadores, registro)
        for i in range(1, argumentos.workers + 1)
    ]
    monitor = MonitorEstado(cola, contadores, registro, senal_fin)
    hilos_secundarios = trabajadores + [monitor]

    # ---------- 4. INICIO ----------
    inicio = time.perf_counter()
    monitor.start()
    for trabajador in trabajadores:
        trabajador.start()

    # ---------- 5. ESPERA CON JOIN ----------
    for trabajador in trabajadores:
        trabajador.join()

    # ---------- 6. SENAL DE CIERRE AL MONITOR ----------
    senal_fin.set()
    monitor.join()

    segundos = time.perf_counter() - inicio

    imprimir_resumen(registro, inventario, contadores, hilos_secundarios,
                     len(pedidos), segundos, proteccion_activa)


if __name__ == "__main__":
    main()
