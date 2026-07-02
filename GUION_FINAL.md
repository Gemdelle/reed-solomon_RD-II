# RockDove — Guion del Final (10 min)

Documento para estudiar y repartir en el grupo. Tiene 3 partes:
1. **Cómo funciona** (explicado fácil).
2. **Guion de 10 minutos** (4 personas × 2.5 min).
3. **La demo paso a paso** (los 3 casos) + preguntas típicas.

---

## 1. Cómo funciona RockDove (fácil)

### El problema
Cuando mandás un archivo por una red mala (satélite, celular, redes industriales), se **pierden pedacitos** en el camino. Lo normal (TCP) es pedir "reenviame ese pedazo", pero eso es **lento** y a veces **imposible** (enlaces de una sola vía, mucha latencia).

### La idea (Reed-Solomon / FEC)
Antes de mandar, el archivo se corta en pedazos y se le agregan **pedazos de respaldo hechos con matemática**. El que recibe solo necesita *suficientes* pedazos (cualquiera) para **rearmar todo, sin pedir nada de vuelta**.

> 📖 **Analogía:** mandás un libro de 30 páginas como 32 (2 de respaldo "mágicas"). Si se pierden 2 en el correo, el receptor las reconstruye solo. Si el correo es un desastre, mandás más respaldos.

Esto se llama **FEC (Forward Error Correction)** y el algoritmo concreto es **Reed-Solomon**.

### Qué es, qué hace y qué componentes tiene
- **Qué es:** una plataforma de transferencia de archivos **peer-to-peer** (entre pares) con corrección de errores.
- **Qué hace:** manda archivos directo de una máquina a otra y garantiza que lleguen completos aunque la red pierda paquetes, sin reenviar.
- **Componentes principales:**
  1. **Peers / agentes (plano de datos):** las computadoras de los usuarios. Cada una corre un *agente* que parte el archivo, agrega la paridad Reed-Solomon y lo envía directo al otro peer.
  2. **Servidor central (plano de control):** coordina el sistema. No mueve archivos: gestiona identidades y presencia, permisos/administración, métricas de red y relays.

### RockDove es un overlay (capa 4–7) sobre un underlay ⭐
RockDove es un **overlay**: una capa que opera de la **capa 4 a la 7** del modelo OSI (transporte hasta aplicación). **No reemplaza la red**: necesita **sí o sí un underlay** por debajo que provea la conectividad IP.
- **Underlay** = la red que da alcance entre máquinas: **internet, una NAT o una VPN** (WireGuard, Tailscale, NetBird).
- **Overlay (RockDove)** = lo que agrega encima: descubrimiento de peers, coordinación, y **corrección de errores con Reed-Solomon**.

En criollo: el underlay resuelve *cómo llegar* de una IP a otra; RockDove **asume que esa conectividad existe** y se encarga de que los datos lleguen completos y protegidos.

### La gran decisión de diseño: dos planos separados

| Plano | Quién | Qué hace | ¿Ve el archivo? |
|-------|-------|----------|:---------------:|
| **Control** | Servidor central (en la nube) | Guía telefónica: quién está online, dónde, y "cuánto respaldo conviene" | ❌ Nunca |
| **Datos** | Agente (uno por máquina) | Corta/rearma con Reed-Solomon y manda el archivo **directo** a la otra máquina | ✅ |

> 📞 **Analogía:** el servidor es un amigo que te da la dirección de tu compañero. Después vos vas **directo** a su casa a entregar el paquete. El amigo nunca toca el paquete. (Igual que Tailscale o Syncthing.)

### Redundancia adaptativa
El sistema **mide la red** (ping, jitter, pérdida). Red buena → pocos respaldos (rápido). Red mala → muchos respaldos (seguro). **Automático**, el usuario no toca nada. Usa el nivel más alto entre lo que necesita el que manda y el que recibe (se protege según el extremo más débil).

### Canal de datos: UDP vs QUIC
- **UDP** = tirar postales: rápido, sin garantía, sin cifrado.
- **QUIC** = igual de rápido pero **cifrado y con identidad verificada** (certificado). Usa modo *datagram* que **no reenvía a propósito**, para no pisar el trabajo de Reed-Solomon.

### Canal de control: de TCP a QUIC streams ⭐ (decisión central de la materia)
La comunicación entre los agentes y el servidor (registro, presencia, métricas, consultas) **no usa el clásico HTTPS sobre TCP**: se cambió a **QUIC streams**, un transporte confiable y ordenado, pero sin pagar el *handshake* de TLS en cada pedido. El agente abre **una conexión QUIC persistente** al arrancar y la mantiene viva.
- **Plano de control** → **QUIC streams** (confiable y ordenado, tipo RPC).
- **Plano de datos** → **UDP** o **QUIC datagrams** (sin retransmisión, para que RS haga su trabajo).

> Junto con el FEC Reed-Solomon, este cambio TCP → QUIC streams es lo más importante para defender en el final.

### Autenticación y administración
El servidor tiene un **sistema de permisos con administradores**. Un admin puede:
- Decidir **quién entra** a la organización (login federado OIDC, o *device tokens* para dispositivos sin pantalla).
- Definir **qué peers pueden actuar como relay** y **quiénes pueden usar** esos relays.
- Ajustar políticas de transferencias entrantes (aceptar/rechazar por peer).

En **modo desarrollo** (el que usamos en la demo) la autenticación está relajada: cualquiera se registra y todos se ven entre sí.

### Relays: saltos A → C → B
A veces A **no puede llegar directo** a B (NAT, firewall, red segmentada) o la conexión directa es mala. Entonces se hace un **salto por un tercero**: en vez de A → B, va **A → C → B**, si C tiene mejor conexión. El peer del medio **solo reenvía** los bloques; nunca puede leer el archivo. El resultado queda marcado como `relayed`.

### Métricas, grafo de red y camino óptimo
Cada peer mide su red (latencia, jitter, pérdida) y reporta al servidor. El servidor:
- Guarda las últimas muestras de cada peer.
- Arma un **grafo de la red** (nodos = peers, aristas = calidad del enlace).
- Con ese grafo detecta enlaces lentos y calcula el **mejor camino** (por ejemplo, cuándo conviene un relay).
- Además alimenta la **redundancia adaptativa** (ver abajo).

### Los 4 resultados posibles
- `ok` = llegó todo directo.
- `degraded` = se perdieron pedazos **pero Reed-Solomon los reconstruyó** ✅ (acá se luce el algoritmo).
- `failed` = se perdió más de lo que el respaldo puede cubrir → no se puede rearmar.
- `relayed` = llegó a través de un peer intermediario (cuando no se pueden ver directo).

### Los números (para la parte técnica)
- `n` = 32 bloques totales por transferencia.
- `k` = bloques de datos = `round(n × (1 − r))`.
- `paridad` = `n − k` = cuántos bloques se pueden perder y aun así reconstruir.
- `r` = nivel de redundancia, entre 5% y 50%.

| Redundancia `r` | k (datos) | Paridad | Pérdida que tolera |
|:---:|:---:|:---:|:---:|
| 5% | 30 | 2 | 5% |
| 10% | 29 | 3 | 10% |
| 25% | 24 | 8 | 25% |
| 50% | 16 | 16 | 50% |

**Clave conceptual:** *cualquier* k de los n bloques alcanza para reconstruir todo. Como en UDP se sabe exactamente qué bloque llegó y cuál no, se usa el modo "borrado" (*erasure*), que es el más eficiente de Reed-Solomon.

---

## 2. Guion de 10 minutos — 4 personas × 2.5 min

> El texto **literal palabra por palabra** está en `GUION_HABLADO.md`. Acá va la versión resumida en bullets. **Toda la presentación es la demo en vivo.**

### 🎤 Persona 1 — Qué es RockDove y sus componentes (2.5 min)
- Enganchar con el problema: redes malas pierden paquetes; TCP reenvía = lento/imposible.
- La idea: **agregar respaldo matemático para no tener que reenviar** (analogía del libro).
- **Componentes:** peers/agentes = **plano de datos**; servidor central = **plano de control**.
- Mostrar el dashboard con los **peers online**.
- *Cierre: pasar al servidor por dentro.*

### 🎤 Persona 2 — El servidor: control, autenticación, métricas y relays (2.5 min) — *la parte de infra/backend*
- **Overlay capa 4–7** que necesita un **underlay** (internet / NAT / VPN); RockDove no da la conectividad, la asume.
- **QUIC streams** para el plano de control (⭐ cambio de TCP → QUIC streams; sin handshake TLS por pedido).
- **Autenticación y administración:** admins deciden quién entra, quiénes son relay y quiénes pueden usarlos.
- **Métricas + grafo de red:** el servidor mide cada peer, arma un grafo y calcula el **camino óptimo**.
- **Relays:** saltos **A → C → B** cuando el directo no sirve o C tiene mejor conexión.
- Mostrar el panel de administración / configuración del servidor.
- *Cierre: pasar al corazón, Reed-Solomon.*

### 🎤 Persona 3 — El corazón: Reed-Solomon en vivo (2.5 min) — *lo más de la materia*
- n = 32 bloques (k datos + paridad); **cualquier k de n reconstruye todo** (*erasure* sobre GF(2⁸)).
- Abrir **Demo RS**, elegir imagen.
- **Caso A:** 25% / 0% → `ok` (las 3 imágenes iguales).
- **Caso B:** 25% / 20% → `degraded` (panel "Sin RS" roto vs "Con RS" perfecto).
- Mencionar: los datos viajan por UDP / QUIC datagram (sin retransmisión).
- *Cierre: "¿hasta dónde aguanta?".*

### 🎤 Persona 4 — El límite, el rescate y cierre (2.5 min)
- **Caso C:** 25% / 40% → `failed` (se perdió más que la paridad).
- **Rescate:** subir a 50% / 40% → `degraded`, imagen recuperada.
- Conectar con la **redundancia adaptativa**: usa las métricas del servidor para ajustar sola el respaldo.
- *Cierre: conclusiones (control vs datos, QUIC streams, RS sin reenvío, adaptativa, relays).*

---

## 3. La demo paso a paso

### Antes de empezar (checklist)
1. Servidor + Redis corriendo (`http://localhost:8080`).
2. Agente `peer-alice` en `http://127.0.0.1:8000`.
3. (Para la parte 1, envío real) segundo agente `peer-bob` en `http://127.0.0.1:8001`.
4. UI en `http://localhost:5173/`.
5. Tener a mano **una imagen** (PNG o JPG) con formas/colores claros (una foto o un logo grande se ve mejor cuando se rompe).

### Parte 1 — Envío real (opcional, si sobra tiempo)
1. Conectarse como `peer-alice`.
2. En el dashboard, ver los peers online (el pajarito indica conectado).
3. Elegir un archivo → enviar a `peer-bob`.
4. Mostrar la **recomendación de redundancia** (chip de calidad).
5. Cambiar el transporte **UDP ↔ QUIC** y comentar la diferencia (QUIC = cifrado + aprobación por certificado).
6. Ver el resultado `ok` y el historial.

> Nota: en la misma computadora (localhost) casi no hay pérdida real, así que el envío real da `ok`. Para mostrar pérdida y reconstrucción usamos la **Demo RS** (parte 2), que simula el canal.

### Parte 2 — Demo RS (Personas 3 y 4) — la estrella visual
Pestaña **"Demo RS"** en el menú lateral. Persona 3 hace los casos A y B; Persona 4 hace el caso C y el rescate.

1. **Elegir imagen** (botón "Elegir imagen").
2. **Caso A — todo bien:**
   - Redundancia = **25%**, Pérdida = **0%** → ▶ Simular.
   - Resultado: **`ok`**. Las 3 imágenes iguales.
3. **Caso B — Reed-Solomon salva el día:**
   - Redundancia = **25%**, Pérdida = **20%** → ▶ Simular.
   - Resultado: **`degraded`**.
   - Panel **"Sin Reed-Solomon"** = imagen con bandas grises (lo que llegó crudo).
   - Panel **"Con Reed-Solomon"** = imagen **perfecta** (reconstruida con la paridad).
   - Señalar el contador "Recuperados por RS".
4. **Caso C — se rompe y luego se rescata:**
   - Redundancia = **25%**, Pérdida = **40%** → ▶ Simular.
   - Resultado: **`failed`** (se perdieron más bloques que la paridad). "Con RS" no puede.
   - **Ahora subir Redundancia a 50%**, misma pérdida 40% → ▶ Simular.
   - Resultado: **`degraded`** → imagen **rescatada**. 🎯
   - Moraleja: más redundancia = más resistencia (a costa de más datos enviados). Por eso la **redundancia adaptativa** ajusta esto solo según la red.

### Qué mirar en pantalla (para narrar)
- **Bloques enviados / perdidos / paridad / recuperados por RS**: cuentan la historia con números.
- Los 3 paneles de imagen: **Original | Sin RS | Con RS**.
- El cartel de estado: `ok` / `degraded` / `failed`.

---

## 4. Preguntas típicas del profesor (y respuestas cortas)

**¿Por qué UDP y no TCP?**
Porque TCP reenvía cada paquete perdido (round-trips), inviable en alta latencia o enlaces de una vía. RS reconstruye sin volver a pedir.

**¿RockDove reemplaza la red? ¿Qué es eso de overlay/underlay?**
No la reemplaza. RockDove es un **overlay** (capa 4–7): se apoya sobre un **underlay** que da la conectividad IP —internet, una NAT o una VPN—. El underlay resuelve *cómo llegar* de una IP a otra; RockDove asume esa conectividad y agrega descubrimiento de peers, coordinación y corrección de errores.

**¿Por qué cambiaron TCP por QUIC streams en el control?**
Para la coordinación (registro, presencia, métricas) usamos QUIC streams en vez de HTTPS/TCP: es confiable y ordenado igual, pero evita el handshake TLS en cada pedido. El agente mantiene una única conexión QUIC persistente. Es una de las decisiones centrales del trabajo.

**¿Por qué QUIC usa datagrams sin retransmisión en los datos?**
Si QUIC reenviara solo, pisaría el modelo de "borrado" de RS. Con DATAGRAM (RFC 9221) QUIC aporta cifrado e identidad sin cambiar la semántica de pérdida que RS necesita. Ojo: control = QUIC **streams** (confiable); datos = UDP o QUIC **datagram** (sin reenvío).

**¿Qué es un relay y quién puede usarlo?**
Un peer intermediario que reenvía bloques cuando A no llega directo a B (va A → C → B). Los administradores definen qué peers son relay y quiénes pueden usarlos. El relay nunca lee el archivo. Estado `relayed`.

**¿Cómo elige el mejor camino?**
El servidor junta métricas de cada peer, arma un grafo de la red con la calidad de cada enlace y calcula la ruta óptima (incluido cuándo conviene pasar por un relay).

**¿Qué pasa si se pierden más bloques que la paridad?**
Falla (`failed`): no hay suficiente información para reconstruir. Solución: más redundancia (lo hace la redundancia adaptativa).

**¿El servidor ve mis archivos?**
Nunca. Solo coordina (quién está online, dónde, cuánta redundancia). Los datos van directo peer-a-peer.

**¿Cómo decide cuánta redundancia?**
Mide RTT, jitter y pérdida, clasifica la calidad (excellent→critical) y sugiere 5%–50%. Usa el nivel más alto entre emisor y receptor.

**¿Qué es GF(2⁸)?**
El "campo de números" (aritmética de Galois de 256 elementos) donde RS hace sus cuentas byte a byte para generar y recuperar la paridad.

**¿Qué pasa si no se pueden ver directo (NAT/firewall)?**
Hay **relay**: un peer intermediario reenvía los bloques. Estado `relayed`.

---

## 5. Cómo levantar todo (referencia rápida)

```powershell
# 1) Servidor + Redis
cd server
docker compose up --build   # http://localhost:8080

# 2) Agente peer-alice
cd client/agent
$env:PEER_ID="peer-alice"; $env:SERVER_URL="http://localhost:8080"
$env:AGENT_API_URL="http://127.0.0.1:8000"; $env:UDP_PORT="9001"
uv run uvicorn main:app --app-dir src --host 127.0.0.1 --port 8000

# 3) Agente peer-bob (para envío real)
$env:PEER_ID="peer-bob"; $env:AGENT_API_URL="http://127.0.0.1:8001"; $env:UDP_PORT="9002"
uv run uvicorn main:app --app-dir src --host 127.0.0.1 --port 8001

# 4) UI
cd client/ui
npm run dev   # http://localhost:5173

# Para el segundo peer en otra pestaña, antes de conectar (DevTools console):
# localStorage.setItem("agentUrl", "http://127.0.0.1:8001")
```

> La pestaña **Demo RS** funciona con solo el agente en `:8000` (no necesita el segundo peer ni la red: simula todo en memoria).
