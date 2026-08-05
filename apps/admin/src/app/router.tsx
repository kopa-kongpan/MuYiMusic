import { Navigate, createBrowserRouter } from 'react-router-dom'

import { AdminShell } from './AdminShell'
import { AppointmentsPage } from './AppointmentsPage'
import { LoginPage } from './LoginPage'
import { ProductsPage } from './ProductsPage'
import { SchedulesPage } from './SchedulesPage'
import { StoreContentPage } from './StoreContentPage'
import { StoresPage } from './StoresPage'
import { UsersPage } from './UsersPage'

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
      { path: 'store-content', element: <StoreContentPage /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'schedules', element: <SchedulesPage /> },
      { path: 'appointments', element: <AppointmentsPage /> },
      { path: 'users', element: <UsersPage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/stores" replace />,
  },
])
