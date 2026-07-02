# RockDove — Guion del Final (10 min)

Documento para estudiar y repartir en el grupo. Tiene 3 partes:
1. **Cómo funciona** (explicado fácil).
2. **Guion de 10 minutos** (5 personas × 2 min).
3. **La demo paso a paso** (los 3 casos) + preguntas típicas.

---

## 1. Cómo funciona RockDove (fácil)

### El problema
Cuando mandás un archivo por una red mala (satélite, celular, redes industriales), se **pierden pedacitos** en el camino. Lo normal (TCP) es pedir "reenviame ese pedazo", pero eso es **lento** y a veces **imposible** (enlaces de una sola vía, mucha latencia).

### La idea (Reed-Solomon / FEC)
Antes de mandar, el archivo se corta en pedazos y se le agregan **pedazos de respaldo hechos con matemática**. El que recibe solo necesita *suficientes* pedazos (cualquiera) para **rearmar todo, sin pedir nada de vuelta**.

> 📖 **Analogía:** mandás un libro de 30 páginas como 32 (2 de respaldo "mágicas"). Si se pierden 2 en el correo, el receptor las reconstruye solo. Si el correo es un desastre, mandás más respaldos.

Esto se llama **FEC (Forward Error Correction)** y el algoritmo concreto es **Reed-Solomon**.

### La gran decisión de diseño: dos planos separados

| Plano | Quién | Qué hace | ¿Ve el archivo? |
|-------|-------|----------|:---------------:|
| **Control** | Servidor central (en la nube) | Guía telefónica: quién está online, dónde, y "cuánto respaldo conviene" | ❌ Nunca |
| **Datos** | Agente (uno por máquina) | Corta/rearma con Reed-Solomon y manda el archivo **directo** a la otra máquina | ✅ |

> 📞 **Analogía:** el servidor es un amigo que te da la dirección de tu compañero. Después vos vas **directo** a su casa a entregar el paquete. El amigo nunca toca el paquete. (Igual que Tailscale o Syncthing.)

### Redundancia adaptativa
El sistema **mide la red** (ping, jitter, pérdida). Red buena → pocos respaldos (rápido). Red mala → muchos respaldos (seguro). **Automático**, el usuario no toca nada. Usa el nivel más alto entre lo que necesita el que manda y el que recibe (se protege según el extremo más débil).

### Canal: UDP vs QUIC
- **UDP** = tirar postales: rápido, sin garantía, sin cifrado.
- **QUIC** = igual de rápido pero **cifrado y con identidad verificada** (certificado). Usa modo *datagram* que **no reenvía a propósito**, para no pisar el trabajo de Reed-Solomon.

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

## 2. Guion de 10 minutos — 5 personas × 2 min

### 🎤 Persona 1 — El gancho / el problema (2 min)
- Transferir archivos en redes malas pierde paquetes.
- TCP reenvía = caro y lento en satélite/celular/enlaces de una vía.
- Presentar la idea: **agregar respaldo matemático para no tener que reenviar**.
- Analogía del libro con páginas de respaldo.
- *Objetivo: enganchar. Cerrar diciendo "esto es RockDove".*

### 🎤 Persona 2 — Arquitectura / dos planos (2 min)
- **Plano de control** (servidor = guía telefónica, nunca ve el archivo).
- **Plano de datos** (agente en cada máquina, transferencia **directa P2P**).
- Mostrar el diagrama C4 de contenedores del informe.
- Analogía Tailscale/Syncthing.
- *Cierre: "el servidor coordina, pero los datos viajan directo y protegidos".*

### 🎤 Persona 3 — El corazón: Reed-Solomon (2 min) — *lo más de la materia*
- n = 32 bloques (k datos + paridad).
- **Cualquier k de n reconstruye todo** → modo *erasure* sobre GF(2⁸).
- Mostrar la **tabla de redundancia** (5% → tolera 5% … 50% → tolera 50%).
- Mencionar la **redundancia adaptativa** (se ajusta según la calidad de red medida).
- *Cierre: "ahora lo mostramos funcionando".*

### 🎤 Persona 4 — DEMO parte 1: envío real + canal (2 min)
- Abrir RockDove, mostrar peers online.
- Enviar un archivo real de un peer a otro.
- Mostrar la **recomendación automática** de redundancia (excellent/good/fair…).
- Mostrar el toggle **UDP vs QUIC** (y en QUIC, la aprobación por certificado).
- *Cierre: "pero, ¿qué pasa cuando la red pierde paquetes? Lo vemos con imágenes".*

### 🎤 Persona 5 — DEMO parte 2: los 3 casos + cierre (2 min)
- Ir a la pestaña **Demo RS**. Subir una imagen.
- **Caso A:** redundancia 25%, pérdida 0% → `ok`, imagen perfecta.
- **Caso B:** redundancia 25%, pérdida 20% → `degraded`, RS reconstruye → imagen igual perfecta (mostrar el panel "Sin RS" roto vs "Con RS" perfecto).
- **Caso C:** redundancia 25%, pérdida 40% → `failed`, imagen rota → **subir redundancia a 50%** → se salva.
- *Cierre: conclusiones (servidor liviano, datos privados, resiliencia sin reenvío, aprende de la red).*

---

## 3. La demo paso a paso

### Antes de empezar (checklist)
1. Servidor + Redis corriendo (`http://localhost:8080`).
2. Agente `peer-alice` en `http://127.0.0.1:8000`.
3. (Para la parte 1, envío real) segundo agente `peer-bob` en `http://127.0.0.1:8001`.
4. UI en `http://localhost:5173/`.
5. Tener a mano **una imagen** (PNG o JPG) con formas/colores claros (una foto o un logo grande se ve mejor cuando se rompe).

### Parte 1 — Envío real (Persona 4)
1. Conectarse como `peer-alice`.
2. En el dashboard, ver los peers online (el pajarito indica conectado).
3. Elegir un archivo → enviar a `peer-bob`.
4. Mostrar la **recomendación de redundancia** (chip de calidad).
5. Cambiar el transporte **UDP ↔ QUIC** y comentar la diferencia (QUIC = cifrado + aprobación por certificado).
6. Ver el resultado `ok` y el historial.

> Nota: en la misma computadora (localhost) casi no hay pérdida real, así que el envío real da `ok`. Para mostrar pérdida y reconstrucción usamos la **Demo RS** (parte 2), que simula el canal.

### Parte 2 — Demo RS (Persona 5) — la estrella visual
Pestaña **"Demo RS"** en el menú lateral.

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

**¿Por qué QUIC usa datagrams sin retransmisión?**
Si QUIC reenviara solo, pisaría el modelo de "borrado" de RS. Con DATAGRAM (RFC 9221) QUIC aporta cifrado e identidad sin cambiar la semántica de pérdida que RS necesita.

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
