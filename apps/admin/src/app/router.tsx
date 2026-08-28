import { Navigate, createBrowserRouter } from 'react-router-dom'

import { AdminShell } from './AdminShell'
import { AdminAccountsPage } from './AdminAccountsPage'
import { AppointmentsPage } from './AppointmentsPage'
import { FranchisePage } from './FranchisePage'
import { LoginPage } from './LoginPage'
import { NotificationDeliveriesPage } from './NotificationDeliveriesPage'
import { ProductsPage } from './ProductsPage'
import { SchedulesPage } from './SchedulesPage'
import { StoreContentPage } from './StoreContentPage'
import { StoresPage } from './StoresPage'
import { UsersPage } from './UsersPage'
import { VideoCoursesPage } from './VideoCoursesPage'

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
      { path: 'franchise', element: <FranchisePage /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'video-courses', element: <VideoCoursesPage /> },
      { path: 'schedules', element: <SchedulesPage /> },
      { path: 'appointments', element: <AppointmentsPage /> },
      { path: 'notifications', element: <NotificationDeliveriesPage /> },
      { path: 'users', element: <UsersPage /> },
      { path: 'admin-accounts', element: <AdminAccountsPage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/stores" replace />,
  },
])
