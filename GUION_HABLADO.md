# RockDove — Guion hablado (10 min, todo demo en vivo)

**Cómo usar este guion:**
- El texto normal es **lo que se dice literal**. Leelo natural, sin apurarte (ritmo tranquilo ≈ 140 palabras por minuto).
- Lo que está entre corchetes `[ACCIÓN: ...]` **NO se dice**: es lo que hacés en la pantalla mientras hablás.
- Toda la presentación es la app en vivo. Empezá con RockDove ya abierto y compartiendo pantalla.
- Cada persona ≈ 2 minutos.

**Antes de arrancar (checklist):**
- App abierta en el dashboard, con peers en línea visibles.
- Tener a mano una imagen con colores/formas (se ve mucho mejor cuando se "rompe").
- Pestaña **Demo RS** lista para usar.

---

## 🎤 Persona 1 — Introducción mostrando la app (≈2 min)

*[ACCIÓN: pantalla compartida con RockDove abierto en el dashboard, peers en línea a la vista.]*

Buenas a todos. Somos el Grupo 1 y les vamos a presentar **RockDove**, un sistema para transferir archivos entre computadoras que sigue funcionando incluso cuando la red es mala y se pierden pedazos de información.

Y en vez de contarles con diapositivas, se los vamos a mostrar funcionando. Esto que ven es la app real, corriendo ahora mismo.

*[ACCIÓN: señalar la lista de peers.]*

Acá aparece la lista de **peers**, que son simplemente las computadoras conectadas al sistema. Cada pajarito indica que ese peer está en línea, listo para enviar o recibir archivos.

¿Por qué esto es un problema interesante? Cuando mandás un archivo por internet, viaja partido en paquetes, y en redes malas —una conexión satelital, celular, o una red industrial— algunos de esos paquetes se pierden en el camino. La solución de siempre, la que usa por ejemplo TCP, es pedir "che, reenviame ese pedazo". Pero eso es lento, y a veces imposible, por ejemplo en un enlace que va en una sola dirección.

RockDove lo resuelve distinto: en lugar de pedir que reenvíen, **agrega pedazos de respaldo hechos con matemática**, así el que recibe reconstruye el archivo completo solo, sin volver a pedir nada. Es como mandar un libro de 30 páginas con 2 páginas mágicas de respaldo: si se pierden dos en el correo, el que lo recibe las recupera solo.

Ahora vamos a ver cómo se conectan los peers, cómo viaja un archivo y, sobre todo, cómo esos respaldos salvan una imagen cuando la red falla.

---

## 🎤 Persona 2 — Arquitectura navegando la app (≈2 min)

*[ACCIÓN: quedarse en el dashboard; ir señalando la lista de peers.]*

Vamosa a ver cómo está organizado RockDove por dentro: tiene dos partes bien separadas. Por un lado, el **servidor central**, que funciona como una guía telefónica: sabe qué peers están conectados y dónde encontrarlos.

*[ACCIÓN: señalar la lista de peers que se actualiza sola.]*

Esta lista que se actualiza sola viene justamente de ese servidor. Pero atención con esto: el servidor **nunca ve el contenido de los archivos**. Solo coordina.

Por otro lado está el **agente**, un programa que corre en cada computadora.

*[ACCIÓN: abrir la pestaña Configuración.]*

Acá, en Configuración, ven los datos de nuestro agente: su identidad y el canal que usa para transferir. El agente es el que hace el trabajo pesado: parte el archivo, le agrega los respaldos y lo manda directo a la otra computadora.

Y ese es el punto clave del diseño: cuando yo le mando un archivo a un compañero, el archivo viaja **directo de mi máquina a la suya**. El servidor solo me dijo dónde estaba; nunca toca el paquete. Es la misma idea que usan herramientas como Tailscale.

¿Por qué separarlo así? Porque el servidor queda liviano y no maneja información privada, y la transferencia sigue funcionando aunque el servidor tenga problemas. Además, fíjense que el canal se puede cambiar entre **UDP** y **QUIC** —ya lo vamos a ver —. Ahora vamos a ver cómo son esos respaldos matemáticos.

---

## 🎤 Persona 3 — Reed-Solomon + primer caso en vivo (≈2 min)

*[ACCIÓN: abrir la pestaña "Demo RS".]*

El corazón de RockDove es un algoritmo que se llama **Reed-Solomon**. Se los muestro con esta pestaña, "Demo RS", que preparamos justamente para ver el algoritmo funcionando sobre una imagen.

*[ACCIÓN: hacer clic en "Elegir imagen" y seleccionar la foto.]*

Elijo una imagen para enviar. Lo que hace RockDove por dentro es partir este archivo en **32 bloques**. De esos 32, algunos son los datos originales y el resto son bloques de respaldo, lo que llamamos la **paridad**. La propiedad mágica de Reed-Solomon es esta: **no importa cuáles bloques lleguen; con que llegue una cantidad suficiente, se reconstruye el archivo entero**.

Por ejemplo, con 25% de redundancia tengo 24 bloques de datos y 8 de respaldo. Eso significa que puedo perder hasta 8 bloques cualesquiera y aún así recuperar todo.

*[ACCIÓN: poner Redundancia en 25%, Pérdida en 0%, y clic en "Simular transferencia".]*

Empecemos por el caso fácil: redundancia 25% y una red perfecta, sin pérdida. Simulo...

*[ACCIÓN: mostrar el resultado; señalar las tres imágenes.]*

Perfecto: estado **"ok"**, y las tres imágenes son idénticas. Llegó todo directo, no hizo falta reconstruir nada.

Fíjense en estos números de acá: bloques enviados, perdidos y recuperados. Ahora, cero perdidos. Pero, ¿qué pasa cuando la red empieza a fallar y se pierden paquetes? Ahí es donde Reed-Solomon se luce.

---

## 🎤 Persona 4 — La red falla y RS salva la imagen (≈2 min)

*[ACCIÓN: en Demo RS, dejar Redundancia en 25% y subir Pérdida a 20%. Clic en "Simular".]*

Vamos a romper un poco la red, a ver qué pasa. Dejo la misma redundancia, 25%, pero ahora subo la pérdida al 20%. Simulo...

*[ACCIÓN: señalar los tres paneles, uno por uno.]*

Miren lo que pasó. En el panel del medio, "Sin Reed-Solomon", ven la imagen como llegaría con UDP crudo: con bandas grises, rota, porque se perdieron bloques en el camino. Pero a la derecha, "Con Reed-Solomon", la imagen está **perfecta**. El algoritmo usó los bloques de respaldo para reconstruir los que se perdieron.

El estado dice **"degraded"**: hubo pérdida, pero se recuperó todo. Y acá, "recuperados por RS", muestra cuántos bloques rearmó el algoritmo.

Esto es lo que hace único a RockDove: la misma pérdida que rompería un archivo normal, acá ni se nota.

Y hay algo más. RockDove no le pide al usuario que adivine cuánta redundancia usar. El sistema **mide la calidad de la red en tiempo real** —cuánto tarda, cuánto varía, cuánto se pierde— y ajusta la redundancia solo: si la red está bien, usa poco respaldo para ir rápido; si está mal, usa más para ir seguro. A eso lo llamamos **redundancia adaptativa**.

También se puede elegir el canal: **UDP**, más simple, o **QUIC**, que agrega cifrado e identidad verificada. Pero, ¿qué pasa si la red está tan mal que se pierde más de lo que el respaldo puede cubrir? Eso lo cierra [nombre].

---

## 🎤 Persona 5 — El límite, el rescate y cierre (≈2 min)

*[ACCIÓN: dejar Redundancia en 25% y subir Pérdida a 40%. Clic en "Simular".]*

Vamos al peor caso. Dejo la redundancia en 25%, que aguanta hasta 8 bloques perdidos, pero subo la pérdida al 40%. Eso son unos 13 bloques perdidos, más de lo que el respaldo puede cubrir. Simulo...

*[ACCIÓN: señalar el estado y el panel derecho vacío.]*

Ahora sí, el estado es **"failed"**. Ni siquiera Reed-Solomon puede reconstruir la imagen, porque se perdió más información de la que había de respaldo. Este es el límite del sistema.

Pero acá está lo interesante.

*[ACCIÓN: subir Redundancia a 50%, dejar Pérdida en 40%. Clic en "Simular".]*

Subo la redundancia al 50% —es decir, mando más respaldo— y con la misma pérdida del 40%, simulo de nuevo... Y la imagen **se recupera**. Volvimos a "degraded", reconstruida. Con más respaldo, el sistema resiste más pérdida. Por eso la redundancia adaptativa que vimos recién es tan importante: elige ese balance sola, según cómo esté la red.

Para cerrar: RockDove separa la coordinación de los datos, así el servidor es liviano y nunca ve tus archivos. Usa Reed-Solomon para reconstruir **sin tener que reenviar**, ideal para redes lentas o intermitentes. Y ajusta la protección solo, aprendiendo de la red.

Vieron todo funcionando en vivo: cómo se conectan los peers, cómo viaja un archivo y cómo se salva una imagen cuando la red falla. Muchas gracias, quedamos para las preguntas.

---

## Resumen de acciones de la demo (chuleta)

| Persona | Qué muestra | Valores |
|---|---|---|
| 1 | Dashboard + peers online | — |
| 2 | Peers (servidor) + pestaña Configuración (agente, canal) | — |
| 3 | Demo RS: elegir imagen + caso OK | Redundancia 25% · Pérdida 0% |
| 4 | Demo RS: RS reconstruye | Redundancia 25% · Pérdida 20% → **degraded** |
| 5 | Demo RS: falla y rescate | 25% · 40% → **failed**, luego 50% · 40% → **degraded** |
