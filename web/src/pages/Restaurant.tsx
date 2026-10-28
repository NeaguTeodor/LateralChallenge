import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, money, type MenuItem, type Restaurant } from "../api";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import { ErrorNote } from "../components/Layout";

export function RestaurantPage() {
  const id = Number(useParams().id);
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [menu, setMenu] = useState<MenuItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cart = useCart();

  useEffect(() => {
    Promise.all([api.restaurant(id), api.menu(id)]).then(
      ([r, m]) => {
        setRestaurant(r);
        setMenu(m);
      },
      (e) => setError(e.message),
    );
  }, [id]);

  if (error) return <ErrorNote error={error} />;
  if (!restaurant || !menu) return <p className="muted">Loading…</p>;

  const otherCart = cart.restaurantId !== null && cart.restaurantId !== id && cart.count > 0;

  return (
    <>
      <p>
        <Link to="/" className="small">
          ← All restaurants
        </Link>
      </p>
      <h1>{restaurant.name}</h1>
      <p className="muted">
        {restaurant.description} · {restaurant.address}
      </p>

      <div className="split">
        <section>
          <h2>Menu</h2>
          {menu.length === 0 && <p className="muted">This restaurant has no menu items yet.</p>}
          <ul className="menu">
            {menu.map((item) => (
              <li key={item.id} className={item.is_available ? "" : "unavailable"}>
                <div>
                  <strong>{item.name}</strong>
                  <p className="muted small">{item.description}</p>
                </div>
                <div className="menu-actions">
                  <span className="price">{money(item.price)}</span>
                  {item.is_available ? (
                    <button className="btn btn-small" onClick={() => cart.add(item)}>
                      Add
                    </button>
                  ) : (
                    <span className="muted small">Unavailable</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {otherCart && (
            <p className="note small">
              You have items from another restaurant in your cart. Adding an item here starts a new cart.
            </p>
          )}
        </section>

        <aside className="card cart">
          <h2>Your order</h2>
          {cart.restaurantId === id && cart.count > 0 ? (
            <Checkout restaurantId={id} />
          ) : (
            <p className="muted small">Add items from the menu.</p>
          )}
        </aside>
      </div>
    </>
  );
}

function Checkout({ restaurantId }: { restaurantId: number }) {
  const cart = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const order = await api.placeOrder({
        restaurant_id: restaurantId,
        delivery_address: address,
        items: cart.lines.map((l) => ({ menu_item_id: l.item.id, quantity: l.quantity })),
      });
      cart.clear();
      navigate(`/orders/${order.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <ul className="cart-lines">
        {cart.lines.map((l) => (
          <li key={l.item.id}>
            <span>{l.item.name}</span>
            <span className="qty">
              <button className="btn btn-ghost btn-small" onClick={() => cart.setQuantity(l.item.id, l.quantity - 1)}>
                −
              </button>
              {l.quantity}
              <button className="btn btn-ghost btn-small" onClick={() => cart.setQuantity(l.item.id, l.quantity + 1)}>
                +
              </button>
            </span>
            <span>{money(Number(l.item.price) * l.quantity)}</span>
          </li>
        ))}
      </ul>
      <p className="total">
        <span>Total</span>
        <strong>{money(cart.total)}</strong>
      </p>
      {user ? (
        <form onSubmit={submit} className="stack">
          <label>
            Delivery address
            <input value={address} onChange={(e) => setAddress(e.target.value)} required maxLength={255} />
          </label>
          <ErrorNote error={error} />
          <button className="btn" disabled={submitting}>
            {submitting ? "Placing order…" : "Place order"}
          </button>
        </form>
      ) : (
        <p className="small">
          <Link to="/login" state={{ from: `/restaurants/${restaurantId}` }}>
            Log in
          </Link>{" "}
          or <Link to="/register">sign up</Link> to place your order.
        </p>
      )}
    </>
  );
}
