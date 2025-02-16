# Mini CoinTracker
A mini coin-tracking application built with FastAPI and SQLModel for managing BTC addresses, synchronizing transactions (via the Blockchair API), and viewing balances. This project supports:
* Creating and deleting addresses 
* Triggering an incremental sync to fetch on-chain transactions 
* Storing those transactions in a local database 
* Retrieving transactions with pagination 
* Returning up-to-date balances

## Features
1. Address Management
    * Add a BTC address (stores it in an Address table). 
    * Delete an address by ID. 
    * Lookup addresses by string. 
2. Transaction Sync 
    * Fetches transactions for each address from the Blockchair Bitcoin API. 
    * Stores transactions in a Transaction table, tracking tx_hash, amount, and timestamp. 
    * Calculates and updates the address balance. 
3. Transaction Pagination 
    * Retrieves transactions for a given address with limit/offset pagination. 
    * Ordered by newest (descending timestamp). 
4. Sync Status 
    * Each address has a sync_status field: UNSYNCED, IN_PROGRESS, DONE, or ERROR. 
    * last_synced_at and last_synced_offset track the sync progress.

## Tech Stack
* Python 3.9+
* FastAPI (for the HTTP layer)
* SQLModel (ORM + Pydantic data models)
* SQLite (local development database)
* requests (for external API calls)

## Installation & Setup
1. Clone the repository
2. Create & activate a virtual environment. Make sure you create your virtual environment with Python 3.9+. 
```commandline
python3 -m venv .venv
source .venv/bin/activate
```
3. Install dependencies
```commandline
pip install -r requirements.txt
```
4. Run the server
```commandline
uvicorn main:app --reload
```

By default, the API will run at http://127.0.0.1:8000.

## Usage
Once running, you can explore the available endpoints:

Visit http://127.0.0.1:8000/docs to see interactive API docs.

### Example Endpoints
1. Add an address
```commandline
POST /addresses
Body: { "address": "bc1q..." }
```
2. Sync an address (async background task version)
```commandline
POST /addresses/{id}/sync
```
- Returns immediately with a success message.
- The sync process runs in the background.
- Check GET /addresses/{id} to see sync_status.
3. Get address details
```commandline
GET /addresses/{id}
```
Returns the address, current balance, sync_status, transaction_count, etc.
4. Get transactions (paginated)
```commandline
GET /addresses/{id}/transactions?limit=10&offset=0
```
Returns a list of the stored transactions, newest first.
5. Delete an address
```commandline
DELETE /addresses/{id}
```

## Improvement Areas
1. Expand data model to allow for different cryptocurrencies. Right now, the code assumes that BTC is the only currency.
2. True Async for Sync
    * Currently, we use requests or a synchronous approach. Converting to an async HTTP client (e.g., httpx with async/await) in the background tasks would enable higher concurrency if multiple syncs run simultaneously. 
4. Error Handling & Retries 
   * Add robust error handling for external API calls. 
   * Implement a retry mechanism (e.g. exponential backoff) when Blockchair is unreachable or returns errors. 
5. Scalability 
   * For large transaction volumes, consider a more scalable DB (PostgreSQL). 
   * Use asynchronous workers or a message queue (e.g. Celery or RQ) to handle sync tasks at scale.