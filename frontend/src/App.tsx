import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Box, CircularProgress } from "@mui/material";
import { AuthProvider } from "./components/AuthProvider";
import ProtectedRoute from "./components/ProtectedRoute";
import AppLayout from "./components/AppLayout";
import { ToastProvider } from "./components/ToastProvider";
import LoginPage from "./pages/LoginPage";

const ChatPage = lazy(() => import("./pages/ChatPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ClipsPage = lazy(() => import("./pages/ClipsPage"));
const ClipJobPage = lazy(() => import("./pages/ClipJobPage"));

function PageLoader() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        minHeight: 200,
      }}
    >
      <CircularProgress sx={{ color: "#7c3aed" }} />
    </Box>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<ChatPage />} />
                <Route path="/assets" element={<AssetsPage />} />
                <Route path="/clips" element={<ClipsPage />} />
                <Route path="/clips/:jobId" element={<ClipJobPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
            </Routes>
          </Suspense>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
