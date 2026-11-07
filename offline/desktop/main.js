const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");

// Public key used to verify activation codes (matches LICENCE_PUBLIC_KEY on the website server).
const LICENCE_PUBLIC_KEY = "G8Jy7VEVHgl6Vp6oRf645qoqsqcoEf3XqWXiJG8-E_g";
const API_PORT = 8765;
const DB_PORT = 27718;
const procs = [];

const res = (...p) => (app.isPackaged ? path.join(process.resourcesPath, ...p) : path.join(__dirname, "..", "dist-resources", ...p));

function secret(dataDir) {
  const f = path.join(dataDir, "secret.key");
  if (!fs.existsSync(f)) fs.writeFileSync(f, crypto.randomBytes(32).toString("hex"));
  return fs.readFileSync(f, "utf8").trim();
}

function start(cmd, args, env) {
  const p = spawn(cmd, args, { env: { ...process.env, ...env }, windowsHide: true });
  p.on("exit", (code) => console.log(`${path.basename(cmd)} exited ${code}`));
  procs.push(p);
  return p;
}

function waitFor(url, ms = 60000) {
  const until = Date.now() + ms;
  return new Promise((resolve, reject) => {
    const tick = () => http.get(url, (r) => (r.statusCode < 500 ? resolve() : retry())).on("error", retry);
    const retry = () => (Date.now() > until ? reject(new Error("Easy Books server did not start")) : setTimeout(tick, 500));
    tick();
  });
}

async function boot() {
  const dataDir = path.join(app.getPath("userData"), "data");
  const dbDir = path.join(dataDir, "db");
  fs.mkdirSync(dbDir, { recursive: true });

  start(res("mongodb", "mongod.exe"), ["--dbpath", dbDir, "--port", String(DB_PORT), "--bind_ip", "127.0.0.1"], {});
  start(res("server", "easybooks-server.exe"), [], {
    MONGO_URL: `mongodb://127.0.0.1:${DB_PORT}`, DB_NAME: "easybooks", JWT_SECRET: secret(dataDir),
    LICENCE_PUBLIC_KEY, EB_DATA_DIR: dataDir, FRONTEND_DIR: res("frontend"), EB_PORT: String(API_PORT), OFFLINE_MODE: "1",
  });

  const win = new BrowserWindow({ width: 1400, height: 900, title: "Easy Books", autoHideMenuBar: true, show: false });
  win.loadURL(`data:text/html,<body style="font-family:Segoe UI;display:flex;align-items:center;justify-content:center;height:100vh">Starting Easy Books...</body>`);
  win.show();
  try {
    await waitFor(`http://127.0.0.1:${API_PORT}/api/`);
    win.loadURL(`http://127.0.0.1:${API_PORT}/`);
  } catch (e) {
    dialog.showErrorBox("Easy Books", `${e.message}. Please restart your computer and try again.`);
    app.quit();
  }
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http") && !url.startsWith(`http://127.0.0.1:${API_PORT}`)) { shell.openExternal(url); return { action: "deny" }; }
    return { action: "allow" };
  });
}

if (!app.requestSingleInstanceLock()) app.quit();
app.whenReady().then(boot);
app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => procs.forEach((p) => { try { p.kill(); } catch (e) { /* already stopped */ } }));
