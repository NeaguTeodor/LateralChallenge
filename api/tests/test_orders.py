import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import MenuItem, Order, OrderStatus, Restaurant
from tests.conftest import API


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
