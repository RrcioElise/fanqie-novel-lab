const { app, BrowserWindow, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const APP_PATH = path.join(PROJECT_ROOT, 'src', 'fanqie_novel_lab', 'app.py');
const VENV_PYTHON = process.platform === 'win32'
  ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
  : path.join(PROJECT_ROOT, '.venv', 'bin', 'python');

const HOST = '127.0.0.1';
const PORT = Number(process.env.FANQIE_LAB_PORT || 8501);
const APP_URL = `http://${HOST}:${PORT}`;
let streamlitProc = null;
let mainWindow = null;

function isPortOpen() {
  return new Promise((resolve) => {
    const req = http.get(APP_URL, (res) => {
      res.resume();
      resolve(true);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(700, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForServer(timeoutMs = 30000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await isPortOpen()) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function startStreamlit() {
  if (!fs.existsSync(VENV_PYTHON)) {
    dialog.showErrorBox(
      '未找到 Python 虚拟环境',
      `请先运行：\n\ncd ${PROJECT_ROOT}\nbash scripts/setup.sh\n\n然后重新启动客户端。`
    );
    return false;
  }

  streamlitProc = spawn(
    VENV_PYTHON,
    [
      '-m', 'streamlit', 'run', APP_PATH,
      '--server.address', HOST,
      '--server.port', String(PORT),
      '--server.headless', 'true',
      '--browser.gatherUsageStats', 'false'
    ],
    {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['ignore', 'pipe', 'pipe']
    }
  );

  streamlitProc.stdout.on('data', (data) => console.log(`[streamlit] ${data}`));
  streamlitProc.stderr.on('data', (data) => console.error(`[streamlit] ${data}`));
  streamlitProc.on('exit', (code, signal) => {
    console.log(`Streamlit exited: code=${code}, signal=${signal}`);
    streamlitProc = null;
  });
  return true;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 920,
    minWidth: 1100,
    minHeight: 760,
    title: 'Fanqie Novel Lab',
    backgroundColor: '#0e1117',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.setMenuBarVisibility(false);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    console.error(`Renderer process gone: ${JSON.stringify(details)}`);
  });

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load ${validatedURL}: ${errorCode} ${errorDescription}`);
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  await mainWindow.loadURL(APP_URL);
}

app.whenReady().then(async () => {
  const alreadyRunning = await isPortOpen();
  if (!alreadyRunning) {
    const ok = startStreamlit();
    if (!ok) {
      app.quit();
      return;
    }
    const ready = await waitForServer();
    if (!ready) {
      dialog.showErrorBox('启动失败', `Streamlit 服务未能在 ${APP_URL} 启动，请检查终端日志或 .env 配置。`);
      app.quit();
      return;
    }
  }

  await createWindow();

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (streamlitProc && !streamlitProc.killed) {
    streamlitProc.kill('SIGTERM');
  }
});
