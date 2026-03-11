import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import PredictionPage from './pages/PredictionPage'
import GhostCarPage from './pages/GhostCarPage'
import BestCarPage from './pages/BestCarPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="prediction" element={<PredictionPage />} />
        <Route path="ghost-car" element={<GhostCarPage />} />
        <Route path="best-car" element={<BestCarPage />} />
      </Route>
    </Routes>
  )
}
