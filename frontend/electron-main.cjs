const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');

let backendProcess = null;
let staticServer = null;
const rootDir = path.resolve(__dirname, '..');
const backendPort = process.env.SAHAM_API_PORT || '8774';
const frontendPort = process.env.SAHAM_FRONTEND_PORT || '4179';
const logFile = path.join(app.getPath('userData'), 'saham-api.log');

function safeLog(message) {
  const line = `[${new Date().toISOString()}] ${String(message).trim()}\n`;
  fs.appendFile(logFile, line, () => {});
}

function startBackend() {
  const env = { ...process.env, PYTHONPATH: path.join(rootDir, 'backend') };
  backendProcess = spawn('python', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', backendPort], {
    cwd: path.join(rootDir, 'backend'),
    env,
    windowsHide: true,
  });
  backendProcess.stdout.on('data', (data) => safeLog(`[api] ${data}`));
  backendProcess.stderr.on('data', (data) => safeLog(`[api] ${data}`));
  backendProcess.on('error', (err) => safeLog(`[api:error] ${err.stack || err.message || err}`));
  backendProcess.on('exit', (code, signal) => safeLog(`[api:exit] code=${code} signal=${signal}`));
}

function contentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.html') return 'text/html; charset=utf-8';
  if (ext === '.js') return 'text/javascript; charset=utf-8';
  if (ext === '.css') return 'text/css; charset=utf-8';
  if (ext === '.json') return 'application/json; charset=utf-8';
  if (ext === '.svg') return 'image/svg+xml';
  if (ext === '.png') return 'image/png';
  if (ext === '.ico') return 'image/x-icon';
  return 'application/octet-stream';
}

function startStaticServer() {
  const distDir = path.join(__dirname, 'dist');
  staticServer = http.createServer((req, res) => {
    try {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const normalizedPath = path.normalize(urlPath).replace(/^([/\\])+/, '').replace(/^(\.\.[/\\])+/, '');
      let filePath = path.join(distDir, normalizedPath || 'index.html');
      if (!filePath.startsWith(distDir)) filePath = path.join(distDir, 'index.html');
      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        filePath = path.join(distDir, 'index.html');
      }
      res.writeHead(200, { 'Content-Type': contentType(filePath) });
      fs.createReadStream(filePath).pipe(res);
    } catch (err) {
      safeLog(`[static:error] ${err.stack || err.message || err}`);
      res.writeHead(500);
      res.end('Internal Server Error');
    }
  });
  staticServer.listen(Number(frontendPort), '127.0.0.1', () => {
    safeLog(`[static] listening http://127.0.0.1:${frontendPort}`);
  });
  staticServer.on('error', (err) => safeLog(`[static:error] ${err.stack || err.message || err}`));
}

function createWindow() {
  const win = new BrowserWindow({
    width: 430,
    height: 860,
    minWidth: 390,
    minHeight: 720,
    title: 'Saham ID',
    backgroundColor: '#050814',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5180';
  if (process.env.NODE_ENV === 'development') {
    win.loadURL(devUrl);
  } else {
    win.loadURL(`http://127.0.0.1:${frontendPort}/index.html`);
  }
}

app.whenReady().then(() => {
  startBackend();
  if (process.env.NODE_ENV !== 'development') startStaticServer();
  setTimeout(createWindow, 1500);
});

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill();
  if (staticServer) staticServer.close();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProcess) backendProcess.kill();
  if (staticServer) staticServer.close();
});
