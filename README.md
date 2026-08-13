# NovaTech — Procesamiento concurrente de pedidos con hilos



** Vieri Alexander Sistemas Operativos I **

---

## Datos del estudiante

| Campo | Valor |
|---|---|
| Nombre completo | `Vieri Alexander Ixtecoc Lopez` |
| Carné | `1890-23-3479` |
| Sección | `A` |
| Fecha de entrega | `14 de agosto de 2026` |
| Lenguaje seleccionado | Python |
| Versión / entorno | Python 3.14.0 (64-bit) |
| Sistema operativo de prueba | Windows 11 |
| Forma de entrega | Archivo ZIP con el proyecto completo |

---

## 1. Requisitos

- **Python 3.8 o superior** (probado en 3.14.0)
- **Ninguna dependencia externa.** El programa usa solo la biblioteca
  estándar: `threading`, `queue`, `random`, `time`, `argparse`, `datetime`,
  `enum`, `os`.

No hay `requirements.txt` porque no hay nada que instalar.

Verificar la instalación:

```bash
python --version
```

---

## 2. Ejecución

Desde la carpeta raíz del proyecto (la que contiene `main.py`):

```bash
# Ejecución normal: 3 trabajadores + 1 monitor
python main.py
```

### Modos adicionales

```bash
# Comparación de rendimiento: 1 solo trabajador
python main.py --workers 1

# Cualquier cantidad de trabajadores
python main.py --workers 6

# MODO DEMOSTRACIÓN: desactiva el candado para exponer la condición de carrera
python main.py --sin-lock --workers 6
```

> ⚠️ `--sin-lock` **no es el modo de operación**. Existe únicamente para
> evidenciar qué ocurre sin sincronización (el inventario queda negativo).
> El modo normal siempre protege la sección crítica.

Si el comando `python` no funciona en Windows, probar con `py main.py`.

---

## 3. Estructura del proyecto

```
NovaTechPython/
├── main.py                  Hilo principal: crea, inicia, join, resumen
├── novatech/
│   ├── __init__.py
│   ├── modelo.py            Estado, Producto, LineaPedido, Pedido
│   ├── cargador.py          Lectura de CSV y excepciones de datos
│   ├── registro.py          Log con marca de tiempo y candado propio
│   ├── inventario.py        RECURSO COMPARTIDO — sección crítica
│   ├── contadores.py        Contadores protegidos y control de duplicados
│   ├── trabajador.py        Hilo trabajador (x3 mínimo)
│   └── monitor.py           Hilo monitor (x1)
├── datos/
│   ├── inventario.csv       5 productos con su existencia inicial
│   └── pedidos.csv          23 pedidos: 20 válidos + 3 mal formados
├── evidencias/              Capturas de los casos de prueba
├── docs/                    Diagrama e informe técnico
├── .gitignore
└── README.md
```

📌 La carpeta `datos/` debe permanecer junto a `main.py`. Las rutas se
resuelven a partir de la ubicación del archivo, por lo que el programa
funciona sin importar desde qué carpeta se invoque.

---

## 4. Estructura de hilos

| Componente | Cantidad | Responsabilidad | Condición de finalización |
|---|---|---|---|
| Hilo principal | 1 | Carga datos, crea hilos, `start()`, `join()`, resumen | Después de todos los secundarios |
| Trabajadores | 3 (configurable) | Extraen de la cola, simulan trabajo, validan y descuentan | Cuando la cola queda vacía |
| Monitor | 1 | Reporta estado cada 1.5 s | Al recibir la señal `Event` |
| **Total secundarios** | **4** | El hilo principal no se cuenta | Cierre limpio, sin hilos abandonados |

### Flujo

```
Hilo principal
    │  carga inventario.csv y pedidos.csv
    │  llena la cola compartida (queue.Queue)
    │
    ├──> MONITOR ──────────► lee contadores cada 1.5 s
    │                        se detiene con Event.set()
    │
    ├──> WORKER-1 ─┐
    ├──> WORKER-2 ─┼──► toman pedidos de la cola
    └──> WORKER-3 ─┘    ├─ simulan 0.5–2 s   (FUERA del candado)
                        └─ validan y descuentan (DENTRO del candado)
    │
    │  join() de los 3 trabajadores
    │  Event.set()  → señal al monitor
    │  join() del monitor
    ▼
  Resumen final + verificación de invariante
```

### Dónde ver cada etapa en el código

| Etapa | Archivo | Marca |
|---|---|---|
| Creación de hilos | `main.py` | `# ---------- 3. CREACION DE LOS HILOS ----------` |
| Inicio | `main.py` | `# ---------- 4. INICIO ----------` |
| Espera | `main.py` | `# ---------- 5. ESPERA CON JOIN ----------` |
| Señal de cierre | `main.py` | `# ---------- 6. SENAL DE CIERRE AL MONITOR ----------` |

---

## 5. Decisiones de sincronización

| Recurso compartido | Riesgo | Protección implementada |
|---|---|---|
| Cola de pedidos | Dos hilos toman el mismo pedido | `queue.Queue` (thread-safe) + un `set` de IDs ya tomados como segunda barrera |
| Inventario | Venta sobre la existencia, cantidades negativas | **`threading.Lock`** envolviendo validación + descuento |
| Contadores y resultados | Totales incorrectos por incrementos perdidos | `threading.Lock` en cada operación |
| Señal del monitor | El monitor sigue corriendo al terminar | **`threading.Event`** con `wait(timeout)` |
| Salida por consola | Líneas entremezcladas e ilegibles | Candado **independiente** en `Registro` |

### La sección crítica

Está en `novatech/inventario.py`, método `procesar()`:

```python
if self.proteccion_activa:
    self._candado.acquire()
try:
    # 1. Validar TODAS las líneas del pedido
    # 2. Si todas alcanzan, descontar TODAS
finally:
    self._candado.release()
```

**Tres decisiones deliberadas:**

1. **Verificar y descontar van juntos.** Separarlos produciría el patrón
   `check-then-act`: dos hilos leen "quedan 4 unidades", ambos concluyen que
   alcanza, ambos descuentan, y el inventario queda en −4.

2. **Todo o nada.** Un pedido puede tener varios productos. Si una sola línea
   no tiene existencias, no se descuenta ninguna. Esto cumple el RF-05:
   *"rechazar el pedido sin modificar el stock"*.

3. **El candado se libera en `finally`.** Aunque se lance una excepción, el
   candado se suelta y ningún hilo queda bloqueado para siempre.

### Qué queda deliberadamente FUERA del candado

- La simulación de trabajo de 0.5 a 2 s → está en `trabajador.py`, **antes**
  de llamar a `procesar()`. La regla técnica prohíbe mantener un lock durante
  esperas artificiales.
- La escritura en consola → `Registro` tiene su propio candado. Usar el del
  inventario para imprimir volvería el programa secuencial.

### Cómo termina el monitor

`Event.wait(1.5)` devuelve `False` al cumplirse el tiempo (imprime otro
reporte) y `True` cuando llega la señal (sale de inmediato). Se usa en lugar
de `time.sleep()` porque con `sleep` el monitor seguiría dormido hasta 1.5 s
después de que todo terminó. No es un hilo *daemon* abandonado: se le hace
`join()` igual que a los trabajadores.

---

## 6. Datos del escenario

**Inventario inicial** (`datos/inventario.csv`):

| Código | Producto | Existencia |
|---|---|---|
| P001 | Teclado mecánico | 12 |
| P002 | Mouse inalámbrico | 18 |
| P003 | Audífonos USB | 10 |
| P004 | Cámara web | 8 |
| P005 | Monitor de 24 pulgadas | 6 |

**Pedidos** (`datos/pedidos.csv`): 23 en total — **20 válidos** (el mínimo
que exige el RF-01) más **3 mal formados** para el caso CP-04.

Formato: `id,cliente,CODIGO:CANTIDAD|CODIGO:CANTIDAD`

Los datos están diseñados para forzar los casos de prueba:

- **P005** (6 unidades) recibe pedidos por 10 → contención garantizada (CP-02)
- **P004** (8 unidades) recibe pedidos por 10 → contención garantizada (CP-02)
- **ORD-014** pide 20 audífonos habiendo 10 → rechazo seguro (CP-03)
- **ORD-021/022/023** traen código vacío, cantidad cero y cantidad no
  numérica → error controlado (CP-04)

Los pedidos mal formados **no se descartan al cargar**: entran a la cola para
que un trabajador falle de forma controlada y para que se cumpla
`procesados == cargados`.

---

## 7. Reproducir los casos de prueba

| Caso | Comando | Qué observar |
|---|---|---|
| CP-01 Flujo normal | `python main.py` | Logs intercalados de WORKER-1/2/3 |
| CP-02 Contención | `python main.py` | Rechazos en P004 y P005 sin negativos |
| CP-03 Stock insuficiente | `python main.py` | `ORD-014 RECHAZADO` |
| CP-04 Pedido inválido | `python main.py` | `ORD-021/022/023 ERROR`, los demás siguen |
| CP-05 Cierre limpio | `python main.py` | `4/4` hilos y 0 activos al final |
| Condición de carrera | `python main.py --sin-lock --workers 6` | Inventario **negativo** |
| Rendimiento | `python main.py --workers 1` vs `--workers 3` | Comparar tiempo total |

> El orden exacto de los mensajes **cambia entre ejecuciones**. Eso es normal
> en un programa concurrente. Lo que nunca cambia es la integridad de los
> datos.

---

## 8. Verificación automática de integridad

Al terminar, el programa comprueba e imprime cinco condiciones:

```
[OK]  Invariante: existencia final = inicial - aprobadas
[OK]  Ningun producto quedo con existencia negativa
[OK]  Aprobados + Rechazados + Errores = Procesados
[OK]  Cada pedido se proceso exactamente una vez (23 ids unicos de 23)
[OK]  Todos los hilos secundarios finalizaron (cierre limpio)
```

Si alguna falla, aparece `[FALLA]` en lugar de `[OK]`.

**Pruebas realizadas:** 10 ejecuciones consecutivas sin un solo `[FALLA]`.
También se probó con 1, 2, 6 y 20 trabajadores, y con valores inválidos
(`0`, `-5`, que se corrigen a 1), sin pérdida de integridad ni hilos
colgados.

---

## 9. Manejo de errores

| Situación | Comportamiento |
|---|---|
| Falta `pedidos.csv` o `inventario.csv` | Mensaje claro, salida controlada |
| ID de pedido duplicado en el CSV | Error de carga antes de iniciar hilos |
| Existencia inicial negativa | Error de carga |
| Archivo sin pedidos | Error de carga |
| Pedido mal formado | Se cuenta como ERROR, los demás hilos continúan |
| Excepción inesperada en un trabajador | Se captura, se registra y el hilo sigue |

---

## 10. Créditos y recursos utilizados

- Documentación oficial de Python: módulos
  [`threading`](https://docs.python.org/3/library/threading.html) y
  [`queue`](https://docs.python.org/3/library/queue.html).
- No se utilizaron bibliotecas de terceros ni fragmentos de código externos.
- Los datos del escenario (productos y existencias iniciales) provienen del
  enunciado de la tarea.
