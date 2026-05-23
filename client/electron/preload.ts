import { contextBridge } from "electron";

// Expose the agent base URL so the UI can reach it.
// All API calls go to the local agent over HTTP — no direct Electron IPC needed for now.
contextBridge.exposeInMainWorld("rsAgent", {
  baseUrl: "http://127.0.0.1:8000",
});
