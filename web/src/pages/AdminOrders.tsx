import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, CANCELLABLE, money, NEXT_STATUS, statusLabel, type Order, type OrderStatus } from "../api";
import { ErrorNote, StatusBadge } from "../components/Layout";

const FILTERS: (OrderStatus | "")[] = ["", "pending", "accepted", "out_for_delivery", "delivered", "cancelled"];
const POLL_MS = 10000;

export function AdminOrdersPage() {
  const [filter, setFilter] = useState<OrderStatus | "">("pending");
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const refresh = useCallback(() => {
    api.orders(filter || undefined).then(setOrders, (e) => setError(e.message));
  }, [filter]);

  // Poll so new customer orders appear without a reload.
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  async function move(order: Order, status: OrderStatus) {
    setBusyId(order.id);
    setError(null);
    try {
      await api.setOrderStatus(order.id, status);
      refresh();
    } catch (e) {
      setError(`Order #${order.id}: ${(e as Error).message}`);
      refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1>Manage orders</h1>
      <div className="tabs">
        {FILTERS.map((f) => (
          <button key={f || "all"} className={f === filter ? "tab active" : "tab"} onClick={() => setFilter(f)}>
            {f ? statusLabel(f) : "All"}
          </button>
        ))}
      </div>
      <ErrorNote error={error} />
      {!orders && <p className="muted">Loading…</p>}
      {orders?.length === 0 && <p className="muted">No orders here.</p>}
      {orders && orders.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Customer</th>
                <th>Restaurant</th>
                <th>Items</th>
                <th>Address</th>
                <th>Total</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const next = NEXT_STATUS[o.status];
                return (
                  <tr key={o.id}>
                    <td>
                      <Link to={`/orders/${o.id}`}>#{o.id}</Link>
                      <div className="muted small">{new Date(o.created_at).toLocaleTimeString()}</div>
                    </td>
                    <td>{o.customer_name}</td>
                    <td>{o.restaurant_name}</td>
                    <td className="small">{o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}</td>
                    <td className="small">{o.delivery_address}</td>
                    <td>{money(o.total)}</td>
                    <td>
                      <StatusBadge status={o.status} />
                    </td>
                    <td className="row-actions">
                      {next && (
                        <button className="btn btn-small" disabled={busyId === o.id} onClick={() => move(o, next)}>
                          → {statusLabel(next)}
                        </button>
                      )}
                      {CANCELLABLE.includes(o.status) && (
                        <button
                          className="btn btn-small btn-danger"
                          disabled={busyId === o.id}
                          onClick={() => move(o, "cancelled")}
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
