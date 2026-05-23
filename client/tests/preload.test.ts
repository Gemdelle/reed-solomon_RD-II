import { vi, it, expect, beforeEach, describe } from "vitest";

// Mock electron before any import that pulls it in
const exposeInMainWorld = vi.fn();
vi.mock("electron", () => ({
  contextBridge: { exposeInMainWorld },
  app: { isPackaged: false, whenReady: vi.fn().mockResolvedValue(undefined), on: vi.fn() },
  BrowserWindow: vi.fn(),
  shell: { openExternal: vi.fn() },
}));

beforeEach(() => {
  exposeInMainWorld.mockClear();
  vi.resetModules();
});

describe("preload", () => {
  it("exposes rsAgent with a baseUrl string on window", async () => {
    await import("../electron/preload");
    expect(exposeInMainWorld).toHaveBeenCalledOnce();
    const [key, api] = exposeInMainWorld.mock.calls[0] as [string, { baseUrl: string }];
    expect(key).toBe("rsAgent");
    expect(typeof api.baseUrl).toBe("string");
    expect(api.baseUrl).toMatch(/^http:\/\/127\.0\.0\.1:\d+/);
  });

  it("baseUrl uses port 8000 by default", async () => {
    delete process.env["AGENT_PORT"];
    await import("../electron/preload");
    const [, api] = exposeInMainWorld.mock.calls[0] as [string, { baseUrl: string }];
    expect(api.baseUrl).toBe("http://127.0.0.1:8000");
  });
});
