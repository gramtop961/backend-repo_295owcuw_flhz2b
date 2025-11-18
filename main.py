import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product

app = FastAPI(title="Swag Store API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Swag Store Backend Ready"}


@app.get("/products", response_model=List[Product])
def list_products():
    try:
        items = get_documents("product")
        normalized = []
        for it in items:
            p = Product(
                title=it.get("title", "Untitled"),
                description=it.get("description"),
                price=float(it.get("price", 0)),
                category=it.get("category", "apparel"),
                in_stock=bool(it.get("in_stock", True)),
                sizes=it.get("sizes") or ["XS", "S", "M", "L", "XL"],
                image=it.get("image"),
            )
            normalized.append(p)
        return normalized
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products-full")
def list_products_full():
    """Return full products with their database ids as strings"""
    try:
        items = get_documents("product")
        out = []
        for it in items:
            out.append({
                "_id": str(it.get("_id")),
                "title": it.get("title"),
                "description": it.get("description"),
                "price": float(it.get("price", 0)),
                "category": it.get("category"),
                "in_stock": bool(it.get("in_stock", True)),
                "sizes": it.get("sizes") or ["XS","S","M","L","XL"],
                "image": it.get("image"),
            })
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AddToCartRequest(BaseModel):
    product_id: str
    size: str
    quantity: int = 1


@app.post("/cart", status_code=201)
def add_to_cart(body: AddToCartRequest):
    if not ObjectId.is_valid(body.product_id):
        raise HTTPException(status_code=400, detail="Invalid product id")
    prod = db["product"].find_one({"_id": ObjectId(body.product_id)})
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    if body.size not in (prod.get("sizes") or ["XS", "S", "M", "L", "XL"]):
        raise HTTPException(status_code=400, detail="Invalid size for this product")

    try:
        cid = create_document("cartitem", {
            "product_id": body.product_id,
            "size": body.size,
            "quantity": body.quantity,
        })
        return {"id": cid, "message": "Added to cart"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cart")
def get_cart():
    try:
        items = get_documents("cartitem")
        enriched = []
        for it in items:
            pid = it.get("product_id", "")
            prod = db["product"].find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
            enriched.append({
                "id": str(it.get("_id")),
                "product_id": pid,
                "size": it.get("size"),
                "quantity": it.get("quantity", 1),
                "title": prod.get("title") if prod else None,
                "price": float(prod.get("price", 0)) if prod else 0,
                "image": prod.get("image") if prod else None,
            })
        return {"items": enriched}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/products", status_code=201)
def create_product(product: Product):
    """Create a new product document. Sizes are validated by schema."""
    try:
        doc = product.dict()
        new_id = create_document("product", doc)
        return {"id": new_id, "message": "Product created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/seed")
def seed_products():
    """Seed a couple of Y2K/Chromatic Opium inspired products if none exist"""
    try:
        count = db["product"].count_documents({}) if db else 0
        if count > 0:
            return {"seeded": False, "message": "Products already exist"}

        products = [
            {
                "title": "Nebula Sheen Hoodie",
                "description": "Gloss vinyl sheen with soft-core cotton. Y2K gradients, reflective piping.",
                "price": 89.0,
                "category": "hoodies",
                "in_stock": True,
                "sizes": ["S", "M", "L", "XL"],
                "image": "https://images.unsplash.com/photo-1520975916090-3105956dac38?q=80&w=1600&auto=format&fit=crop"
            },
            {
                "title": "Chrome Ripple Tee",
                "description": "Liquid chrome graphic, oversized cut. Opium club energy.",
                "price": 45.0,
                "category": "tshirts",
                "in_stock": True,
                "sizes": ["XS", "S", "M", "L"],
                "image": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?q=80&w=1600&auto=format&fit=crop"
            },
            {
                "title": "Ultra Violet Cargo",
                "description": "Parachute cargos with iridescent straps and cinch toggles.",
                "price": 110.0,
                "category": "pants",
                "in_stock": True,
                "sizes": ["S", "M", "L"],
                "image": "https://images.unsplash.com/photo-1532890162909-9f2bff5f7c1a?q=80&w=1600&auto=format&fit=crop"
            },
        ]
        for p in products:
            create_document("product", p)
        return {"seeded": True, "count": len(products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
