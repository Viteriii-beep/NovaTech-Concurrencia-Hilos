"""
Paquete novatech: simulador concurrente de procesamiento de pedidos.

Modulos:
    modelo      - Estado, Producto, LineaPedido, Pedido
    cargador    - lectura de CSV y excepciones de datos
    registro    - log con marca de tiempo y candado propio
    inventario  - recurso compartido con la SECCION CRITICA
    contadores  - contadores protegidos y control de duplicados
    trabajador  - hilo trabajador
    monitor     - hilo monitor
"""
