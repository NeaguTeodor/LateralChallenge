import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, money, type MenuItem, type Restaurant } from "../api";
import { ErrorNote } from "../components/Layout";

export function AdminMenusPage() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRestaurants = useCallback(
    (select?: number) =>
      api.restaurants().then((rs) => {
        setRestaurants(rs);
        setSelected((cur) => select ?? cur ?? rs[0]?.id ?? null);
      }, (e) => setError(e.message)),
    [],
  );

  useEffect(() => {
    loadRestaurants();
  }, [loadRestaurants]);

  return (
    <>
      <h1>Manage menus</h1>
      <ErrorNote error={error} />
      <div className="tabs">
        {restaurants.map((r) => (
          <button
            key={r.id}
            className={r.id === selected && !showNew ? "tab active" : "tab"}
            onClick={() => {
              setSelected(r.id);
              setShowNew(false);
            }}
          >
            {r.name}
            {!r.is_active && " (inactive)"}
          </button>
        ))}
        <button className={showNew ? "tab active" : "tab"} onClick={() => setShowNew(true)}>
          + New restaurant
        </button>
      </div>

      {showNew ? (
        <NewRestaurant
          onCreated={(r) => {
            setShowNew(false);
            loadRestaurants(r.id);
          }}
        />
      ) : (
        selected !== null && (
          <>
            <ActiveToggle restaurant={restaurants.find((r) => r.id === selected)} onChange={() => loadRestaurants()} />
            <MenuEditor key={selected} restaurantId={selected} />
          </>
        )
      )}
    </>
  );
}

// Restaurants are deactivated rather than deleted, since past orders reference them.
function ActiveToggle({ restaurant, onChange }: { restaurant?: Restaurant; onChange: () => void }) {
  const [error, setError] = useState<string | null>(null);
  if (!restaurant) return null;

  const toggle = () =>
    api.updateRestaurant(restaurant.id, { is_active: !restaurant.is_active }).then(onChange, (e) => setError(e.message));

  return (
    <p className="toolbar">
      <span className="muted small">
        {restaurant.is_active ? "Visible to customers." : "Hidden from customers; no new orders."}
      </span>
      <button className={restaurant.is_active ? "btn btn-danger btn-small" : "btn btn-small"} onClick={toggle}>
        {restaurant.is_active ? "Deactivate restaurant" : "Reactivate restaurant"}
      </button>
      <ErrorNote error={error} />
    </p>
  );
}

function NewRestaurant({ onCreated }: { onCreated: (r: Restaurant) => void }) {
  const [form, setForm] = useState({ name: "", description: "", address: "" });
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      onCreated(await api.createRestaurant({ ...form, is_active: true }));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} className="card stack narrow">
      <h2>New restaurant</h2>
      <label>
        Name
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </label>
      <label>
        Description
        <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </label>
      <label>
        Address
        <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} required />
      </label>
      <ErrorNote error={error} />
      <button className="btn">Create restaurant</button>
    </form>
  );
}

const EMPTY_ITEM = { name: "", description: "", price: "", is_available: true };

function MenuEditor({ restaurantId }: { restaurantId: number }) {
  const [menu, setMenu] = useState<MenuItem[] | null>(null);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.menu(restaurantId).then(setMenu, (e) => setError(e.message));
  }, [restaurantId]);

  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      setEditing(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!menu) return <p className="muted">Loading…</p>;

  return (
    <div className="card">
      <ErrorNote error={error} />
      <ul className="menu">
        {menu.map((item) =>
          editing === item.id ? (
            <li key={item.id}>
              <ItemForm
                initial={item}
                onCancel={() => setEditing(null)}
                onSave={(data) => run(() => api.updateMenuItem(restaurantId, item.id, data))}
              />
            </li>
          ) : (
            <li key={item.id} className={item.is_available ? "" : "unavailable"}>
              <div>
                <strong>{item.name}</strong> {!item.is_available && <span className="badge">unavailable</span>}
                <p className="muted small">{item.description}</p>
              </div>
              <div className="menu-actions">
                <span className="price">{money(item.price)}</span>
                <button
                  className="btn btn-ghost btn-small"
                  onClick={() =>
                    run(() => api.updateMenuItem(restaurantId, item.id, { is_available: !item.is_available }))
                  }
                >
                  {item.is_available ? "Mark unavailable" : "Mark available"}
                </button>
                <button className="btn btn-ghost btn-small" onClick={() => setEditing(item.id)}>
                  Edit
                </button>
                <button
                  className="btn btn-danger btn-small"
                  onClick={() => run(() => api.deleteMenuItem(restaurantId, item.id))}
                >
                  Delete
                </button>
              </div>
            </li>
          ),
        )}
      </ul>
      {menu.length === 0 && <p className="muted">No menu items yet.</p>}
      {editing === "new" ? (
        <ItemForm
          initial={EMPTY_ITEM}
          onCancel={() => setEditing(null)}
          onSave={(data) => run(() => api.createMenuItem(restaurantId, data))}
        />
      ) : (
        <button className="btn" onClick={() => setEditing("new")}>
          + Add menu item
        </button>
      )}
    </div>
  );
}

type ItemData = typeof EMPTY_ITEM;

function ItemForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: ItemData;
  onSave: (data: ItemData) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<ItemData>({
    name: initial.name,
    description: initial.description,
    price: initial.price,
    is_available: initial.is_available,
  });

  return (
    <form
      className="item-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(form);
      }}
    >
      <input
        placeholder="Name"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        required
        autoFocus
      />
      <input
        placeholder="Description"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />
      <input
        placeholder="Price"
        type="number"
        min="0.01"
        step="0.01"
        value={form.price}
        onChange={(e) => setForm({ ...form, price: e.target.value })}
        required
      />
      <label className="inline">
        <input
          type="checkbox"
          checked={form.is_available}
          onChange={(e) => setForm({ ...form, is_available: e.target.checked })}
        />
        Available
      </label>
      <button className="btn btn-small">Save</button>
      <button type="button" className="btn btn-ghost btn-small" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}
