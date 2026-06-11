import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css';
import './theme-clay.css';
import './layout-fix.css';
import './performance.css';
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
