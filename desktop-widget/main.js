/**
 * Electron Main Process - Desktop Widget for Chirag Clone
 * Creates a floating always-on-top window for quick chat
 */
const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, nativeImage } = require('electron');
const path = require('path');
const Store = require('electron-store');

// Initialize settings store
const store = new Store({
    defaults: {
        backendUrl: 'http://localhost:8000',
        alwaysOnTop: true,
        windowBounds: { width: 320, height: 450, x: undefined, y: undefined }
    }
});

let mainWindow = null;
let tray = null;

function createWindow() {
    const bounds = store.get('windowBounds');

    mainWindow = new BrowserWindow({
        width: bounds.width,
        height: bounds.height,
        x: bounds.x,
        y: bounds.y,
        frame: false, // Frameless for modern look
        transparent: true,
        alwaysOnTop: store.get('alwaysOnTop'),
        skipTaskbar: true,
        resizable: true,
        minimizable: false,
        maximizable: false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    mainWindow.loadFile('index.html');

    // Save bounds on resize/move
    mainWindow.on('close', () => {
        store.set('windowBounds', mainWindow.getBounds());
    });

    mainWindow.on('resize', () => {
        store.set('windowBounds', mainWindow.getBounds());
    });

    mainWindow.on('move', () => {
        store.set('windowBounds', mainWindow.getBounds());
    });
}

function createTray() {
    // Create a simple tray icon (16x16 template image)
    const iconPath = path.join(__dirname, 'tray-icon.png');
    let trayIcon;

    try {
        trayIcon = nativeImage.createFromPath(iconPath);
        trayIcon = trayIcon.resize({ width: 16, height: 16 });
        trayIcon.setTemplateImage(true);
    } catch {
        // Create a simple colored icon if file doesn't exist
        trayIcon = nativeImage.createEmpty();
    }

    tray = new Tray(trayIcon);
    tray.setToolTip('Chirag Clone Widget');

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Show Widget',
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
            }
        },
        {
            label: 'Hide Widget',
            click: () => {
                if (mainWindow) {
                    mainWindow.hide();
                }
            }
        },
        { type: 'separator' },
        {
            label: 'Always on Top',
            type: 'checkbox',
            checked: store.get('alwaysOnTop'),
            click: (menuItem) => {
                store.set('alwaysOnTop', menuItem.checked);
                if (mainWindow) {
                    mainWindow.setAlwaysOnTop(menuItem.checked);
                }
            }
        },
        { type: 'separator' },
        {
            label: 'Settings',
            click: () => {
                // Send event to renderer to show settings
                if (mainWindow) {
                    mainWindow.webContents.send('show-settings');
                }
            }
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                app.quit();
            }
        }
    ]);

    tray.setContextMenu(contextMenu);

    // Click to toggle visibility
    tray.on('click', () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });
}

function registerShortcuts() {
    // Cmd/Ctrl + Shift + C to toggle widget
    globalShortcut.register('CommandOrControl+Shift+C', () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });
}

// IPC handlers
ipcMain.handle('get-backend-url', () => {
    return store.get('backendUrl');
});

ipcMain.handle('set-backend-url', (_, url) => {
    store.set('backendUrl', url);
    return true;
});

ipcMain.handle('minimize-window', () => {
    if (mainWindow) {
        mainWindow.hide();
    }
});

ipcMain.handle('close-window', () => {
    if (mainWindow) {
        mainWindow.hide();
    }
});

// App lifecycle
app.whenReady().then(() => {
    createWindow();
    createTray();
    registerShortcuts();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // Keep app running in tray
});

app.on('will-quit', () => {
    globalShortcut.unregisterAll();
});

// Hide dock icon on macOS (we're a menubar/tray app)
if (process.platform === 'darwin') {
    app.dock.hide();
}
