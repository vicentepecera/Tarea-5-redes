INFORME - ACTIVIDAD: FORWARDING BÁSICO

1. Tabla de rutas de la actividad vs. una tabla de rutas real

Ambas tablas asocian un destino (una red en notación CIDR) con el next hop al que se debe enviar el paquete, se recorren para encontrar la ruta que calza con la dirección de destino, pueden tener una ruta default que captura todo lo que no calza con otra entrada, y en ambas el router solo conoce el siguiente salto y no el camino completo. Las diferencias son varias. En la actividad todos los routers comparten la IP 127.0.0.1 y se distinguen por puerto, por lo que cada ruta incluye un rango de puertos; una tabla real no considera puertos, ya que son información de la capa de transporte. Nuestra tabla se recorre en orden y se usa la primera entrada que calza, mientras que una tabla real usa longest prefix match (gana la máscara más específica sin importar el orden). Una tabla real además indica la interfaz de salida y una métrica para cada ruta, y suele llenarse dinámicamente con protocolos de ruteo (OSPF, BGP, RIP), mientras que la nuestra es estática y se escribe a mano. Por último, en la actividad varias rutas hacia un mismo destino se reparten por round-robin; en redes reales esto existe (ECMP), pero solo entre rutas de igual costo.

2. Estructura del paquete IP

El paquete se representa solo con bytes y tiene un header de 7 bytes: los bytes 0 a 3 son la IP de destino (un byte por cada número de a.b.c.d), los bytes 4 y 5 son el puerto de destino (entero big-endian de 2 bytes), el byte 6 es el TTL (0 a 255) y desde el byte 7 en adelante va el mensaje en UTF-8. La función parse_packet(IP_packet) devuelve un diccionario {"ip", "port", "ttl", "message"} y create_packet(parsed_IP_packet) reconstruye los bytes a partir de ese diccionario. El test de ida y vuelta (tests.py) imprime "IP_packet_v1 == IP_packet_v2 ? True". Como create_packet ya retorna bytes, no es necesario el .encode() que aparece en el ejemplo del enunciado para la Parte II.

3. Script de envío de mensajes

El script enviar.py recibe todo por línea de comandos con sys.argv, de la forma:

    python3 enviar.py IP_router_final puerto_router_final "mensaje" IP_envio puerto_envio [TTL]

IP_router_final y puerto_router_final son el destino final que se escribe en el header, el mensaje va entre comillas si tiene espacios, IP_envio y puerto_envio son el router al que se entrega el paquete (primer salto) y el TTL es opcional, con valor 64 por defecto (el de Linux). Por ejemplo, "python3 enviar.py 127.0.0.1 8883 "hola" 127.0.0.1 8881 10" envía "hola" a R3 entrando por R1 con TTL 10. Para las pruebas con archivos se usa prueba_router.py, que lee el archivo desde la entrada estándar:

    python3 prueba_router.py "127.0.0.1;8885;10" 127.0.0.1 8881 < archivo.txt

Los headers van entre comillas porque en la terminal el ";" separa comandos.

4. Diseño de round-robin

check_routes(routes_file_name, destination_address) lee la tabla en orden y busca la primera línea que calza con el destino (IP dentro de la red CIDR y puerto dentro del rango). Esa línea define el "área" de destino, que es la tupla (red, puerto inicial, puerto final), y todas las líneas de la tabla con exactamente esa misma área se consideran rutas alternativas. El estado se guarda en un diccionario global, _round_robin_state, cuya llave es (archivo_de_rutas, área) y cuyo valor es el índice de la próxima ruta a usar; en cada llamada se retorna la ruta en ese índice y el índice avanza de forma circular. Así el código funciona con cualquier número de rutas alternativas, cada área lleva su propio contador (el tráfico hacia un área no altera el ciclo de las otras) y la ruta default (0.0.0.0/0) es un área distinta, por lo que nunca entra en el ciclo de un área interna. La tabla se vuelve a leer en cada llamada, así que se puede modificar sin reiniciar el router.

5. Router default

Se agregó un router default en (127.0.0.1, 7000) y a cada tabla se le añadió como última línea "0.0.0.0/0 0 65535 127.0.0.1 7000". La ruta default debe ir en la última posición de la tabla: como la tabla se recorre en orden y se usa la primera coincidencia, y la ruta default calza con cualquier destino, cualquier ruta que estuviera debajo de ella nunca se usaría. Esto equivale a que en una tabla real la ruta /0 sea la menos específica. Por ejemplo, la tabla de R2 en la red de 5 routers queda así:

    127.0.0.1/24 8881 8881 127.0.0.1 8881
    127.0.0.1/24 8883 8885 127.0.0.1 8883
    127.0.0.1/24 8883 8885 127.0.0.1 8884
    0.0.0.0/0 0 65535 127.0.0.1 7000

La tabla del router default (rutas_default.txt) tiene una ruta directa hacia cada router de la red (8880 a 8886). Como prueba se envió un paquete a 127.0.0.1:9000 (fuera de la red) entrando por R1: R1 lo reenvió a ('127.0.0.1', 7000) y el router default, que no tiene ruta hacia afuera de nuestra red, imprimió "No hay rutas hacia ('127.0.0.1', 9000)". En el mismo momento, otro paquete con destino R5 siguió su camino normal.

6. Pruebas del mini-Internet sin TTL

Con rutas_R2_v2.txt mal configurado, R2 envía los paquetes destinados a R3 (8883) de vuelta a R1, por lo que un paquete de R1 a R3 queda atrapado en un ciclo infinito R1 -> R2 -> R1 -> R2 -> ...: R1 lo envía a R2 porque su tabla dice que R3 está por R2, y R2 se lo devuelve. El paquete nunca llega a R3 y, sin TTL, nada lo detiene; los dos routers lo reenvían para siempre consumiendo CPU y ancho de banda, y cada paquete nuevo se suma al ciclo y aumenta la congestión.

En la red de 5 routers (R1-R2, R2-R3, R2-R4, R3-R5, R4-R5) se enviaron 12 paquetes seguidos de R1 a R5. Round-robin funciona: R2 alterna entre 8883 y 8884 para el área 8883-8885. Los paquetes no siempre dan la misma cantidad de saltos, sino que alternan entre 7 y 3 (promedio 5), mientras que el mínimo es 3 (R1->R2->R3->R5 o R1->R2->R4->R5); es decir, la mitad de los paquetes toma un camino más del doble de largo que el óptimo. Esto ocurre porque round-robin no considera distancias: la primera ruta de R3 hacia R5 vuelve por R2, y lo mismo pasa en R4, por lo que el camino largo es R1->R2->R3->R2->R4->R2->R3->R5. El patrón es tan regular porque los paquetes se enviaron de a uno; con tráfico concurrente los contadores se mezclan y los saltos varían más.

Para la red de 7 routers se agregó R0 (8880), conectado a R1 y R2, y R6 (8886), conectado a R2 y R3. Se intercalaron 8 paquetes de R1 a R5 y 8 de R5 a R1. Los de R1 a R5 dieron 3, 4, 6, 4, 7, 5, 5 y 6 saltos (promedio 5,0) y los de R5 a R1 dieron 4, 3, 5, 5, 4, 4, 6 y 3 saltos (promedio 4,25); en ambos sentidos el mínimo posible es 3. Todos los paquetes llegaron, pero al haber más caminos la cantidad de saltos es más variable que en la red de 5 routers y casi nunca es la mínima. En R2 se comprobó que round-robin cicla de forma independiente en cada área aunque los paquetes de ambos sentidos llegaran intercalados: hacia el área 8883-8886 (R5) usó 8883, 8884, 8886, 8883, 8884, 8886..., y hacia el área 8880-8881 (R1) usó 8880, 8881, 8880, 8881...

Las tablas creadas para esta red son las siguientes (las versiones _default agregan al final "0.0.0.0/0 0 65535 127.0.0.1 7000"):

    # rutas_R0_v4.txt
    127.0.0.1/24 8881 8881 127.0.0.1 8881
    127.0.0.1/24 8882 8886 127.0.0.1 8882

    # rutas_R1_v4.txt
    127.0.0.1/24 8880 8880 127.0.0.1 8880
    127.0.0.1/24 8882 8886 127.0.0.1 8882
    127.0.0.1/24 8882 8886 127.0.0.1 8880

    # rutas_R2_v4.txt
    127.0.0.1/24 8880 8881 127.0.0.1 8880
    127.0.0.1/24 8880 8881 127.0.0.1 8881
    127.0.0.1/24 8883 8886 127.0.0.1 8883
    127.0.0.1/24 8883 8886 127.0.0.1 8884
    127.0.0.1/24 8883 8886 127.0.0.1 8886

    # rutas_R3_v4.txt
    127.0.0.1/24 8880 8882 127.0.0.1 8882
    127.0.0.1/24 8880 8882 127.0.0.1 8886
    127.0.0.1/24 8884 8885 127.0.0.1 8885
    127.0.0.1/24 8884 8885 127.0.0.1 8882
    127.0.0.1/24 8886 8886 127.0.0.1 8886

    # rutas_R4_v4.txt
    127.0.0.1/24 8880 8883 127.0.0.1 8882
    127.0.0.1/24 8880 8883 127.0.0.1 8885
    127.0.0.1/24 8885 8885 127.0.0.1 8885
    127.0.0.1/24 8886 8886 127.0.0.1 8882

    # rutas_R5_v4.txt
    127.0.0.1/24 8880 8884 127.0.0.1 8883
    127.0.0.1/24 8880 8884 127.0.0.1 8884
    127.0.0.1/24 8886 8886 127.0.0.1 8883

    # rutas_R6_v4.txt
    127.0.0.1/24 8880 8882 127.0.0.1 8882
    127.0.0.1/24 8883 8885 127.0.0.1 8883
    127.0.0.1/24 8883 8885 127.0.0.1 8882

7. Pruebas del mini-Internet con TTL

Al repetir la prueba de la tabla mal configurada con TTL 10, el paquete de R1 a R3 vuelve a quedar atrapado entre R1 y R2, pero esta vez el ciclo termina: cada salto resta 1 al TTL y, tras 10 reenvíos (5 en R1 y 5 en R2), el paquete llega a R1 con TTL 0, R1 imprime "Se recibió paquete [127.0.0.1,8883,0,hola] con TTL 0" y lo descarta. La diferencia con la versión sin TTL es que el error de configuración sigue impidiendo que el paquete llegue a R3, pero ya no genera tráfico infinito: el costo de un paquete perdido queda acotado a TTL saltos (con TTL 255 se observaron exactamente 255 reenvíos antes del descarte). También se verificó el caso del enunciado: un paquete de R1 a R3 con TTL 1 sale de R1 con TTL 0, R2 lo descarta y nunca llega a R3.

Para el orden de los paquetes se envió un archivo de 200 líneas ("linea 000" a "linea 199") de R1 a R5 en la red de 5 routers con prueba_router.py. Con TTL 64 llegaron las 200 líneas, pero en 60 ocasiones una línea llegó antes que una anterior; con TTL 10 llegaron 186, se descartaron 14 por TTL y hubo 37 inversiones de orden. En una corrida el orden de llegada comenzó con 2, 6, 10, 14, 18, ..., 66, 8, 24, 40, 56, 3, 7, 11... Los paquetes no llegan en orden porque round-robin envía paquetes consecutivos por caminos de distinto largo (3, 5, 7 o más saltos), y los que van por caminos cortos adelantan a los demás; además, cuando muchos paquetes llegan a la vez los contadores se intercalan y algunos paquetes dan muchas vueltas, lo que explica las pérdidas con TTL 10. Esto muestra que la capa de red, al igual que UDP, no garantiza ni el orden ni la entrega, y que si se necesita el contenido completo y ordenado una capa superior debe numerar, reordenar y retransmitir, como hace TCP.

8. Archivos entregados y ejecución

router.py es el router, con parse_packet, create_packet y check_routes (incluye round-robin), y se ejecuta como "python3 router.py 127.0.0.1 8881 rutas/rutas_R1_v3.txt". enviar.py envía un mensaje (sección 3) y prueba_router.py envía un archivo línea por línea. lanzar_red.py levanta todos los routers de una topología con fork (v1, v2, v2_malo, v3, v3_default, v4 o v4_default) y deja la salida de cada router en log_<puerto>.txt. tests.py contiene los tests de ida y vuelta de los paquetes, de check_routes, de round-robin por área y de la ruta default. La carpeta rutas/ contiene todas las tablas de rutas.
