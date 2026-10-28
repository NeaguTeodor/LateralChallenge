import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import type { OrderStatus } from "../api";
import { statusLabel } from "../api";

export function Layout() {
  const { user, logout } = useAuth();
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
            {user ? (
              <>
                <span className="muted small">
                  {user.full_name}
                  {user.role === "admin" && <span className="badge badge-admin">admin</span>}
                </span>
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
