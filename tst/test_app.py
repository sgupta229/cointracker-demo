def test_delete_address(client, session):
    # Create a new address
    payload = {"address": "bc1qToDelete"}
    resp = client.post("/addresses", json=payload)
    assert resp.status_code == 200, resp.text
    address_id = resp.json()["id"]

    # Delete it
    delete_resp = client.delete(f"/addresses/{address_id}")
    assert delete_resp.status_code == 200, delete_resp.text

    # Confirm it's gone
    get_resp = client.get(f"/addresses/{address_id}")
    assert get_resp.status_code == 404, get_resp.text
