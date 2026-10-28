import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Restaurant } from "../api";
import { ErrorNote } from "../components/Layout";

export function RestaurantsPage() {
  const [restaurants, setRestaurants] = useState<Restaurant[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.restaurants().then(setRestaurants, (e) => setError(e.message));
  }, []);

  return (
    <>
      <h1>Restaurants</h1>
      <ErrorNote error={error} />
      {!restaurants && !error && <p className="muted">Loading…</p>}
      {restaurants?.length === 0 && <p className="muted">No restaurants yet.</p>}
      <div className="grid">
        {restaurants?.map((r) => (
          <Link key={r.id} to={`/restaurants/${r.id}`} className="card card-link">
            <h2>
              {r.name} {!r.is_active && <span className="badge">inactive</span>}
            </h2>
            <p>{r.description}</p>
            <p className="muted small">{r.address}</p>
          </Link>
        ))}
      </div>
    </>
  );
}

// Map of restaurant id → name, for labelling orders.
export function useRestaurantNames() {
  const [names, setNames] = useState<Record<number, string>>({});
  useEffect(() => {
    api
      .restaurants()
      .then((rs) => setNames(Object.fromEntries(rs.map((r) => [r.id, r.name]))))
      .catch(() => {});
  }, []);
  return (id: number) => names[id] ?? `Restaurant #${id}`;
}
