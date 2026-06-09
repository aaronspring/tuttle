import { autoUpdater } from "electron-updater";
import type { BrowserWindow } from "electron";

export { autoUpdater };

export function initUpdater(win: BrowserWindow) {
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = false;

  autoUpdater.on("update-downloaded", (info) => {
    win.webContents.send("update-downloaded", {
      version: info.version,
    });
  });

  autoUpdater.on("error", (err) => {
    console.error("[updater]", err);
    win.webContents.send("update-error", {
      message: err?.message ?? String(err),
    });
  });

  autoUpdater.checkForUpdates().catch((err) => {
    console.error("[updater] check failed:", err);
    win.webContents.send("update-error", {
      message: err?.message ?? String(err),
    });
  });
}
