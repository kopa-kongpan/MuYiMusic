import 'antd/dist/reset.css'
import './styles.scss'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'

const rootElement = document.querySelector('#root')

if (!rootElement) {
  throw new Error('Application root element was not found')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

