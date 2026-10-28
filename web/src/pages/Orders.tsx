import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, money, type Order } from "../api";
import { ErrorNote, StatusBadge } from "../components/Layout";
import { useRestaurantNames } from "./Restaurants";

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const restaurantName = useRestaurantNames();

  useEffect(() => {
    api.orders().then(setOrders, (e) => setError(e.message));
  }, []);

  return (
    <>
      <h1>My orders</h1>
      <ErrorNote error={error} />
      {!orders && !error && <p className="muted">Loading…</p>}
      {orders?.length === 0 && (
        <p className="muted">
          No orders yet. <Link to="/">Browse restaurants</Link>
        </p>
      )}
      <ul className="order-list">
        {orders?.map((o) => (
          <li key={o.id}>
            <Link to={`/orders/${o.id}`} className="card card-link order-row">
              <span>
                <strong>#{o.id}</strong> · {restaurantName(o.restaurant_id)}
              </span>
              <span className="muted small">{new Date(o.created_at).toLocaleString()}</span>
              <span>{money(o.total)}</span>
              <StatusBadge status={o.status} />
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
