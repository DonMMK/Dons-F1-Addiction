import { Navigate, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import PredictionPage from "./pages/PredictionPage";
import GhostCarPage from "./pages/GhostCarPage";
import BestCarPage from "./pages/BestCarPage";
import WeekendPage from "./pages/WeekendPage";
import MotorsportPage from "./pages/MotorsportPage";
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="weekend" element={<WeekendPage />} />
        <Route path="prediction" element={<PredictionPage />} />
        <Route path="ghost-car" element={<GhostCarPage />} />
        <Route path="looking-back" element={<BestCarPage />} />
        <Route
          path="best-car"
          element={<Navigate to="/looking-back" replace />}
        />
        <Route path="not-just-f1" element={<MotorsportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
