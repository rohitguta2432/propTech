/**
 * Tiny scoped logger. Each scope produces a `[propcheck:<scope>]` prefix
 * so logs from individual content scripts are easy to filter in DevTools.
 * Production builds keep `info` enabled at the same volume — the payloads
 * are small and seeing badge events from the page console is useful when
 * triaging "why didn't a badge appear" reports.
 */

type Level = "info" | "warn" | "error" | "debug";

export interface Logger {
  info: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
  debug: (...args: unknown[]) => void;
}

export function createLogger(scope: string): Logger {
  const prefix = `[propcheck:${scope}]`;
  const emit = (level: Level, args: unknown[]): void => {
    // Group all four into a single console call so DevTools stack-traces
    // point at the caller, not this helper.
    const fn = console[level] ?? console.log;
    fn.call(console, prefix, ...args);
  };
  return {
    info: (...a) => emit("info", a),
    warn: (...a) => emit("warn", a),
    error: (...a) => emit("error", a),
    debug: (...a) => emit("debug", a),
  };
}
