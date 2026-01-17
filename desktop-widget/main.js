/**
 * Electron Main Process - Desktop Widget for Chirag Clone
 * Creates a floating always-on-top window for quick chat
 * Now with Eye Mode for proactive screen-aware assistance
 */
const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, nativeImage, desktopCapturer } = require('electron');
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

// ============= EYE MODE (Vision) =============

let eyeModeInterval = null;
let eyeModeEnabled = false;

ipcMain.handle('capture-screen', async () => {
    try {
        const sources = await desktopCapturer.getSources({
            types: ['window', 'screen'],
            thumbnailSize: { width: 1280, height: 720 }
        });

        // Find the focused window or use the first screen
        const focused = sources.find(s => s.name !== 'Chirag Clone Widget') || sources[0];

        if (focused && focused.thumbnail) {
            const dataUrl = focused.thumbnail.toDataURL();
            const base64 = dataUrl.split(',')[1];
            return {
                success: true,
                image_base64: base64,
                window_name: focused.name,
                mime_type: 'image/png'
            };
        }
        return { success: false, error: 'No screen source found' };
    } catch (error) {
        console.error('Screen capture error:', error);
        return { success: false, error: error.message };
    }
});

ipcMain.handle('analyze-screen', async (_, imageBase64, mimeType) => {
    try {
        const backendUrl = store.get('backendUrl');
        const response = await fetch(`${backendUrl}/api/vision/desktop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_base64: imageBase64,
                mime_type: mimeType || 'image/png'
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Vision analysis error:', error);
        return { success: false, error: error.message };
    }
});

ipcMain.handle('set-eye-mode', (_, enabled) => {
    eyeModeEnabled = enabled;
    store.set('eyeModeEnabled', enabled);
    return { success: true, enabled };
});

ipcMain.handle('get-eye-mode', () => {
    return { enabled: store.get('eyeModeEnabled', false) };
});

// ============= REWIND MODE (Temporal Memory) =============

let rewindInterval = null;
let rewindEnabled = false;
const REWIND_CAPTURE_INTERVAL = 5000; // 5 seconds

ipcMain.handle('start-rewind', async () => {
    if (rewindInterval) return { success: true, message: 'Already running' };

    rewindEnabled = true;
    store.set('rewindEnabled', true);

    rewindInterval = setInterval(async () => {
        if (!rewindEnabled) return;

        try {
            const sources = await desktopCapturer.getSources({
                types: ['window', 'screen'],
                thumbnailSize: { width: 640, height: 360 }
            });

            // Find focused window (exclude our widget)
            const focused = sources.find(s => s.name !== 'Chirag Clone Widget') || sources[0];

            if (focused && focused.thumbnail) {
                const base64 = focused.thumbnail.toDataURL().split(',')[1];
                const backendUrl = store.get('backendUrl');

                // Send to backend
                const formData = new URLSearchParams();
                formData.append('image_base64', base64);
                formData.append('window_name', focused.name);
                formData.append('mime_type', 'image/png');

                fetch(`${backendUrl}/api/rewind/frame`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                }).catch(err => console.error('Rewind upload failed:', err));
            }
        } catch (error) {
            console.error('Rewind capture error:', error);
        }
    }, REWIND_CAPTURE_INTERVAL);

    return { success: true, message: 'Rewind started', interval: REWIND_CAPTURE_INTERVAL };
});

ipcMain.handle('stop-rewind', () => {
    if (rewindInterval) {
        clearInterval(rewindInterval);
        rewindInterval = null;
    }
    rewindEnabled = false;
    store.set('rewindEnabled', false);
    return { success: true, message: 'Rewind stopped' };
});

ipcMain.handle('get-rewind-status', () => {
    return {
        enabled: rewindEnabled,
        interval: REWIND_CAPTURE_INTERVAL
    };
});

ipcMain.handle('query-rewind', async (_, question, timeRangeMinutes = null) => {
    try {
        const backendUrl = store.get('backendUrl');
        const response = await fetch(`${backendUrl}/api/rewind/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question,
                time_range_minutes: timeRangeMinutes
            })
        });
        return await response.json();
    } catch (error) {
        console.error('Rewind query error:', error);
        return { success: false, error: error.message };
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
