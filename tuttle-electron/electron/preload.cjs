const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tuttle", {
  rpc: (method, params) =>
    ipcRenderer.invoke("rpc", method, params || {}),
  readFile: (filePath) =>
    ipcRenderer.invoke("read-file", filePath),
});
