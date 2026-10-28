import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import { roleLabel, statusLabel, type OrderStatus, type Role } from "../api";

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
            {user && <NavLink to="/orders">My orders</NavLink>}
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
                  const role = e.target.value as Role;
                  switchTo(role).then(() => navigate(role === "admin" ? "/admin/orders" : "/"));
                }}
              >
                <option value="" disabled>
                  Switch to…
                </option>
                {demoAccounts.map((a) => (
                  <option key={a.id} value={a.role} disabled={a.id === user?.id} title={a.email}>
                    {roleLabel(a.role)}
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
        <Outlet />
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
