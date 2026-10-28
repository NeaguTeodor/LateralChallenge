import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.config import settings
from app.models import MenuItem, Order, OrderStatus, Restaurant, UserRole
from tests.conftest import API, _auth_headers, _make_user


@pytest.fixture
def order(client, customer_headers, restaurant):
    burger, fries, _ = restaurant.menu_items
    res = client.post(
        f"{API}/orders",
        json={
            "restaurant_id": restaurant.id,
            "delivery_address": "42 Home Rd",
            "items": [
                {"menu_item_id": burger.id, "quantity": 2},
                {"menu_item_id": fries.id, "quantity": 1},
            ],
        },
        headers=customer_headers,
    )
    assert res.status_code == 201
    return res.json()


def test_place_order_computes_total_and_snapshots_items(order):
    assert order["status"] == "pending"
    assert order["customer_name"] == "customer@test.dev"  # conftest uses the email as name
    assert order["total"] == "22.25"
    assert [(i["name"], i["unit_price"], i["quantity"]) for i in order["items"]] == [
        ("Burger", "9.50", 2),
        ("Fries", "3.25", 1),
    ]


def test_order_requires_auth(client, restaurant):
    res = client.post(f"{API}/orders", json={})
    assert res.status_code == 401


def test_cannot_order_unavailable_item(client, customer_headers, restaurant):
    shake = restaurant.menu_items[2]
    res = client.post(
        f"{API}/orders",
        json={
            "restaurant_id": restaurant.id,
            "delivery_address": "x",
            "items": [{"menu_item_id": shake.id, "quantity": 1}],
        },
        headers=customer_headers,
    )
    assert res.status_code == 409


def test_cannot_order_item_from_another_restaurant(client, db, customer_headers, restaurant):
    other = Restaurant(name="Other", address="2 St", menu_items=[MenuItem(name="Pie", price=1)])
    db.add(other)
    db.commit()
    res = client.post(
        f"{API}/orders",
        json={
            "restaurant_id": restaurant.id,
            "delivery_address": "x",
            "items": [{"menu_item_id": other.menu_items[0].id, "quantity": 1}],
        },
        headers=customer_headers,
    )
    assert res.status_code == 422


def test_customer_sees_only_own_orders(client, order, customer_headers, other_customer_headers):
    assert len(client.get(f"{API}/orders", headers=customer_headers).json()) == 1
    assert client.get(f"{API}/orders", headers=other_customer_headers).json() == []
    res = client.get(f"{API}/orders/{order['id']}", headers=other_customer_headers)
    assert res.status_code == 404


def test_admin_moves_order_through_lifecycle(client, order, admin_headers, customer_headers):
    for next_status in ("accepted", "out_for_delivery", "delivered"):
        res = client.patch(
            f"{API}/orders/{order['id']}/status",
            json={"status": next_status},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == next_status

    # The customer can track the final state.
    res = client.get(f"{API}/orders/{order['id']}", headers=customer_headers)
    assert res.json()["status"] == "delivered"


def test_invalid_status_transition_rejected(client, order, admin_headers):
    res = client.patch(
        f"{API}/orders/{order['id']}/status", json={"status": "delivered"}, headers=admin_headers
    )
    assert res.status_code == 409


def test_customer_cannot_update_status(client, order, customer_headers):
    res = client.patch(
        f"{API}/orders/{order['id']}/status", json={"status": "accepted"}, headers=customer_headers
    )
    assert res.status_code == 403


def test_admin_can_filter_orders_by_status(client, order, admin_headers):
    res = client.get(f"{API}/orders", params={"status": "pending"}, headers=admin_headers)
    assert [o["id"] for o in res.json()] == [order["id"]]
    res = client.get(f"{API}/orders", params={"status": "delivered"}, headers=admin_headers)
    assert res.json() == []


def test_customer_cancels_pending_order(client, order, customer_headers):
    res = client.post(f"{API}/orders/{order['id']}/cancel", headers=customer_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_customer_cannot_cancel_accepted_order(client, order, customer_headers, admin_headers):
    client.patch(
        f"{API}/orders/{order['id']}/status", json={"status": "accepted"}, headers=admin_headers
    )
    res = client.post(f"{API}/orders/{order['id']}/cancel", headers=customer_headers)
    assert res.status_code == 409


def test_status_update_waits_for_concurrent_update(client, db, order, admin_headers):
    """A status change holds a row lock, so a concurrent one waits and then sees the new state."""
    locked = db.get(Order, order["id"], with_for_update=True)  # another admin mid-update
    url = f"{API}/orders/{order['id']}/status"
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(client.patch, url, json={"status": "accepted"}, headers=admin_headers)
        time.sleep(0.5)
        assert not request.done()  # blocked on the lock rather than reading stale state

        locked.status = OrderStatus.ACCEPTED
        db.commit()
        assert request.result().status_code == 409  # pending -> accepted already happened


def test_order_size_is_bounded(client, customer_headers, restaurant):
    burger = restaurant.menu_items[0]
    res = client.post(
        f"{API}/orders",
        json={
            "restaurant_id": restaurant.id,
            "delivery_address": "x",
            "items": [{"menu_item_id": burger.id, "quantity": 1}] * 51,
        },
        headers=customer_headers,
    )
    assert res.status_code == 422


def test_inactive_restaurant_does_not_take_orders(client, db, customer_headers, restaurant):
    restaurant.is_active = False
    db.commit()
    res = client.post(
        f"{API}/orders",
        json={
            "restaurant_id": restaurant.id,
            "delivery_address": "x",
            "items": [{"menu_item_id": restaurant.menu_items[0].id, "quantity": 1}],
        },
        headers=customer_headers,
    )
    assert res.status_code == 404


def test_idempotency_key_returns_the_same_order(client, customer_headers, restaurant):
    body = {
        "restaurant_id": restaurant.id,
        "delivery_address": "x",
        "items": [{"menu_item_id": restaurant.menu_items[0].id, "quantity": 1}],
    }
    headers = {**customer_headers, "Idempotency-Key": "checkout-1"}
    first = client.post(f"{API}/orders", json=body, headers=headers).json()
    retry = client.post(f"{API}/orders", json=body, headers=headers).json()
    assert retry["id"] == first["id"]
    assert len(client.get(f"{API}/orders", headers=customer_headers).json()) == 1


def test_status_history_is_recorded(client, order, admin_headers):
    res = client.patch(
        f"{API}/orders/{order['id']}/status", json={"status": "accepted"}, headers=admin_headers
    )
    assert [e["status"] for e in res.json()["events"]] == ["pending", "accepted"]


def test_status_stream_pushes_changes(client, order, customer_headers):
    def read_stream():
        url = f"{API}/orders/{order['id']}/stream"
        with client.stream("GET", url, headers=customer_headers) as res:
            return [line[6:] for line in res.iter_lines() if line.startswith("data: ")]

    with ThreadPoolExecutor(max_workers=1) as pool:
        events = pool.submit(read_stream)
        time.sleep(0.5)  # let the stream start listening
        client.post(f"{API}/orders/{order['id']}/cancel", headers=customer_headers)
        assert events.result(timeout=10) == ["pending", "cancelled"]


def test_cannot_stream_someone_elses_order(client, order, other_customer_headers):
    res = client.get(f"{API}/orders/{order['id']}/stream", headers=other_customer_headers)
    assert res.status_code == 404


def _place(client, headers, restaurant, **extra):
    body = {
        "restaurant_id": restaurant.id,
        "items": [{"menu_item_id": restaurant.menu_items[0].id, "quantity": 1}],
    }
    return client.post(f"{API}/orders", json=body | extra, headers=headers)


def _set_status(client, headers, order, status):
    url = f"{API}/orders/{order['id']}/status"
    return client.patch(url, json={"status": status}, headers=headers)


def test_address_is_saved_and_reused(client, db, order, customer_headers, admin_headers):
    assert client.get(f"{API}/auth/me", headers=customer_headers).json()["address"] == "42 Home Rd"

    _set_status(client, admin_headers, order, "cancelled")
    restaurant = db.get(Restaurant, order["restaurant_id"])
    res = _place(client, customer_headers, restaurant)  # no address sent: the saved one is used
    assert res.status_code == 201
    assert res.json()["delivery_address"] == "42 Home Rd"


def test_first_order_needs_an_address(client, customer_headers, restaurant):
    assert _place(client, customer_headers, restaurant).status_code == 422


def test_one_active_order_per_restaurant(client, order, customer_headers, admin_headers, db):
    restaurant = db.get(Restaurant, order["restaurant_id"])
    res = _place(client, customer_headers, restaurant)
    assert res.status_code == 409
    assert f"#{order['id']}" in res.json()["detail"]

    # Once the first order is finished, the customer can order there again.
    for status in ("accepted", "out_for_delivery", "delivered"):
        _set_status(client, admin_headers, order, status)
    assert _place(client, customer_headers, restaurant).status_code == 201


def test_order_limit_ignores_cancelled_orders(client, order, customer_headers, db, monkeypatch):
    monkeypatch.setattr(settings, "max_orders_per_customer", 1)
    other = Restaurant(name="Other", address="2 St", menu_items=[MenuItem(name="Pie", price=1)])
    db.add(other)
    db.commit()
    res = _place(client, customer_headers, other)
    assert res.status_code == 409
    assert "limit" in res.json()["detail"]

    client.post(f"{API}/orders/{order['id']}/cancel", headers=customer_headers)
    assert _place(client, customer_headers, other).status_code == 201


@pytest.mark.parametrize(
    "items",
    [
        [{"quantity": 11}],  # over the per-item cap
        [{"quantity": 10}, {"quantity": 10}],  # same item twice to get around the cap
    ],
)
def test_per_item_quantity_is_capped(client, customer_headers, restaurant, items):
    burger_id = restaurant.menu_items[0].id
    lines = [{"menu_item_id": burger_id, **line} for line in items]
    res = _place(client, customer_headers, restaurant, delivery_address="x", items=lines)
    assert res.status_code == 422


def test_deactivating_restaurant_cancels_unsent_orders(client, db, admin_headers, restaurant):
    pending, accepted, on_the_way = (
        _place(client, h, restaurant, delivery_address="x").json()
        for h in (
            _customer(client, db, "a@test.dev"),
            _customer(client, db, "b@test.dev"),
            _customer(client, db, "c@test.dev"),
        )
    )
    _set_status(client, admin_headers, accepted, "accepted")
    for s in ("accepted", "out_for_delivery"):
        _set_status(client, admin_headers, on_the_way, s)

    url = f"{API}/restaurants/{restaurant.id}"
    client.patch(url, json={"is_active": False}, headers=admin_headers)

    def status_of(order):
        return client.get(f"{API}/orders/{order['id']}", headers=admin_headers).json()

    assert status_of(pending)["status"] == "cancelled"
    assert status_of(accepted)["status"] == "cancelled"
    assert status_of(on_the_way)["status"] == "out_for_delivery"  # already left, so delivered
    assert status_of(pending)["events"][-1]["status"] == "cancelled"  # recorded in history
    assert status_of(on_the_way)["restaurant_name"] == "Testaurant"  # still named when inactive


def _customer(client, db, email):
    _make_user(db, email, UserRole.CUSTOMER)
    return _auth_headers(client, email)
