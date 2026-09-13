import time
import json
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

app = FastAPI(title="API Caching Layer Demo")

{
  "source": "database",
  "data": {
    "id": 1,
    "item": "Laptop",
    "price": 1200,
    "stock": 10
  },
  "response_time_ms": 1501.23
}

# Self-contained in-memory cache (No Redis server required)
class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        item = self.store.get(key)
        if item:
            val, expiry = item
            if time.time() < expiry:
                return val
            else:
                del self.store[key]
        return None

    def setex(self, key, ttl, val):
        self.store[key] = (val, time.time() + ttl)

    def delete(self, key):
        self.store.pop(key, None)

cache = InMemoryCache()

# Simulated Database
fake_db = {
    "1": {"id": 1, "item": "Laptop", "price": 1200, "stock": 10},
    "2": {"id": 2, "item": "Phone", "price": 800, "stock": 25},
}

CACHE_TTL = 60  # Time to live in seconds


class ItemUpdate(BaseModel):
    item: str
    price: float
    stock: int


@app.get("/")
async def root():
    return {
        "status": "Online",
        "message": "Welcome to the Caching API!",
        "endpoints": {
            "Get Item": "/items/1",
            "Interactive Docs": "/docs"
        }
    }


@app.get("/items/{item_id}")
async def get_item(item_id: str, response: Response):
    start_time = time.time()
    cache_key = f"item:{item_id}"

    # 1. Check if data exists in cache (Cache Hit vs. Miss)
    cached_data = cache.get(cache_key)
    if cached_data:
        duration = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Cache-Status"] = "HIT"
        response.headers["X-Response-Time-Ms"] = str(duration)
        return {
            "source": "cache",
            "data": json.loads(cached_data),
            "response_time_ms": duration
        }

    # 2. Simulate slow DB/external API call (Cache Miss)
    time.sleep(1.5)  
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")

    item_data = fake_db[item_id]

    # 3. Store the result in cache with an expiration time (TTL)
    cache.setex(cache_key, CACHE_TTL, json.dumps(item_data))

    duration = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Cache-Status"] = "MISS"
    response.headers["X-Response-Time-Ms"] = str(duration)
    return {
        "source": "database",
        "data": item_data,
        "response_time_ms": duration
    }


@app.put("/items/{item_id}")
async def update_item(item_id: str, update_data: ItemUpdate):
    """
    Cache Invalidation Strategy:
    When underlying data changes, update the DB and delete the stale cache entry.
    """
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")

    # Update simulated DB
    fake_db[item_id] = {
        "id": int(item_id),
        "item": update_data.item,
        "price": update_data.price,
        "stock": update_data.stock
    }

    # Invalidate/delete the cache key
    cache.delete(f"item:{item_id}")

    return {"message": f"Item {item_id} updated and cache invalidated."}