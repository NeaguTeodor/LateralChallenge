import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, setUnauthorizedHandler, tokenStore, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  demoAccounts: User[];
  login: (email: string, password: string) => Promise<void>;
  switchTo: (userId: number) => Promise<void>;
  logout: () => void;
}

// Remembers an explicit logout, so the demo doesn't log you straight back in.
const LOGGED_OUT_KEY = "takeaway.loggedOut";

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [demoAccounts, setDemoAccounts] = useState<User[]>([]);

  const clearSession = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  // Refreshed on every sign-in, so newly registered accounts show up in the switcher.
  const loadDemoAccounts = useCallback(async () => {
    const accounts = await api.demoAccounts().catch(() => []);
    setDemoAccounts(accounts);
    return accounts;
  }, []);

  const startSession = useCallback(
    async (token: string) => {
      tokenStore.set(token);
      localStorage.removeItem(LOGGED_OUT_KEY);
      setUser(await api.me());
      loadDemoAccounts();
    },
    [loadDemoAccounts],
  );

  const login = useCallback(
    async (email: string, password: string) => startSession((await api.login(email, password)).access_token),
    [startSession],
  );
  const switchTo = useCallback(
    async (userId: number) => startSession((await api.demoLogin(userId)).access_token),
    [startSession],
  );
  const logout = useCallback(() => {
    clearSession();
    localStorage.setItem(LOGGED_OUT_KEY, "1");
  }, [clearSession]);

  // Restore the session; in local demo mode, start as the demo customer.
  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    (async () => {
      const accounts = await loadDemoAccounts();
      const me = tokenStore.get() ? await api.me().catch(() => null) : null;
      const firstCustomer = accounts.find((a) => a.role === "customer");
      if (me) setUser(me);
      else if (firstCustomer && !localStorage.getItem(LOGGED_OUT_KEY)) await switchTo(firstCustomer.id);
      else clearSession();
    })().finally(() => setLoading(false));
  }, [clearSession, loadDemoAccounts, switchTo]);

  return (
    <AuthContext.Provider value={{ user, loading, demoAccounts, login, switchTo, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function RequireAuth({ admin, children }: { admin?: boolean; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (admin && user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}
