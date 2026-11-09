import { Navigate, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import { lazy } from "react";
import HomePage from "./pages/HomePage";
const PredictionPage = lazy(() => import("./pages/PredictionPage"));
const GhostCarPage = lazy(() => import("./pages/GhostCarPage"));
const BestCarPage = lazy(() => import("./pages/BestCarPage"));
const WeekendPage = lazy(() => import("./pages/WeekendPage"));
const MotorsportPage = lazy(() => import("./pages/MotorsportPage"));
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
