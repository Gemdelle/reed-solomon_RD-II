# RockDove — Infraestructura de Red y Requerimientos del Underlay

## Principio central

RockDove es un **overlay de aplicación**: coordina peers, aplica FEC y abstrae la distribución.
No es una red por sí misma — depende del underlay para que los sockets sean alcanzables.

```
┌─────────────────────────────────────────────────────────┐
│                   ROCKDOVE (overlay)                     │
│  peer discovery · FEC adaptativo · distribución P2P      │
└──────────────────────────┬──────────────────────────────┘
                           │ depende de reachability IP
┌──────────────────────────▼──────────────────────────────┐
│                UNDERLAY DE RED (infraestructura)         │
│  LAN · VPN · MPLS · SD-WAN · Internet + NAT              │
└─────────────────────────────────────────────────────────┘
```

Cada capa tiene responsabilidades claras:

| Responsabilidad | RockDove | Underlay |
|---|---|---|
| Descubrimiento de peers | ✅ rendezvous server | |
| Identidad y auth | ✅ Keycloak OIDC + device tokens | |
| FEC y resiliencia de datos | ✅ Reed-Solomon | |
| Segmentación organizacional | ✅ realms + groups | ✅ VLANs / WireGuard peers |
| Reachability IP entre nodos | | ✅ routing + NAT policy |
| Cifrado de transporte | *(pendiente: QUIC)* | ✅ WireGuard / TLS / IPsec |
| Traversal de NAT simétrico | *(relay nativo pendiente)* | ✅ VPN / port forwarding |

---

## Requerimiento fundamental

**El puerto UDP 9001 del agente receptor debe ser alcanzable desde el agente emisor.**

El servidor central solo necesita **8080 TCP** abierto. No está en el camino de datos.

Si hay NAT entre emisor y receptor, el socket UDP no es alcanzable por defecto. Las opciones para
resolverlo están en la sección de escenarios abajo.

---

## Escenarios de despliegue

### Escenario 1 — LAN corporativa

```
[Peer A] ──────── switch ──────── [Peer B]
          red interna, sin NAT
```

**Soporte:** nativo. Sin configuración de red adicional.

- Todos los peers están en el mismo segmento o tienen routing interno.
- `AGENT_API_URL` apunta a la IP privada del agente (ej. `http://192.168.1.10:8000`).
- El servidor puede estar en la misma LAN o en cloud; solo necesita alcanzabilidad TCP 8080.

**Recomendación de redundancia:** perfil `lan` (r = 0.05 — overhead mínimo).

---

### Escenario 2 — VPN corporativa (WireGuard / Tailscale / NetBird / ZeroTier)

```
[Peer A] ──── VPN overlay ──── [Peer B]
              10.x.x.x/24
```

**Soporte:** recomendado — el escenario ideal para RockDove.

La VPN resuelve reachability, routing y traversal de NAT. RockDove opera encima sin cambios.
`AGENT_API_URL` y `UDP_HOST` apuntan a la IP del tunnel VPN.

**WireGuard en particular** habilita:

- Segmentación por grupos de peers usando `AllowedIPs` — los peers solo ven el segmento que les
  corresponde, complementando la segmentación lógica de RockDove (realms + groups).
- Cifrado punto a punto del túnel, independiente de RockDove.
- Peers móviles/remotos con IP fija de tunnel, sin depender de IP pública.

**Stack resultante:**
```
RockDove FEC + coordinación
    encima de
WireGuard / Tailscale (reachability + cifrado + segmentación L3)
    encima de
Internet / MPLS / LTE
```

Cada capa hace exactamente una cosa. El resultado es un sistema más robusto que cualquier
solución monolítica.

**Recomendación de redundancia:** perfil `wifi` o `cellular` según la calidad del uplink físico.

---

### Escenario 3 — Internet pública con port forwarding

```
[Peer A]             firewall / NAT             [Peer B]
NAT privado ── Internet ── port forwarding ── IP pública
                                UDP 9001 → 192.168.x.y:9001
```

**Soporte:** parcial. Requiere configuración manual en cada peer receptor.

- El receptor necesita una IP pública o regla de DNAT hacia su puerto UDP 9001.
- Funciona para topologías hub-and-spoke (un servidor central con IP fija recibe de clientes
  detrás de NAT).
- No funciona en NAT simétrico sin intervención adicional (ver relay nativo más abajo).

`AGENT_API_URL` debe ser la IP/hostname público del peer, no `127.0.0.1`.

**Limitación actual:** RockDove no implementa STUN/ICE/hole punching activo. Si ambos peers
están detrás de NAT sin port forwarding, la transferencia UDP directa no es posible sin un relay.

---

### Escenario 4 — Firewall enterprise (Fortinet / Palo Alto)

```
[LAN A] ── Fortinet ── MPLS / Internet ── Palo Alto ── [LAN B]
           policies: UDP 9001 permitido entre segmentos
```

**Soporte:** depende de políticas. RockDove no requiere configuración especial del firewall,
pero necesita que UDP 9001 esté permitido entre los segmentos de peers participantes.

Consideraciones:

- Deep Packet Inspection (DPI) no afecta RockDove — los bloques UDP no están en plaintext
  de aplicación, son payloads RS binarios. *Con QUIC futuro, habrá cifrado completo.*
- Las políticas de segmentación del firewall pueden complementar (o reemplazar) la segmentación
  por groups de RockDove para entornos con postura de seguridad estricta.
- En SD-WAN con múltiples uplinks, RockDove puede beneficiarse de la redundancia del path
  porque FEC se combina con path diversity.

---

### Escenario 5 — Link satelital / celular degradado

```
[HQ / datacenter] ── uplink satelital ── [Site remoto]
                     alta latencia, pérdida variable
```

**Soporte:** es el caso de uso para el que RockDove está optimizado.

- El perfil `satellite` activa redundancia r = 0.50 (50% de paquetes perdidos tolerables).
- El `NETWORK_HINT=satellite` en el agente del site remoto guía al servidor a recomendar
  redundancia alta automáticamente.
- La transferencia es unidireccional: el HQ envía, el site reconstruye sin retransmitir.
  Esto elimina el costo de round-trips sobre links de alta latencia.

**Relay como nodo concentrador:** en este escenario tiene sentido que el site remoto actúe
como relay para redistribuir localmente en LAN lo que recibió del uplink satelital, evitando
que cada dispositivo edge haga su propio uplink.

---

### Escenario 6 — Relay nativo RockDove (roadmap)

Para escenarios donde la conectividad directa no es posible (NAT simétrico, peers móviles sin
VPN, redes industriales segmentadas), RockDove puede operar un relay propio:

```
[Peer A] ──► [Relay peer C] ──► [Peer B]
             store-and-forward
             re-encode FEC por hop
```

El relay es un peer RockDove con `relay_capable=true` en su registro. El servidor puede
sugerir rutas multi-hop cuando detecta que el path directo no está disponible.

Ver sección de relay en el TODO para el estado de implementación.

---

## Matriz de escenarios

| Escenario | Soporte actual | Configuración requerida |
|---|---|---|
| LAN corporativa (mismo segmento) | ✅ Nativo | Ninguna |
| LAN con routing entre VLANs | ✅ Nativo | Reglas de routing internas |
| VPN WireGuard / Tailscale | ✅ Recomendado | IP del tunnel en `AGENT_API_URL` |
| MPLS / SD-WAN corporativo | ✅ Con políticas | UDP 9001 permitido |
| Internet + port forwarding | ⚠️ Parcial | DNAT hacia UDP 9001 en receptor |
| NAT simétrico sin VPN | ❌ No soportado | Requiere relay (roadmap) |
| Link satelital / celular | ✅ Optimizado | `NETWORK_HINT=satellite` en agente |
| Redes industriales aisladas | ✅ Con relay local | Relay peer en el segmento |

---

## Recomendación operacional

Para producción, el stack recomendado es:

```
RockDove
  │  coordina peers, aplica FEC, gestiona identidad
  └─► sobre WireGuard o Tailscale
        │  resuelve reachability, NAT, cifrado L3
        └─► sobre el underlay físico (LAN / Internet / celular / satélite)
```

Esto permite:

- RockDove enfocado en resiliencia y distribución de datos.
- La VPN manejando la complejidad de red (NAT, routing, cifrado).
- Separación de responsabilidades limpia — cada capa reemplazable independientemente.

Para entornos sin VPN corporativa, el relay nativo de RockDove (roadmap P2) cubre el caso de
NAT sin necesidad de infraestructura adicional.

---

## Puertos requeridos

| Puerto | Protocolo | Componente | Quién lo necesita abierto |
|---|---|---|---|
| 8080 | TCP | Servidor central | Todos los peers (HTTPS hacia el servidor) |
| 8000 | TCP | Agente HTTP | Solo el Electron local (127.0.0.1) |
| 9001 | UDP | Agente UDP | Peers emisores entrantes |

El puerto 9001 UDP es el único que requiere reglas en firewalls intermedios entre peers.
El servidor central no necesita UDP abierto en ningún momento.
