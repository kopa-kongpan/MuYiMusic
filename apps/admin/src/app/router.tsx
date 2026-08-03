import { Navigate, createBrowserRouter } from 'react-router-dom'

import { AdminShell } from './AdminShell'
import { LoginPage } from './LoginPage'
import { StoresPage } from './StoresPage'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <AdminShell />,
    children: [
      { index: true, element: <Navigate to="/stores" replace /> },
      { path: 'stores', element: <StoresPage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/stores" replace />,
  },
])
