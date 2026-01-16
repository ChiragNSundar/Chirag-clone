/**
 * Preload Script - Secure bridge between main and renderer
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Backend URL management
    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
    setBackendUrl: (url) => ipcRenderer.invoke('set-backend-url', url),

    // Window controls
    minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
    closeWindow: () => ipcRenderer.invoke('close-window'),

    // Event listeners
    onShowSettings: (callback) => ipcRenderer.on('show-settings', callback),

    // Eye Mode (Vision) APIs
    captureScreen: () => ipcRenderer.invoke('capture-screen'),
    analyzeScreen: (imageBase64, mimeType) => ipcRenderer.invoke('analyze-screen', imageBase64, mimeType),
    setEyeMode: (enabled) => ipcRenderer.invoke('set-eye-mode', enabled),
    getEyeMode: () => ipcRenderer.invoke('get-eye-mode')
});
