import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import { CartProvider } from "./cart";
import { Layout } from "./components/Layout";
import { RestaurantsPage } from "./pages/Restaurants";
import { RestaurantPage } from "./pages/Restaurant";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { OrdersPage } from "./pages/Orders";
import { OrderPage } from "./pages/Order";
import { AdminOrdersPage } from "./pages/AdminOrders";
import { AdminMenusPage } from "./pages/AdminMenus";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<RestaurantsPage />} />
              <Route path="restaurants/:id" element={<RestaurantPage />} />
              <Route path="login" element={<LoginPage />} />
              <Route path="register" element={<RegisterPage />} />
              <Route path="orders" element={<RequireAuth><OrdersPage /></RequireAuth>} />
              <Route path="orders/:id" element={<RequireAuth><OrderPage /></RequireAuth>} />
              <Route path="admin/orders" element={<RequireAuth admin><AdminOrdersPage /></RequireAuth>} />
              <Route path="admin/menus" element={<RequireAuth admin><AdminMenusPage /></RequireAuth>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
