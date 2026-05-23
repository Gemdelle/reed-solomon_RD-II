# client/ui — Frontend Guidelines

React 18 + Vite + TypeScript + Tailwind SPA. Corre dentro del Electron shell o como SPA standalone. Habla exclusivamente con el agent local (`localhost:8000`) y con el servidor de control (`localhost:8080`). No hay backend propio de UI.

Leer [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) y [../../docs/RULES.md](../../docs/RULES.md) antes de tocar cualquier cosa.

---

## Stack

| Capa | Herramienta |
|------|-------------|
| Framework | React 18, TypeScript strict |
| Build | Vite 5 |
| Estilos | Tailwind CSS 3 — paleta dark slate + token `brand-*` |
| Auth | `oidc-client-ts` — no tocar el flujo OIDC sin leer `auth/oidc.ts` |
| Tests | Vitest + happy-dom |

**No hay otras dependencias instaladas.** Antes de agregar una librería, justificar por qué Tailwind + fetch + React hooks no alcanzan.

---

## Lo que NO se debe hacer

### Fetch directo en componentes
```tsx
// MAL — nunca
const res = await fetch("http://localhost:8000/files/");

// BIEN — siempre a través de la capa de API
const files = await agentApi.listFiles();
```

### Hardcodear URLs o puertos
```tsx
// MAL
fetch("http://localhost:8000/transfer/send", ...)
fetch("http://localhost:8080/peers", ...)

// BIEN — usar los helpers de api.ts
import { getAgentUrl, getServerUrl } from "../api";
```

### Leer el token JWT directamente en componentes
```tsx
// MAL
const token = localStorage.getItem("token");
headers: { Authorization: `Bearer ${token}` }

// BIEN — authHeaders() en api.ts lo maneja
// Los métodos de agentApi y serverApi ya incluyen el header
```

### Leer localStorage en componentes (salvo App.tsx)
El único lugar que lee/escribe `serverUrl`, `peerId`, `token` desde localStorage es `App.tsx` en `loadConfig()`. Los componentes reciben config por props.

### Agregar routing
No hay React Router ni ningún router. La navegación es por estado: `config === null` → `ConnectPage`, `config !== null` → `DashboardPage`. No agregar rutas.

### Agregar estado global
No hay Redux, Zustand, Context ni similar. El estado compartido se pasa como props desde `App.tsx`. Si algo necesita estado global es una señal de que el diseño está roto.

### Definir tipos fuera de `types.ts`
Todos los tipos que reflejan respuestas de API o modelos del dominio van en `src/types.ts`. Interfaces locales de props de componentes van inline en el mismo archivo del componente.

### Agregar funciones de API fuera de `api.ts`
Todo call a `fetch` vive en `api.ts` dentro de `agentApi` o `serverApi`. Si un endpoint nuevo no está ahí, se agrega ahí.

### Usar CSS modules, styled-components o estilos inline
Solo Tailwind. Clases de color siempre del tema dark slate (`slate-950`, `slate-900`, `slate-800`, etc.) + el token `brand-*` definido en `tailwind.config.js`.

### Acceder a APIs de Electron sin guard
```tsx
// MAL — rompe en modo web
window.rsAgent.openExternal(url);

// BIEN — siempre conditional
if (window.rsAgent?.openExternal) {
  window.rsAgent.openExternal(url);
}
```

---

## Lo que debe tener toda adición

### Toda operación async necesita estado de loading + error

```tsx
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);

async function doSomething() {
  setLoading(true);
  setError(null);
  try {
    await agentApi.someCall();
  } catch (e) {
    setError((e as Error).message);
  } finally {
    setLoading(false);
  }
}
```

### Todo botón async debe estar disabled mientras carga

```tsx
<button disabled={loading || !requiredField} ...>
  {loading ? "Procesando…" : "Confirmar"}
</button>
```

### Efectos con cleanup

```tsx
useEffect(() => {
  const interval = setInterval(poll, 5000);
  return () => clearInterval(interval);
}, [dep]);
```

---

## Estructura de archivos

```
src/
├── api.ts          ← todos los fetch. Tocar solo acá para agregar endpoints
├── types.ts        ← todos los tipos de dominio
├── App.tsx         ← routing por estado, OIDC callback, loadConfig()
├── auth/
│   └── oidc.ts     ← flujo OIDC, no tocar sin entenderlo completo
├── pages/
│   ├── ConnectPage.tsx    ← dos pasos: server URL → SSO login
│   └── DashboardPage.tsx  ← WebSocket peer watch, layout principal
└── components/
    ├── FileList.tsx
    ├── PeerList.tsx
    ├── TransferDialog.tsx
    ├── TransferHistory.tsx
    └── AdminPanel.tsx
```

Un componente por archivo. Si un panel tiene sub-tabs con lógica propia (como `AdminPanel`), las sub-tabs van como funciones locales en el mismo archivo — no crear un archivo por tab.

---

## Patterns de diseño

### Modal overlay

Todos los diálogos flotantes usan este patrón. Cierre con click en overlay, no cerrar si está en proceso.

```tsx
const overlayRef = useRef<HTMLDivElement>(null);

function handleOverlayClick(e: React.MouseEvent) {
  if (e.target === overlayRef.current && !loading) onClose();
}

return (
  <div
    ref={overlayRef}
    onClick={handleOverlayClick}
    className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
  >
    <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-md">
      ...
    </div>
  </div>
);
```

### Status badge con mapa de colores

Para mostrar estados con colores distintos, usar un `Record` en vez de if-chains:

```tsx
const STATUS_COLORS: Record<string, string> = {
  ok:       "text-emerald-400 bg-emerald-950/50 border-emerald-800",
  degraded: "text-yellow-400 bg-yellow-950/50 border-yellow-800",
  failed:   "text-red-400 bg-red-950/50 border-red-800",
  unknown:  "text-slate-400 bg-slate-800/50 border-slate-700",
};

const cls = STATUS_COLORS[status] ?? STATUS_COLORS.unknown;
```

### Error banner inline

Formato estándar para mostrar errores dentro de un panel:

```tsx
{error && (
  <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
    {error}
  </p>
)}
```

### Panel con tabs

Cuando un panel tiene múltiples secciones, definir las secciones como componentes locales y un tipo union para el tab activo:

```tsx
type Tab = "seccion-a" | "seccion-b";

const TAB_LABELS: Record<Tab, string> = {
  "seccion-a": "Label A",
  "seccion-b": "Label B",
};

function SeccionATab() { ... }
function SeccionBTab() { ... }

export default function MiPanel({ onClose }: Props) {
  const [tab, setTab] = useState<Tab>("seccion-a");
  ...
}
```

### Acciones en lista con group-hover

Para no saturar la UI, las acciones por ítem se muestran solo al hacer hover:

```tsx
<li className="flex items-center gap-3 px-4 py-3 hover:bg-slate-800/40 group transition-colors">
  <div className="flex-1 min-w-0">...</div>
  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
    <button>Acción</button>
  </div>
</li>
```

### WebSocket con auto-reconnect

```tsx
const wsRef = useRef<WebSocket | null>(null);

useEffect(() => {
  let retryTimer: ReturnType<typeof setTimeout>;

  function connect() {
    const ws = serverApi.watchPeers(serverUrl, token);
    wsRef.current = ws;
    ws.onopen = () => setOnline(true);
    ws.onmessage = (ev) => { /* parse ev.data */ };
    ws.onerror = () => setOnline(false);
    ws.onclose = () => {
      setOnline(false);
      retryTimer = setTimeout(connect, 5000);
    };
  }

  connect();
  return () => {
    clearTimeout(retryTimer);
    wsRef.current?.close();
  };
}, [serverUrl, token]);
```

### Polling con interval

```tsx
useEffect(() => {
  load();
  const interval = setInterval(load, 5000);
  return () => clearInterval(interval);
}, [load]); // load debe ser useCallback con deps estables
```

---

## Dónde vive cada responsabilidad

| Responsabilidad | Dónde |
|-----------------|-------|
| Fetch + headers auth | `api.ts` |
| Tipos de respuesta API | `types.ts` |
| Detección Electron vs web | Guards `window.rsAgent?.xxx` en componente |
| Config de sesión (serverUrl, peerId, token) | `App.tsx` → `loadConfig()` → pasado como `AppConfig` por props |
| Flujo OIDC | `auth/oidc.ts` (no duplicar lógica en componentes) |
| Lógica de negocio RS | **NO en el frontend** — el agent la resuelve |

---

## Tests

Los tests viven en `src/__tests__/`. Usar Vitest + happy-dom.

- Testear funciones puras de `api.ts` mockeando `fetch` globalmente
- No testear estilos Tailwind ni estructura DOM
- Un test que mockea `agentApi` directamente es aceptable para componentes

Correr con:
```bash
npm run test          # desde client/ui/
npm run test:watch
```
