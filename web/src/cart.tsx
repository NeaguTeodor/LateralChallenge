import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { MenuItem } from "./api";

// A cart belongs to a single restaurant; adding from another restaurant starts a new cart.
interface Cart {
  restaurantId: number | null;
  lines: { item: MenuItem; quantity: number }[];
}

interface CartState extends Cart {
  add: (item: MenuItem) => void;
  setQuantity: (itemId: number, quantity: number) => void;
  clear: () => void;
  count: number;
  total: number;
}

const KEY = "takeaway.cart";
const EMPTY: Cart = { restaurantId: null, lines: [] };
const CartContext = createContext<CartState | null>(null);

function load(): Cart {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "") as Cart;
  } catch {
    return EMPTY;
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(cart));
    } catch {
      // Storage unavailable; the cart just won't survive a reload.
    }
  }, [cart]);

  const add = (item: MenuItem) =>
    setCart((c) => {
      const base = c.restaurantId === item.restaurant_id ? c : { ...EMPTY, restaurantId: item.restaurant_id };
      const existing = base.lines.find((l) => l.item.id === item.id);
      const lines = existing
        ? base.lines.map((l) => (l.item.id === item.id ? { ...l, quantity: Math.min(l.quantity + 1, 50) } : l))
        : [...base.lines, { item, quantity: 1 }];
      return { ...base, lines };
    });

  const setQuantity = (itemId: number, quantity: number) =>
    setCart((c) => {
      const lines =
        quantity <= 0
          ? c.lines.filter((l) => l.item.id !== itemId)
          : c.lines.map((l) => (l.item.id === itemId ? { ...l, quantity: Math.min(quantity, 50) } : l));
      return lines.length ? { ...c, lines } : EMPTY;
    });

  const count = cart.lines.reduce((n, l) => n + l.quantity, 0);
  const total = cart.lines.reduce((n, l) => n + Number(l.item.price) * l.quantity, 0);

  return (
    <CartContext.Provider value={{ ...cart, add, setQuantity, clear: () => setCart(EMPTY), count, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
