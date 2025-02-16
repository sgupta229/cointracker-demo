import requests
from datetime import datetime
from sqlmodel import Session, select, func
from models import Address, Transaction

API_BASE_URL = "https://api.blockchair.com/bitcoin"

def fetch_transactions_chunk(btc_address: str, offset: int, limit: int = 100) -> list:
    """
    Fetch a chunk of transactions using offset-based pagination from Blockchair.
    """
    try:
        url = (
            f"{API_BASE_URL}/dashboards/address/{btc_address}"
            f"?limit={limit}&offset={offset}&transaction_details=true"
        )
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()

        address_data = data.get("data", {}).get(btc_address, {})
        txs = address_data.get("transactions", [])
        return txs

    except requests.RequestException as e:
        print(f"Error fetching data from explorer: {e}")
        return []

def sync_transactions_for_address(session: Session, address_obj: Address, batch_size: int = 100):
    address_obj.sync_status = "IN_PROGRESS"
    session.add(address_obj)
    session.commit()

    try:
        total_new_transactions = 0
        offset = address_obj.last_synced_offset

        while True:
            tx_chunk = fetch_transactions_chunk(address_obj.address, offset=offset, limit=batch_size)
            if not tx_chunk:
                break

            chunk_count = 0
            for tx_data in tx_chunk:
                tx_hash = tx_data.get("hash")
                if not tx_hash:
                    continue

                # Check if this transaction already exists
                stmt = select(Transaction).where(
                    Transaction.address_id == address_obj.id,
                    Transaction.tx_hash == tx_hash
                )
                existing_tx = session.exec(stmt).first()
                if existing_tx:
                    # Already synced this tx
                    continue

                # Insert new transaction
                new_tx = Transaction(
                    tx_hash=tx_hash,
                    amount=_parse_amount(tx_data),   # Net BTC change
                    timestamp=_parse_timestamp(tx_data),
                    address_id=address_obj.id
                )
                session.add(new_tx)
                chunk_count += 1

            # Commit after processing each chunk
            session.commit()

            if len(tx_chunk) < batch_size:
                offset += len(tx_chunk)
                total_new_transactions += chunk_count
                break

            offset += batch_size
            total_new_transactions += chunk_count

        address_obj.last_synced_offset = offset
        address_obj.last_synced_at = datetime.utcnow()

        # Compute new balance
        balance_stmt = select(func.sum(Transaction.amount)).where(Transaction.address_id == address_obj.id)
        new_balance = session.exec(balance_stmt).one()

        if new_balance is None:
            new_balance = 0.0

        new_balance = round(new_balance, 8)

        # Round to 0 if the balance is exceedingly small...
        if abs(new_balance) < 1e-8:
            new_balance = 0.0

        address_obj.balance = new_balance
        address_obj.sync_status = "DONE"
        session.add(address_obj)
        session.commit()

        print(f"Sync complete. Added {total_new_transactions} new transactions for address {address_obj.address}. New balance={new_balance}")

    except Exception as e:
        address_obj.sync_status = "ERROR"
        session.add(address_obj)
        session.commit()
        raise e

def _parse_amount(tx_data: dict) -> float:
    """
    Parse the net transaction amount in BTC from the API data.
    """
    sats = tx_data.get("balance_change", 0)
    return sats / 1e8

def _parse_timestamp(tx_data: dict) -> datetime:
    """
    Parse the transaction timestamp from the API data.
    """
    block_time_str = tx_data.get("time") or tx_data.get("block_time")
    if block_time_str:
        try:
            return datetime.strptime(block_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None
