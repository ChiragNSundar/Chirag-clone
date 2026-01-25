import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

import { MoodProvider } from './contexts/MoodContext'
import { BrowserRouter } from 'react-router-dom'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MoodProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </MoodProvider>
  </StrictMode>,
)
