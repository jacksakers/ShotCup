// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import SiteLogin from './pages/SiteLogin';
import PickUser from './pages/PickUser';
import Leaderboard from './pages/Leaderboard';
import Teams from './pages/Teams';
import Profile from './pages/Profile';
import Admin from './pages/Admin';

function RequireSiteAuth({ children }) {
  const { siteAuthed } = useAuth();
  return siteAuthed ? children : <Navigate to="/" replace />;
}

function RequireAdminAuth({ children }) {
  const { adminAuthed } = useAuth();
  return adminAuthed ? children : <Navigate to="/leaderboard" replace />;
}

function AppRoutes() {
  const { siteAuthed } = useAuth();
  return (
    <Routes>
      <Route path="/" element={siteAuthed ? <Navigate to="/leaderboard" replace /> : <SiteLogin />} />
      <Route path="/pick-user" element={<RequireSiteAuth><PickUser /></RequireSiteAuth>} />
      <Route element={<RequireSiteAuth><Layout /></RequireSiteAuth>}>
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/teams" element={<Teams />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/admin" element={<RequireAdminAuth><Admin /></RequireAdminAuth>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

