"""
Modelo de datos del simulador NovaTech.

Contiene las estructuras basicas: estados posibles, productos del inventario,
lineas de pedido y pedidos.
"""

from enum import Enum


class Estado(Enum):
    """
    Resultado posible de un pedido.

    Son TRES categorias distintas, no dos. El enunciado las separa:
        "Procesados: 20 | Aprobados: 15 | Rechazados: 4 | Error: 1"

    RECHAZADO -> el pedido estaba bien formado pero no habia existencias.
    FALLIDO   -> el pedido venia mal formado (CP-04). No es lo mismo.
    """

    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    FALLIDO = "ERROR"


class Producto:
    """
    Producto del inventario compartido.

    IMPORTANTE: esta clase NO es thread-safe por si misma y no debe serlo.
    Toda lectura o modificacion de 'existencia' se realiza unicamente desde
    la clase Inventario, que es quien posee el candado (threading.Lock).
    Concentrar el candado en un solo lugar evita candados anidados y bloqueos.
    """

    def __init__(self, codigo, nombre, existencia):
        self.codigo = codigo
        self.nombre = nombre
        self.existencia = existencia

    def descontar(self, cantidad):
        """
        Descuenta unidades. Red de seguridad: si alguna vez se intentara dejar
        el inventario en negativo, se lanza excepcion en lugar de corromper
        el dato silenciosamente.
        """
        if cantidad > self.existencia:
            raise RuntimeError(
                "Intento de dejar inventario negativo en {} "
                "(existencia {}, descuento {})".format(
                    self.codigo, self.existencia, cantidad
                )
            )
        self.existencia -= cantidad

    def descontar_forzado(self, cantidad):
        """
        Descuento SIN la red de seguridad. Se usa unicamente en el modo de
        demostracion --sin-lock, cuyo proposito es EXPONER la condicion de
        carrera y dejar que el inventario quede negativo, que es justamente
        el resultado incorrecto que el informe tecnico debe explicar.
        El modo normal del programa jamas llama a este metodo.
        """
        self.existencia -= cantidad

    def __str__(self):
        return "{} - {}".format(self.codigo, self.nombre)


class LineaPedido:
    """
    Una linea de un pedido: un producto y la cantidad solicitada.
    Es inmutable en la practica, por lo que puede compartirse entre hilos.
    """

    def __init__(self, codigo_producto, cantidad):
        self.codigo_producto = codigo_producto
        self.cantidad = cantidad

    def __str__(self):
        return "{}: -{} unidades".format(self.codigo_producto, self.cantidad)


class Pedido:
    """
    Pedido de NovaTech.

    El enunciado dice: "uno o MAS productos con su cantidad solicitada".
    Por eso guarda una LISTA de lineas, no un solo producto. Esto obliga a que
    la validacion y el descuento sean TODO-O-NADA dentro de la misma seccion
    critica (ver Inventario.procesar).

    Una vez creado no se modifica, por lo que puede pasar de un hilo a otro
    a traves de la cola sin necesidad de sincronizacion adicional.
    """

    def __init__(self, id_pedido, cliente, lineas, valido, motivo_error):
        self.id = id_pedido
        self.cliente = cliente
        self.lineas = tuple(lineas)          # tupla = no se puede modificar
        self.valido = valido
        self.motivo_error = motivo_error

    @classmethod
    def crear_valido(cls, id_pedido, cliente, lineas):
        """Crea un pedido bien formado."""
        return cls(id_pedido, cliente, lineas, True, None)

    @classmethod
    def crear_invalido(cls, id_pedido, cliente, motivo_error):
        """
        Crea un pedido mal formado. NO se descarta al cargar: entra igual a la
        cola para que un trabajador lo tome y falle de forma controlada
        (RF-08 y CP-04). Asi ademas se cumple que procesados == cargados.
        """
        return cls(id_pedido, cliente, [], False, motivo_error)

    def detalle_lineas(self):
        """Texto para el log de aprobacion: 'P002: -2 unidades | P003: -1 unidades'."""
        return " | ".join(str(linea) for linea in self.lineas)

    def total_unidades(self):
        return sum(linea.cantidad for linea in self.lineas)

    def __str__(self):
        return "{} ({})".format(self.id, self.cliente)
