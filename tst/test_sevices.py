import pytest
from unittest.mock import patch

from sqlmodel import select
from models import Address, Transaction
from services import sync_transactions_for_address

mock_tx_data = [
    {
        "hash": "abcd1234",
        "balance_change": 10000,  # in satoshis => 0.0001 BTC
        "time": "2023-01-01 10:00:00"
    }
]

@pytest.fixture
def wallet_address(session):
    """Fixture to create and return a single Address in the test DB."""
    address = Address(address="12xQ9k5ousS8MqNsMBqHKtjAtCuKezm2Ju")
    session.add(address)
    session.commit()
    session.refresh(address)
    return address

@patch("services.fetch_transactions_chunk")
def test_sync_transactions(mock_fetch, session, wallet_address):
    """
    Test that sync_transactions_for_address writes new transactions,
    updates balance, and handles near-zero rounding.
    """
    mock_fetch.side_effect = [
        mock_tx_data,
        []
    ]

    address_obj = wallet_address
    sync_transactions_for_address(session, address_obj, batch_size=10)

    session.refresh(address_obj)
    assert address_obj.sync_status == "DONE"

    stmt = select(Transaction).where(Transaction.address_id == address_obj.id)
    txs = session.exec(stmt).all()
    assert len(txs) == 1
    tx = txs[0]

    assert tx.amount == 0.0001
    assert str(tx.timestamp) == "2023-01-01 10:00:00"

    assert address_obj.balance == 0.0001


@patch("services.fetch_transactions_chunk")
def test_sync_negative_near_zero(mock_fetch, session, wallet_address):
    """
    Test that a near-zero negative sum is forced to 0.0 after rounding.
    """
    mock_fetch.side_effect = [
        [
            {"hash": "aaa", "balance_change": 100},  # 0.000001 BTC
            {"hash": "bbb", "balance_change": -100},  # -0.000001 BTC
        ],
        []
    ]

    address_obj = wallet_address
    sync_transactions_for_address(session, address_obj, batch_size=10)
    session.refresh(address_obj)

    assert address_obj.balance == 0.0
    assert address_obj.sync_status == "DONE"

    stmt = select(Transaction).where(Transaction.address_id == address_obj.id)
    txs = session.exec(stmt).all()
    assert len(txs) == 2

def test_sync_wallet_new_and_duplicate_transactions(session, wallet_address):
    first_sync_data = [
        {
            "hash": "tx1",
            "balance_change": 10000,  # 0.0001 BTC
            "time": "2023-01-01 10:00:00"
        },
        {
            "hash": "tx2",
            "balance_change": -5000,  # -0.00005 BTC
            "time": "2023-01-01 10:05:00"
        }
    ]

    with patch("services.fetch_transactions_chunk") as mock_fetch:
        # On the first call return first_sync_data, then an empty list to signal completion.
        mock_fetch.side_effect = [first_sync_data, []]

        sync_transactions_for_address(session, wallet_address, batch_size=100)

    session.refresh(wallet_address)

    # After first sync, last_synced_offset should be 2 (two transactions processed).
    assert wallet_address.last_synced_offset == 2

    # Check that 2 transactions were inserted.
    stmt = select(Transaction).where(Transaction.address_id == wallet_address.id)
    txs = session.exec(stmt).all()
    assert len(txs) == 2

    # Expected balance: (10000 - 5000) sats = 5000 sats, which is 0.00005 BTC
    expected_balance = round((10000 - 5000) / 1e8, 8)
    assert wallet_address.balance == expected_balance

    second_sync_data = [
        {
            "hash": "tx3",
            "balance_change": 20000,  # 0.0002 BTC
            "time": "2023-01-02 11:00:00"
        }
    ]

    with patch("services.fetch_transactions_chunk") as mock_fetch2:
        mock_fetch2.side_effect = [second_sync_data, []]
        sync_transactions_for_address(session, wallet_address, batch_size=100)

    session.refresh(wallet_address)

    assert wallet_address.last_synced_offset == 3

    txs = session.exec(stmt).all()
    assert len(txs) == 3

    tx_hashes = {tx.tx_hash for tx in txs}
    assert "tx3" in tx_hashes

    expected_balance = round((10000 - 5000 + 20000) / 1e8, 8)
    assert wallet_address.balance == expected_balance
