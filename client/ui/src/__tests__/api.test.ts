import { describe, it, expect, vi, beforeEach } from "vitest";
import { getAgentUrl, getServerUrl, agentApi, serverApi } from "../api";

// ── localStorage stub (env's native impl doesn't expose .clear) ───────────────
const _ls: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (k: string) => _ls[k] ?? null,
  setItem: (k: string, v: string) => { _ls[k] = v; },
  removeItem: (k: string) => { delete _ls[k]; },
  clear: () => { Object.keys(_ls).forEach((k) => delete _ls[k]); },
});

// ── fetch stub ────────────────────────────────────────────────────────────────
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function respondWith(data: unknown, ok = true, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok,
    status,
    json: async () => data,
    text: async () => (ok ? "" : String(data)),
  } as Response);
}

beforeEach(() => {
  mockFetch.mockReset();
  Object.keys(_ls).forEach((k) => delete _ls[k]);
  delete (window as { rsAgent?: unknown }).rsAgent;
});

// ── URL helpers ───────────────────────────────────────────────────────────────

describe("getAgentUrl", () => {
  it("returns window.rsAgent.baseUrl when set", () => {
    (window as { rsAgent?: { baseUrl: string } }).rsAgent = { baseUrl: "http://10.0.0.5:8000" };
    expect(getAgentUrl()).toBe("http://10.0.0.5:8000");
  });

  it("falls back to localStorage agentUrl", () => {
    _ls["agentUrl"] = "http://192.168.1.10:8000";
    expect(getAgentUrl()).toBe("http://192.168.1.10:8000");
  });

  it("falls back to hardcoded localhost default", () => {
    expect(getAgentUrl()).toBe("http://localhost:8000");
  });
});

describe("getServerUrl", () => {
  it("returns localStorage serverUrl when set", () => {
    _ls["serverUrl"] = "http://my-server:8080";
    expect(getServerUrl()).toBe("http://my-server:8080");
  });

  it("returns default when not set", () => {
    expect(getServerUrl()).toBe("http://localhost:8080");
  });
});

// ── agentApi ──────────────────────────────────────────────────────────────────

describe("agentApi.health", () => {
  it("calls /health and returns body", async () => {
    respondWith({ status: "ok" });
    const result = await agentApi.health();
    expect(result).toEqual({ status: "ok" });
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining("/health"));
  });
});

describe("agentApi.listFiles", () => {
  it("GET /files returns array", async () => {
    const files = [{ file_id: "f1", filename: "a.txt", sha256: "x", size: 5, created_at: "" }];
    respondWith(files);
    const result = await agentApi.listFiles();
    expect(result).toHaveLength(1);
    expect(result[0].file_id).toBe("f1");
  });
});

describe("agentApi.uploadFile", () => {
  it("POST /files with FormData", async () => {
    respondWith({ file_id: "new-id", filename: "up.txt", sha256: "h", size: 3, created_at: "" });
    const file = new File(["abc"], "up.txt", { type: "text/plain" });
    const result = await agentApi.uploadFile(file);
    expect(result.file_id).toBe("new-id");
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/files");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
});

describe("agentApi.deleteFile", () => {
  it("DELETE /files/{id}", async () => {
    respondWith({ deleted: "file-123" });
    const result = await agentApi.deleteFile("file-123");
    expect(result.deleted).toBe("file-123");
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/files/file-123");
    expect(init.method).toBe("DELETE");
  });
});

describe("agentApi.sendFile", () => {
  it("POST /transfer/send with correct body", async () => {
    const mockResult = {
      transfer_id: "tid",
      status: "ok",
      recovered_blocks: 0,
      total_blocks: 24,
      file_id: "fid",
      reason: null,
    };
    respondWith(mockResult);
    const result = await agentApi.sendFile("file-1", "peer-B", 0.25);
    expect(result.status).toBe("ok");
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.file_id).toBe("file-1");
    expect(body.target_peer_id).toBe("peer-B");
    expect(body.redundancy_level).toBe(0.25);
  });

  it("sends null redundancy_level when omitted", async () => {
    respondWith({ transfer_id: "t", status: "ok", recovered_blocks: 0, total_blocks: 0, file_id: null, reason: null });
    await agentApi.sendFile("f", "p");
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.redundancy_level).toBeNull();
  });
});

describe("agentApi.listTransfers", () => {
  it("GET /transfer returns array", async () => {
    respondWith([{ transfer_id: "t1", status: "ok", recovered_blocks: 0, total_blocks: 24, file_id: null, reason: null }]);
    const result = await agentApi.listTransfers();
    expect(result).toHaveLength(1);
  });
});

// ── serverApi ─────────────────────────────────────────────────────────────────

describe("serverApi.health", () => {
  it("calls the provided server URL", async () => {
    respondWith({ status: "ok" });
    await serverApi.health("http://myserver:8080");
    expect(mockFetch).toHaveBeenCalledWith("http://myserver:8080/health");
  });
});

describe("serverApi.authConfig", () => {
  it("calls /auth/config", async () => {
    respondWith({ oidc_enabled: false, issuer: null, client_id: null });
    const result = await serverApi.authConfig("http://server:8080");
    expect(result.oidc_enabled).toBe(false);
  });
});

describe("serverApi.getRecommendation", () => {
  it("calls /metrics/recommendation/{peerId}", async () => {
    respondWith({ peer_id: "p1", redundancy_level: 0.10, quality: "good", based_on_samples: 5, profile_name: "Wi-Fi" });
    const result = await serverApi.getRecommendation("p1");
    expect(result.redundancy_level).toBe(0.10);
    expect(result.profile_name).toBe("Wi-Fi");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/metrics/recommendation/p1"),
      expect.anything(),
    );
  });
});

// ── Error handling ────────────────────────────────────────────────────────────

describe("error handling", () => {
  it("throws on non-ok response with status code", async () => {
    respondWith("Not Found", false, 404);
    await expect(agentApi.health()).rejects.toThrow("404");
  });
});
