import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import { roleLabel, statusLabel, type OrderStatus } from "../api";

export function Layout() {
  const { user, logout, demoAccounts, switchTo } = useAuth();
  const { count, restaurantId } = useCart();
  const navigate = useNavigate();

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <Link to="/" className="brand">
            🥡 Takeaway
          </Link>
          <nav>
            <NavLink to="/" end>
              Restaurants
            </NavLink>
            {user?.role === "customer" && <NavLink to="/orders">My orders</NavLink>}
            {user?.role === "admin" && (
              <>
                <NavLink to="/admin/orders">Manage orders</NavLink>
                <NavLink to="/admin/menus">Manage menus</NavLink>
              </>
            )}
          </nav>
          <div className="topbar-right">
            {count > 0 && restaurantId && (
              <Link to={`/restaurants/${restaurantId}`} className="cart-pill">
                Cart · {count}
              </Link>
            )}
            {user && (
              <span className="small">
                <span className={`badge role-${user.role}`}>{roleLabel(user.role)}</span> {user.full_name}
              </span>
            )}
            {demoAccounts.length > 0 && (
              <select
                className="switcher"
                aria-label="Switch demo account"
                value=""
                onChange={(e) => {
                  const account = demoAccounts.find((a) => a.id === Number(e.target.value))!;
                  switchTo(account.id)
                    .then(() => navigate(account.role === "admin" ? "/admin/orders" : "/"))
                    .catch(() => {}); // e.g. the account was removed; the header stays as it was
                }}
              >
                <option value="" disabled>
                  Switch to…
                </option>
                {demoAccounts.map((a) => (
                  <option key={a.id} value={a.id} disabled={a.id === user?.id} title={a.email}>
                    {a.full_name} ({roleLabel(a.role)})
                  </option>
                ))}
              </select>
            )}
            {user ? (
              <>
                <button
                  className="btn btn-ghost"
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn btn-ghost">
                  Log in
                </Link>
                <Link to="/register" className="btn">
                  Sign up
                </Link>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="container">
        {/* Keyed on the account: switching users remounts the page so it refetches its data. */}
        <Outlet key={user?.id ?? "anonymous"} />
      </main>
    </>
  );
}

export function StatusBadge({ status }: { status: OrderStatus }) {
  return <span className={`badge status-${status}`}>{statusLabel(status)}</span>;
}

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <p className="error">{error}</p> : null;
}
