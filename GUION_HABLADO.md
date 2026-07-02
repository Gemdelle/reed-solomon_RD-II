# RockDove — Guion hablado (10 min, todo demo en vivo)

**Cómo usar este guion:**
- El texto normal es **lo que se dice literal**. Leelo natural, sin apurarte (ritmo tranquilo ≈ 140 palabras por minuto).
- Lo que está entre corchetes `[ACCIÓN: ...]` **NO se dice**: es lo que hacés en la pantalla mientras hablás.
- Toda la presentación es la app en vivo. Empezá con RockDove ya abierto y compartiendo pantalla.
- **4 personas ≈ 2.5 minutos cada una.** Reemplazá los `[nombre]` por los nombres reales.

**Antes de arrancar (checklist):**
- App abierta en el dashboard, con peers en línea visibles.
- Tener a mano una imagen con colores/formas (se ve mucho mejor cuando se "rompe").
- Pestaña **Demo RS** lista para usar.

---

## 🎤 Persona 1 — Qué es RockDove y sus componentes (≈2.5 min)

*[ACCIÓN: dashboard abierto, peers en línea a la vista.]*

Buenas a todos, somos el Grupo 1 y les presentamos **RockDove**: un sistema para transferir archivos entre computadoras que sigue funcionando aunque la red pierda paquetes.

El problema es este: cuando mandás un archivo, viaja partido en paquetes, y en redes malas —una conexión satelital, celular o industrial— algunos de esos paquetes se pierden. La solución clásica, la de TCP, es pedir que reenvíen el pedazo que faltó; pero eso es lento, y a veces imposible, por ejemplo en un enlace que va en una sola dirección.

RockDove lo resuelve distinto: **agrega pedazos de respaldo hechos con matemática**, así el que recibe reconstruye el archivo completo solo, sin volver a pedir nada. Es como mandar un libro de 30 páginas con 2 de respaldo: si se pierden dos en el correo, el receptor las recupera solo.

El sistema tiene dos grandes componentes.

*[ACCIÓN: señalar la lista de peers.]*

Por un lado, los **peers**: las computadoras de los usuarios, las que realmente envían y reciben los archivos. A eso lo llamamos el **plano de datos**, y acá los ven —cada pajarito es un peer en línea—. Por otro lado, un **servidor central**, el **plano de control**, que coordina todo pero nunca ve el contenido de los archivos.

Esa separación es la idea central: el servidor dice quién está conectado y dónde encontrarlo, pero los archivos viajan **directo** de una máquina a la otra. [nombre] les muestra el servidor por dentro, que es donde pasa toda la gestión.

---

## 🎤 Persona 2 — El servidor: control, autenticación, métricas y relays (≈2.5 min)

*[ACCIÓN: abrir el panel de administración / la pestaña de configuración del servidor.]*

Yo me encargué del backend, así que les muestro el servidor, el plano de control.

*[ACCIÓN: señalar los peers conectados.]*

Primero una aclaración clave de arquitectura: RockDove es un **overlay**, una capa que trabaja de la **capa 4 a la 7** —de transporte hasta aplicación—. No reemplaza la red física: necesita **sí o sí un underlay** por debajo que dé la conectividad, que puede ser **internet, una NAT o una VPN**. RockDove no resuelve cómo llegar de una IP a otra; asume que esa conectividad existe y se ocupa de lo suyo: descubrir peers, coordinar y proteger los datos.

Dicho eso, el servidor coordina en cuatro frentes.

Primero, la **comunicación**. Los agentes hablan con el servidor por un canal permanente usando **QUIC streams**. Esto es clave para la materia: en lugar del clásico HTTPS sobre TCP, cambiamos a QUIC, que nos da un transporte confiable y ordenado pero sin pagar el handshake de TLS en cada pedido. Es una de las decisiones de diseño centrales del trabajo.

Segundo, **autenticación y administración**.

*[ACCIÓN: mostrar el panel de admin / permisos.]*

El servidor tiene un sistema de permisos: hay administradores que deciden quién entra, qué peers pueden actuar como **relay**, y quién tiene permiso de usar esos relays. Todo se gestiona desde acá.

Tercero, **métricas**. El servidor recibe mediciones de cada peer —latencia, variación y pérdida— y con eso arma un **grafo de la red**, como un mapa de conexiones con pesos. Si detecta que un enlace directo es lento o malo, puede calcular un **camino mejor**.

Y ahí entra el cuarto punto: los **relays**. A veces A no puede llegar directo a B, o la conexión directa es mala. Entonces se hace un salto por un tercero: en vez de ir de A a B, va de **A a C, y de C a B**, si C tiene una conexión más fuerte. El peer del medio solo reenvía; sigue sin poder leer el archivo.

Resumiendo el servidor: coordina identidades y presencia, gestiona permisos, mide la red para elegir el mejor camino, y organiza los relays. Nunca toca el contenido. [nombre] va ahora al corazón del sistema: cómo se protegen los datos.

---

## 🎤 Persona 3 — Reed-Solomon en vivo (≈2.5 min)

*[ACCIÓN: abrir la pestaña "Demo RS" y elegir una imagen.]*

El corazón de RockDove, y el tema central de la materia, es la corrección de errores con **Reed-Solomon**. Lo mostramos con esta pestaña, Demo RS, sobre una imagen.

RockDove parte el archivo en **32 bloques**: algunos son los datos, y el resto son de respaldo, la **paridad**. La propiedad clave es esta: **no importa cuáles bloques lleguen; con que llegue una cantidad suficiente, se reconstruye todo**. Con 25% de redundancia, por ejemplo, tengo 24 bloques de datos y 8 de respaldo, así que puedo perder hasta 8 bloques cualesquiera y recuperar el archivo completo.

*[ACCIÓN: Redundancia 25%, Pérdida 0%, "Simular".]*

Caso fácil: 25% de redundancia y red perfecta. Simulo... Estado **"ok"**, las tres imágenes idénticas. Llegó todo, no hubo que reconstruir.

*[ACCIÓN: subir Pérdida a 20%, "Simular".]*

Ahora rompo la red: misma redundancia, pero 20% de pérdida. Simulo... Miren: en el medio, "Sin Reed-Solomon", la imagen llega **rota**, con bandas grises, porque se perdieron bloques. Pero a la derecha, "Con Reed-Solomon", está **perfecta**: el algoritmo usó el respaldo para reconstruir lo que faltaba. El estado es **"degraded"**: hubo pérdida, pero se recuperó todo.

Un detalle: estos bloques viajan **directo entre peers** por UDP, o por QUIC en modo datagrama, que a propósito **no reenvía**, para no pisar el trabajo de Reed-Solomon. [nombre] les muestra hasta dónde aguanta y cómo se ajusta solo.

---

## 🎤 Persona 4 — El límite, el rescate y cierre (≈2.5 min)

*[ACCIÓN: Redundancia 25%, Pérdida 40%, "Simular".]*

Vamos al límite. Dejo 25% de redundancia, que aguanta 8 bloques, pero subo la pérdida al 40%: unos 13 bloques perdidos, más de lo que el respaldo cubre. Simulo... Estado **"failed"**. Ni Reed-Solomon puede: se perdió más información de la que había de respaldo.

*[ACCIÓN: subir Redundancia a 50%, dejar Pérdida en 40%, "Simular".]*

Pero subo la redundancia al 50%, mando más respaldo, con la misma pérdida del 40%... y la imagen **se recupera**. Volvimos a "degraded". Más respaldo, más resistencia.

Y acá se conecta todo: RockDove no te hace elegir ese número a mano. Con las **métricas** que junta el servidor —las que mencionaba [nombre]— mide la calidad de la red y ajusta la redundancia solo: si la red está bien, poco respaldo para ir rápido; si está mal, más respaldo para ir seguro. Eso es la **redundancia adaptativa**.

Para cerrar: RockDove separa control y datos, así el servidor es liviano y nunca ve tus archivos. Usa **QUIC streams** para la coordinación, **Reed-Solomon** para reconstruir sin reenviar, y ajusta la protección solo según la red, con **relays** cuando el camino directo no sirve. Vieron todo en vivo: los peers, el servidor, y cómo se salva una imagen cuando la red falla. Muchas gracias, quedamos para las preguntas.

---

## Resumen de acciones de la demo (chuleta)

| Persona | Qué muestra | Valores |
|---|---|---|
| 1 | Dashboard + peers online (data plane vs control plane) | — |
| 2 | Panel de servidor: QUIC streams, admin/permisos, métricas/grafo, relays | — |
| 3 | Demo RS: elegir imagen → caso OK → caso degraded | 25% · 0% (ok) → 25% · 20% (degraded) |
| 4 | Demo RS: falla y rescate + redundancia adaptativa + cierre | 25% · 40% (failed) → 50% · 40% (degraded) |
