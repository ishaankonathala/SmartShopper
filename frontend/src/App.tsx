import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './layouts/AppShell'
import { PreferencesPage } from './pages/PreferencesPage'
import { ShoppingHistoryPage } from './pages/ShoppingHistoryPage'
import { ShopWithAIPage } from './pages/ShopWithAIPage'
import { DiscoverPage } from './pages/DiscoverPage'
import { SavedProductsPage } from './pages/SavedProductsPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<ShopWithAIPage />} />
          <Route
            path="discover"
            element={<DiscoverPage />}
          />
          <Route
            path="preferences"
            element={<PreferencesPage />}
          />
          <Route
            path="history"
            element={<ShoppingHistoryPage />}
          />
          <Route
            path="saved"
            element={<SavedProductsPage />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
