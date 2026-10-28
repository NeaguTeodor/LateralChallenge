import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, setUnauthorizedHandler, tokenStore, type Role, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  demoAccounts: User[];
  login: (email: string, password: string) => Promise<void>;
  switchTo: (userId: number) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
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

  const refreshUser = useCallback(async () => setUser(await api.me()), []);

  return (
    <AuthContext.Provider value={{ user, loading, demoAccounts, login, switchTo, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

// `role` limits a page to one kind of account; the other kind is sent to its own home page.
export function RequireAuth({ role, children }: { role?: Role; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "admin" ? "/admin/orders" : "/"} replace />;
  return <>{children}</>;
}
