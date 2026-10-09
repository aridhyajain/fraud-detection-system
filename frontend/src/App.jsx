import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import UserDashboard from "./pages/UserDashboard.jsx";
import UsersPage from "./pages/UsersPage.jsx";

const parseJwt = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
};

const ProtectedDashboard = () => {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  
  const decoded = parseJwt(token);
  const role = decoded?.role || "user";
  
  if (role === "admin") {
    return <Dashboard />;
  } else {
    return <UserDashboard />;
  }
};

/**
 * Root application component.
 *
 * Routes:
 *   /login      → Login page (2FA auth flow)
 *   /dashboard  → Admin/User dashboard (protected — requires JWT, handles role-based routing)
 *   /           → Redirects to /login
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<ProtectedDashboard />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
