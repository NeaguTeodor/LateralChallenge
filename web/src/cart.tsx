import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { MAX_QUANTITY, type MenuItem } from "./api";
import { useAuth } from "./auth";

// A cart belongs to a single restaurant (adding from another one starts a new cart) and to the
// user who filled it, so switching accounts doesn't hand one customer's cart to another.
interface Cart {
  restaurantId: number | null;
  ownerId: number | null; // null while browsing anonymously; kept on sign-in
  lines: { item: MenuItem; quantity: number }[];
}

interface CartState extends Cart {
  add: (item: MenuItem) => void;
  setQuantity: (itemId: number, quantity: number) => void;
  syncWithMenu: (restaurantId: number, menu: MenuItem[]) => void;
  clear: () => void;
  count: number;
  total: number;
}

const KEY = "takeaway.cart";
const EMPTY: Cart = { restaurantId: null, ownerId: null, lines: [] };
const CartContext = createContext<CartState | null>(null);

const clamp = (quantity: number) => Math.min(quantity, MAX_QUANTITY);

function load(): Cart {
  try {
    return { ...EMPTY, ...JSON.parse(localStorage.getItem(KEY) ?? "") };
  } catch {
    return EMPTY;
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart>(load);
  const userId = useAuth().user?.id ?? null;

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(cart));
    } catch {
      // Storage unavailable; the cart just won't survive a reload.
    }
  }, [cart]);

  // Claim an anonymous cart on sign-in; drop another user's cart on account switch.
  useEffect(() => {
    if (userId === null) return;
    setCart((c) => (c.ownerId === null ? { ...c, ownerId: userId } : c.ownerId === userId ? c : EMPTY));
  }, [userId]);

  const add = (item: MenuItem) =>
    setCart((c) => {
      const base = c.restaurantId === item.restaurant_id ? c : { ...EMPTY, restaurantId: item.restaurant_id };
      const existing = base.lines.find((l) => l.item.id === item.id);
      const lines = existing
        ? base.lines.map((l) => (l.item.id === item.id ? { ...l, quantity: clamp(l.quantity + 1) } : l))
        : [...base.lines, { item, quantity: 1 }];
      return { ...base, ownerId: userId, lines };
    });

  const setQuantity = (itemId: number, quantity: number) =>
    setCart((c) => {
      const lines =
        quantity <= 0
          ? c.lines.filter((l) => l.item.id !== itemId)
          : c.lines.map((l) => (l.item.id === itemId ? { ...l, quantity: clamp(quantity) } : l));
      return lines.length ? { ...c, lines } : EMPTY;
    });

  // The menu may have changed since items were added: drop deleted/unavailable items and
  // refresh names and prices so the total shown matches what the server will charge.
  const syncWithMenu = useCallback((restaurantId: number, menu: MenuItem[]) => {
    setCart((c) => {
      if (c.restaurantId !== restaurantId) return c;
      const current = new Map(menu.filter((m) => m.is_available).map((m) => [m.id, m]));
      const lines = c.lines.flatMap((l) => {
        const item = current.get(l.item.id);
        return item ? [{ item, quantity: clamp(l.quantity) }] : [];
      });
      return lines.length ? { ...c, lines } : EMPTY;
    });
  }, []);

  const clear = useCallback(() => setCart(EMPTY), []);
  const count = cart.lines.reduce((n, l) => n + l.quantity, 0);
  const total = cart.lines.reduce((n, l) => n + Number(l.item.price) * l.quantity, 0);

  return (
    <CartContext.Provider value={{ ...cart, add, setQuantity, syncWithMenu, clear, count, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
