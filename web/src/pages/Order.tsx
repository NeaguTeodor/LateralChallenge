import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, FLOW, isFinal, money, statusLabel, streamOrderStatus, type Order } from "../api";
import { ErrorNote, StatusBadge } from "../components/Layout";
import { useRestaurantNames } from "./Restaurants";

const RECONNECT_MS = 3000;

export function OrderPage() {
  const id = Number(useParams().id);
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const restaurantName = useRestaurantNames();

  const refresh = useCallback(() => {
    api.order(id).then(
      (o) => {
        setOrder(o);
        setError(null);
      },
      (e) => setError(e.message),
    );
  }, [id]);

  // Live updates: the server pushes each status change; we then refetch for the timestamps.
  // Reconnects if the stream drops while the order is still in progress.
  const live = !order || !isFinal(order.status);
  useEffect(() => {
    refresh();
    if (!live) return;
    const abort = new AbortController();
    const connect = () =>
      streamOrderStatus(id, refresh, abort.signal)
        .catch(() => {})
        .finally(() => !abort.signal.aborted && setTimeout(connect, RECONNECT_MS));
    connect();
    return () => abort.abort();
  }, [id, refresh, live]);

  async function cancel() {
    try {
      setOrder(await api.cancelOrder(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!order) return error ? <ErrorNote error={error} /> : <p className="muted">Loading…</p>;

  const step = FLOW.indexOf(order.status);

  return (
    <>
      <p>
        <Link to="/orders" className="small">
          ← My orders
        </Link>
      </p>
      <h1>
        Order #{order.id} <StatusBadge status={order.status} />
      </h1>
      <p className="muted">
        {restaurantName(order.restaurant_id)} · placed {new Date(order.created_at).toLocaleString()}
      </p>

      {order.status === "cancelled" ? (
        <p className="note">This order was cancelled.</p>
      ) : (
        <ol className="tracker">
          {FLOW.map((s, i) => {
            const at = order.events.find((e) => e.status === s)?.created_at;
            return (
              <li key={s} className={i < step ? "done" : i === step ? "current" : ""}>
                {statusLabel(s)}
                {at && <small>{new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small>}
              </li>
            );
          })}
        </ol>
      )}
      {live && <p className="muted small">Live: updates appear as soon as the restaurant changes the status.</p>}

      <div className="card">
        <ul className="cart-lines">
          {order.items.map((it, i) => (
            <li key={i}>
              <span>
                {it.quantity} × {it.name}
              </span>
              <span className="muted small">{money(it.unit_price)} each</span>
              <span>{money(Number(it.unit_price) * it.quantity)}</span>
            </li>
          ))}
        </ul>
        <p className="total">
          <span>Total</span>
          <strong>{money(order.total)}</strong>
        </p>
        <p className="small muted">Delivering to: {order.delivery_address}</p>
        <ErrorNote error={error} />
        {order.status === "pending" && (
          <button className="btn btn-danger" onClick={cancel}>
            Cancel order
          </button>
        )}
      </div>
    </>
  );
}
