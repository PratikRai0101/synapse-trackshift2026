/**
 * Telemetry bridge: raw TCP (arcade replay) -> WebSocket (browser viewer).
 *
 * The existing `TelemetryStreamServer` in the Python app publishes
 * newline-delimited JSON on localhost:9999 at roughly the replay tick rate
 * (~60 Hz). Browsers cannot open raw TCP sockets, so this process sits in
 * between:
 *
 *     arcade replay (:9999, TCP)  ->  bridge  ->  viewer (:9998, WS)
 *
 * Two jobs, and nothing else:
 *
 *  1. Coalesce. Keep only the newest payload and flush at FLUSH_HZ so the
 *     renderer is not asked to re-render 60x/sec.
 *  2. Retain "sticky" fields. The source only emits `track_geometry` every
 *     ~120 frames. If coalescing dropped that packet the viewer would never
 *     receive the track mesh, so the last value is merged into every outgoing
 *     message.
 *
 * No imports from the Python app. The JSON payload is the only contract.
 */

import type { ServerWebSocket } from "bun";

const TELEMETRY_HOST = process.env.TELEMETRY_HOST ?? "127.0.0.1";
const TELEMETRY_PORT = Number(process.env.TELEMETRY_PORT ?? 9999);
const WS_PORT = Number(process.env.WS_PORT ?? 9998);
const FLUSH_HZ = Number(process.env.FLUSH_HZ ?? 30);
const RECONNECT_MS = 2000;

type Payload = Record<string, unknown>;
type Client = ServerWebSocket<undefined>;

/**
 * Fields the source sends intermittently. The latest seen value is retained
 * and re-injected whenever an outgoing payload omits them.
 */
const STICKY_FIELDS = ["track_geometry", "driver_colors", "has_rc_data"] as const;

/**
 * Fields the source repeats on every tick that this viewer does not read.
 * The live server attaches the full precomputed `lap_times` / `status_laps`
 * tables to every broadcast (~60x/sec), so forwarding them would waste most of
 * the socket. Strip them here; override with STRIP_FIELDS if a future panel
 * needs them.
 */
const STRIP_FIELDS = new Set(
  (process.env.STRIP_FIELDS ?? "lap_times,status_laps")
    .split(",")
    .map((field) => field.trim())
    .filter(Boolean),
);

let latest: Payload | null = null;
let sourceUp = false;
let framesIn = 0;
let reconnecting = false;

const sticky: Record<string, unknown> = {};
const clients = new Set<Client>();

function ingest(line: string): void {
  let parsed: Payload;
  try {
    parsed = JSON.parse(line) as Payload;
  } catch {
    return; // partial/garbled line; the next newline-delimited message will parse
  }

  framesIn += 1;

  for (const field of STICKY_FIELDS) {
    if (parsed[field] != null) sticky[field] = parsed[field];
  }
  for (const [key, value] of Object.entries(sticky)) {
    if (parsed[key] == null) parsed[key] = value;
  }

  for (const field of STRIP_FIELDS) {
    if (field in parsed) delete parsed[field];
  }

  latest = parsed;
}

async function connectSource(): Promise<void> {
  // A fresh decoder/buffer per connection so a mid-message reconnect can never
  // splice bytes from two different sockets together.
  const decoder = new TextDecoder();
  let buffer = "";

  const scheduleReconnect = () => {
    sourceUp = false;
    if (reconnecting) return;
    reconnecting = true;
    setTimeout(() => {
      reconnecting = false;
      void connectSource();
    }, RECONNECT_MS);
  };

  try {
    await Bun.connect({
      hostname: TELEMETRY_HOST,
      port: TELEMETRY_PORT,
      socket: {
        open() {
          sourceUp = true;
          reconnecting = false;
          console.log(
            `[bridge] source connected ${TELEMETRY_HOST}:${TELEMETRY_PORT}`,
          );
        },
        data(_socket, chunk) {
          buffer += decoder.decode(chunk, { stream: true });
          let newline = buffer.indexOf("\n");
          while (newline >= 0) {
            const line = buffer.slice(0, newline);
            buffer = buffer.slice(newline + 1);
            if (line.trim()) ingest(line);
            newline = buffer.indexOf("\n");
          }
        },
        close() {
          console.warn("[bridge] source closed, reconnecting...");
          scheduleReconnect();
        },
        error(_socket, error) {
          console.warn(`[bridge] socket error: ${error.message}`);
        },
        connectError() {
          // Source not running yet (replay not started). Stay quiet and retry.
          scheduleReconnect();
        },
      },
    });
  } catch {
    scheduleReconnect();
  }
}

const server = Bun.serve({
  port: WS_PORT,
  fetch(request, srv) {
    const url = new URL(request.url);

    if (url.pathname === "/ws") {
      if (srv.upgrade(request)) return undefined;
      return new Response("websocket upgrade failed", { status: 400 });
    }

    if (url.pathname === "/health") {
      return Response.json({
        source: `${TELEMETRY_HOST}:${TELEMETRY_PORT}`,
        sourceUp,
        framesIn,
        clients: clients.size,
        haveGeometry: sticky.track_geometry != null,
        flushHz: FLUSH_HZ,
      });
    }

    return new Response("not found", { status: 404 });
  },
  websocket: {
    open(ws) {
      clients.add(ws);
      // Late joiners get the current state (including retained geometry)
      // immediately instead of waiting for the next flush.
      if (latest) ws.send(JSON.stringify(latest));
    },
    message() {
      // The viewer is read-only. Inbound messages are ignored.
    },
    close(ws) {
      clients.delete(ws);
    },
  },
});

setInterval(() => {
  if (!latest || clients.size === 0) return;
  const message = JSON.stringify(latest);
  for (const client of clients) {
    try {
      client.send(message);
    } catch {
      clients.delete(client);
    }
  }
}, 1000 / FLUSH_HZ);

console.log(`[bridge] websocket listening on ws://localhost:${server.port}/ws`);
console.log(
  `[bridge] waiting for telemetry on tcp://${TELEMETRY_HOST}:${TELEMETRY_PORT}`,
);
void connectSource();
