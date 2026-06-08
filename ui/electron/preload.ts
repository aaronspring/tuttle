import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("tuttle", {
  rpc: (method: string, params: Record<string, unknown> = {}) =>
    ipcRenderer.invoke("rpc", method, params),
  readFile: (filePath: string) => ipcRenderer.invoke("read-file", filePath),
  platform: process.platform,
  onUpdateDownloaded: (cb: (info: { version: string }) => void) => {
    ipcRenderer.on("update-downloaded", (_e, info) => cb(info));
  },
  quitAndInstall: () => ipcRenderer.send("quit-and-install"),
});
