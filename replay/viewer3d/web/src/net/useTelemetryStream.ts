import { useEffect } from "react";
import type { TelemetryMessage } from "./protocol";
import { useViewerStore } from "../state/store";

const DEFAULT_URL =
  import.meta.env.VITE_BRIDGE_URL ?? "ws://localhost:9998/ws";

/**
 * Subscribes to the bridge and feeds every message into the store.
 *
 * The bridge already coalesces to ~30 Hz and retains the track geometry, so
 * this hook stays deliberately dumb: parse, hand over, reconnect on drop.
 */
export function useTelemetryStream(url: string = DEFAULT_URL): void {
  const apply = useViewerStore((state) => state.apply);
  const setConnected = useViewerStore((state) => state.setConnected);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let disposed = false;

    const connect = () => {
      socket = new WebSocket(url);

      socket.onopen = () => setConnected(true);

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data as string);
          if (message.type === "source_status") {
            setConnected(message.connected === true);
            return;
          }
          apply(message as TelemetryMessage);
          setConnected(true);
        } catch {
          // Ignore malformed frames; the next flush will replace the state.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (!disposed) {
          retryTimer = window.setTimeout(connect, 1000);
        }
      };

      socket.onerror = () => socket?.close();
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [url, apply, setConnected]);
}
