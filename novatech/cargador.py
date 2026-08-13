"""
Carga del inventario y de los pedidos desde archivos CSV.

Se eligio CSV (permitido por el enunciado junto a memoria, JSON o base de
datos) porque se lee con la biblioteca estandar de Python: el proyecto no
necesita ninguna dependencia externa y corre en cualquier maquina con Python.

Los pedidos mal formados NO se descartan: se convierten en Pedido invalido
y entran igual a la cola, para que un trabajador falle de forma controlada
(RF-08 / CP-04) y para que se cumpla procesados == cargados.
"""

from .modelo import LineaPedido, Pedido, Producto


class PedidoInvalidoError(Exception):
    """
    Se lanza cuando un trabajador toma un pedido mal formado.

    Es una excepcion propia y no una generica para poder capturarla de forma
    especifica en el trabajador y contarla como FALLIDO, sin confundirla con
    un rechazo por falta de stock.
    """
    pass


class ErrorDeCarga(Exception):
    """Error irrecuperable al leer los archivos de datos."""
    pass


def _lineas_utiles(ruta, prefijo_encabezado):
    """Lee el archivo y descarta vacias, comentarios (#) y el encabezado."""
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            for numero, linea in enumerate(archivo, start=1):
                texto = linea.strip()
                if not texto or texto.startswith("#"):
                    continue
                if texto.lower().startswith(prefijo_encabezado):
                    continue
                yield numero, texto
    except FileNotFoundError:
        raise ErrorDeCarga(
            "No se encontro el archivo: {}\n"
            "Verifique que exista la carpeta 'datos' junto a main.py.".format(ruta))


def cargar_inventario(ruta):
    """Devuelve un diccionario {codigo: Producto}."""
    inventario = {}
    for _, texto in _lineas_utiles(ruta, "codigo,"):
        campos = texto.split(",")
        if len(campos) < 3:
            raise ErrorDeCarga("Linea de inventario mal formada: " + texto)

        codigo = campos[0].strip()
        nombre = campos[1].strip()
        try:
            existencia = int(campos[2].strip())
        except ValueError:
            raise ErrorDeCarga("Existencia no numerica en: " + texto)

        if existencia < 0:
            raise ErrorDeCarga("Existencia inicial negativa en: " + texto)
        if codigo in inventario:
            raise ErrorDeCarga("Codigo de producto duplicado: " + codigo)

        inventario[codigo] = Producto(codigo, nombre, existencia)

    if not inventario:
        raise ErrorDeCarga("El inventario quedo vacio: " + ruta)
    return inventario


def cargar_pedidos(ruta, codigos_validos):
    """
    Devuelve una lista de Pedido.

    codigos_validos: codigos existentes en el inventario. Sirve para marcar
    como invalido un pedido que solicita un producto inexistente.
    """
    pedidos = []
    ids_vistos = set()

    for numero, texto in _lineas_utiles(ruta, "id,"):
        campos = texto.split(",", 2)
        if len(campos) < 3:
            pedidos.append(Pedido.crear_invalido(
                "LINEA-{}".format(numero), "(desconocido)",
                "Faltan campos en el registro"))
            continue

        id_pedido = campos[0].strip() or "LINEA-{}".format(numero)
        cliente = campos[1].strip()
        lista_productos = campos[2].strip()

        # Integridad de carga: dos pedidos no pueden compartir id.
        if id_pedido in ids_vistos:
            raise ErrorDeCarga(
                "Identificador de pedido duplicado en el archivo: " + id_pedido)
        ids_vistos.add(id_pedido)

        if not cliente:
            pedidos.append(Pedido.crear_invalido(
                id_pedido, "(sin cliente)", "Cliente vacio"))
            continue
        if not lista_productos:
            pedidos.append(Pedido.crear_invalido(
                id_pedido, cliente, "Pedido sin productos"))
            continue

        lineas = []
        motivo_error = None

        for item in lista_productos.split("|"):
            partes = item.split(":")
            if len(partes) != 2:
                motivo_error = "Formato de producto invalido: '{}'".format(item)
                break

            codigo = partes[0].strip()
            texto_cantidad = partes[1].strip()

            if not codigo:
                motivo_error = "Codigo de producto vacio"
                break
            try:
                cantidad = int(texto_cantidad)
            except ValueError:
                motivo_error = "Cantidad no numerica: '{}'".format(texto_cantidad)
                break
            if cantidad <= 0:
                motivo_error = "Cantidad invalida ({}) en {}".format(cantidad, codigo)
                break
            if codigo not in codigos_validos:
                motivo_error = "Producto inexistente en el inventario: " + codigo
                break

            lineas.append(LineaPedido(codigo, cantidad))

        if motivo_error is not None:
            pedidos.append(Pedido.crear_invalido(id_pedido, cliente, motivo_error))
        else:
            pedidos.append(Pedido.crear_valido(id_pedido, cliente, lineas))

    if not pedidos:
        raise ErrorDeCarga("No se cargo ningun pedido desde: " + ruta)
    return pedidos
