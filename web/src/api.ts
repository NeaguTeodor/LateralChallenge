// Thin typed client for the /api/v1 backend.

export type Role = "customer" | "admin";
export type OrderStatus = "pending" | "accepted" | "out_for_delivery" | "delivered" | "cancelled";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  address: string | null; // last delivery address, pre-fills checkout
}

export interface Restaurant {
  id: number;
  name: string;
  description: string;
  address: string;
  is_active: boolean;
}

export interface MenuItem {
  id: number;
  restaurant_id: number;
  name: string;
  description: string;
  price: string;
  is_available: boolean;
}

export interface OrderItem {
  menu_item_id: number | null;
  name: string;
  unit_price: string;
  quantity: number;
}

export interface Order {
  id: number;
  customer_id: number;
  customer_name: string;
  restaurant_id: number;
  status: OrderStatus;
  delivery_address: string;
  total: string;
  items: OrderItem[];
  events: { status: OrderStatus; created_at: string }[];
  created_at: string;
  updated_at: string;
}

const BASE = "/api/v1";
const TOKEN_KEY = "takeaway.token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Called on 401 so the app can drop a stale session.
let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn;
};

function errorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: [...], msg: "..."}]
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && typeof init.body === "string") headers.set("Content-Type", "application/json");

  const res = await fetch(BASE + path, { ...init, headers });
  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(res.status, errorMessage(body, res.statusText));
  }
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({
  method,
  body: JSON.stringify(data),
});

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  register: (data: { email: string; full_name: string; password: string }) =>
    request<User>("/auth/register", json("POST", data)),
  me: () => request<User>("/auth/me"),
  // Local demo only (404 in production): every account, and passwordless login as any of them.
  demoAccounts: () => request<User[]>("/auth/demo-accounts"),
  demoLogin: (userId: number) => request<{ access_token: string }>(`/auth/demo-login/${userId}`, { method: "POST" }),

  restaurants: () => request<Restaurant[]>("/restaurants"),
  restaurant: (id: number) => request<Restaurant>(`/restaurants/${id}`),
  menu: (id: number) => request<MenuItem[]>(`/restaurants/${id}/menu`),
  createRestaurant: (data: Omit<Restaurant, "id">) =>
    request<Restaurant>("/restaurants", json("POST", data)),
  updateRestaurant: (id: number, data: Partial<Restaurant>) =>
    request<Restaurant>(`/restaurants/${id}`, json("PATCH", data)),
  createMenuItem: (restaurantId: number, data: Omit<MenuItem, "id" | "restaurant_id">) =>
    request<MenuItem>(`/restaurants/${restaurantId}/menu`, json("POST", data)),
  updateMenuItem: (restaurantId: number, itemId: number, data: Partial<MenuItem>) =>
    request<MenuItem>(`/restaurants/${restaurantId}/menu/${itemId}`, json("PATCH", data)),
  deleteMenuItem: (restaurantId: number, itemId: number) =>
    request<void>(`/restaurants/${restaurantId}/menu/${itemId}`, { method: "DELETE" }),

  // The key makes retries (double clicks, flaky networks) return the same order.
  placeOrder: (
    data: { restaurant_id: number; delivery_address?: string; items: { menu_item_id: number; quantity: number }[] },
    idempotencyKey: string,
  ) => request<Order>("/orders", { ...json("POST", data), headers: { "Idempotency-Key": idempotencyKey } }),
  orders: (status?: OrderStatus) =>
    request<Order[]>(`/orders?limit=100${status ? `&status=${status}` : ""}`),
  order: (id: number) => request<Order>(`/orders/${id}`),
  cancelOrder: (id: number) => request<Order>(`/orders/${id}/cancel`, { method: "POST" }),
  setOrderStatus: (id: number, status: OrderStatus) =>
    request<Order>(`/orders/${id}/status`, json("PATCH", { status })),
};

// Server-Sent Events over fetch (EventSource can't send the Authorization header).
// Calls onStatus for every `data:` line until the server closes the stream or signal aborts.
export async function streamOrderStatus(id: number, onStatus: (s: OrderStatus) => void, signal: AbortSignal) {
  const res = await fetch(`${BASE}/orders/${id}/stream`, {
    headers: { Authorization: `Bearer ${tokenStore.get()}` },
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    const events = buffer.split("\n\n");
    buffer = events.pop()!;
    for (const event of events) {
      const data = event.match(/^data: (.*)$/m)?.[1];
      if (data) onStatus(data as OrderStatus);
    }
  }
}

// Mirrors the backend's allowed transitions.
export const NEXT_STATUS: Partial<Record<OrderStatus, OrderStatus>> = {
  pending: "accepted",
  accepted: "out_for_delivery",
  out_for_delivery: "delivered",
};
export const CANCELLABLE: OrderStatus[] = ["pending", "accepted"];
export const isFinal = (s: OrderStatus) => s === "delivered" || s === "cancelled";
export const FLOW: OrderStatus[] = ["pending", "accepted", "out_for_delivery", "delivered"];

export const statusLabel = (s: OrderStatus) =>
  ({
    pending: "Pending",
    accepted: "Accepted",
    out_for_delivery: "Out for delivery",
    delivered: "Delivered",
    cancelled: "Cancelled",
  })[s];

export const roleLabel = (r: Role) => (r === "admin" ? "Admin" : "Customer");

export const money = (v: string | number) => `€${Number(v).toFixed(2)}`;
