from tests.conftest import API


def test_browse_restaurants_and_menu(client, restaurant):
    res = client.get(f"{API}/restaurants")
    assert res.status_code == 200
    assert [r["name"] for r in res.json()] == ["Testaurant"]

    res = client.get(f"{API}/restaurants/{restaurant.id}/menu")
    assert res.status_code == 200
    assert [item["name"] for item in res.json()] == ["Burger", "Fries", "Sold Out Shake"]
    assert res.json()[0]["price"] == "9.50"


def test_inactive_restaurants_are_visible_only_to_admins(client, admin_headers, restaurant):
    client.patch(
        f"{API}/restaurants/{restaurant.id}", json={"is_active": False}, headers=admin_headers
    )
    assert client.get(f"{API}/restaurants").json() == []
    assert client.get(f"{API}/restaurants/{restaurant.id}/menu").status_code == 404

    res = client.get(f"{API}/restaurants", headers=admin_headers)
    assert [r["is_active"] for r in res.json()] == [False]


def test_customer_cannot_manage_menus(client, customer_headers, restaurant):
    res = client.post(
        f"{API}/restaurants", json={"name": "X", "address": "Y"}, headers=customer_headers
    )
    assert res.status_code == 403

    res = client.post(
        f"{API}/restaurants/{restaurant.id}/menu",
        json={"name": "Hack", "price": "1.00"},
        headers=customer_headers,
    )
    assert res.status_code == 403


def test_anonymous_cannot_manage_menus(client, restaurant):
    res = client.post(f"{API}/restaurants", json={"name": "X", "address": "Y"})
    assert res.status_code == 401


def test_admin_manages_restaurant_and_menu(client, admin_headers):
    res = client.post(
        f"{API}/restaurants", json={"name": "New Place", "address": "2 Road"}, headers=admin_headers
    )
    assert res.status_code == 201
    restaurant_id = res.json()["id"]

    res = client.post(
        f"{API}/restaurants/{restaurant_id}/menu",
        json={"name": "Soup", "price": "6.00"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    item_id = res.json()["id"]

    res = client.patch(
        f"{API}/restaurants/{restaurant_id}/menu/{item_id}",
        json={"price": "6.50", "is_available": False},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["price"] == "6.50"
    assert res.json()["is_available"] is False

    res = client.delete(f"{API}/restaurants/{restaurant_id}/menu/{item_id}", headers=admin_headers)
    assert res.status_code == 204
    assert client.get(f"{API}/restaurants/{restaurant_id}/menu").json() == []


def test_menu_item_must_belong_to_restaurant(client, admin_headers, restaurant):
    item_id = restaurant.menu_items[0].id
    res = client.patch(
        f"{API}/restaurants/999/menu/{item_id}", json={"price": "1.00"}, headers=admin_headers
    )
    assert res.status_code == 404


def test_invalid_price_rejected(client, admin_headers, restaurant):
    res = client.post(
        f"{API}/restaurants/{restaurant.id}/menu",
        json={"name": "Free", "price": "0"},
        headers=admin_headers,
    )
    assert res.status_code == 422
