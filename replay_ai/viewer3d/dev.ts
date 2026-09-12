/**
 * Dev orchestrator: starts the telemetry bridge and the Vite dev server
 * together, and shuts both down when either exits or the user hits Ctrl-C.
 *
 *     bun run dev
 *
 * The bridge tolerates a missing source (it retries every 2s), so this can be
 * started before the replay or the mock, in any order.
 */

const procs = [
  Bun.spawn(["bun", "run", "bridge/index.ts"], {
    cwd: import.meta.dir,
    stdio: ["inherit", "inherit", "inherit"],
  }),
  Bun.spawn(["bun", "run", "dev"], {
    cwd: `${import.meta.dir}/web`,
    stdio: ["inherit", "inherit", "inherit"],
  }),
];

let shuttingDown = false;
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const proc of procs) {
    try {
      proc.kill();
    } catch {
      // already gone
    }
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

await Promise.race(procs.map((proc) => proc.exited));
shutdown(0);
