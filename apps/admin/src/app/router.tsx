import { createBrowserRouter } from 'react-router-dom'

import { FoundationPage } from './FoundationPage'

export const router = createBrowserRouter([
  {
    path: '*',
    element: <FoundationPage />,
  },
])
