import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { ErrorNote } from "../components/Layout";

function useRedirectAfterAuth() {
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  return () => navigate(from ?? "/", { replace: true });
}

export function LoginPage() {
  const { login } = useAuth();
  const done = useRedirectAfterAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      done();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card narrow">
      <h1>Log in</h1>
      <form onSubmit={submit} className="stack">
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <ErrorNote error={error} />
        <button className="btn" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="small muted">
        No account? <Link to="/register">Sign up</Link>
      </p>
    </div>
  );
}

export function RegisterPage() {
  const { login } = useAuth();
  const done = useRedirectAfterAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.register(form);
      await login(form.email, form.password);
      done();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value }),
    required: true,
  });

  return (
    <div className="card narrow">
      <h1>Create an account</h1>
      <form onSubmit={submit} className="stack">
        <label>
          Full name
          <input {...field("full_name")} autoFocus />
        </label>
        <label>
          Email
          <input type="email" {...field("email")} />
        </label>
        <label>
          Password <span className="muted small">(8–72 characters)</span>
          <input type="password" minLength={8} maxLength={72} {...field("password")} />
        </label>
        <ErrorNote error={error} />
        <button className="btn" disabled={busy}>
          {busy ? "Creating account…" : "Sign up"}
        </button>
      </form>
      <p className="small muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  );
}
