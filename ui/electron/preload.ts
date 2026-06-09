import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("tuttle", {
  rpc: (method: string, params: Record<string, unknown> = {}) =>
    ipcRenderer.invoke("rpc", method, params),
  readFile: (filePath: string) => ipcRenderer.invoke("read-file", filePath),
  platform: process.platform,
  onUpdateDownloaded: (cb: (info: { version: string }) => void) => {
    ipcRenderer.on("update-downloaded", (_e, info) => cb(info));
  },
  onUpdateError: (cb: (info: { message: string }) => void) => {
    ipcRenderer.on("update-error", (_e, info) => cb(info));
  },
  checkForUpdate: () => ipcRenderer.send("check-for-update"),
  openExternal: (url: string) => ipcRenderer.send("open-external", url),
  quitAndInstall: () => ipcRenderer.send("quit-and-install"),
});
