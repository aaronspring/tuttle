import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("tuttle", {
  rpc: (method: string, params: Record<string, unknown> = {}) =>
    ipcRenderer.invoke("rpc", method, params),
});
