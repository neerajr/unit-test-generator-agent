"""Sample FastAPI router for chunker smoke test."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/items", tags=["items"])


class ItemCreate(BaseModel):
    name: str
    description: str = ""


class ItemResponse(BaseModel):
    id: int
    name: str
    description: str
    active: bool


def get_item_service():
    """Dependency providing the item service (override in tests)."""
    raise NotImplementedError


@router.get("/", response_model=list[ItemResponse])
async def list_items(service=Depends(get_item_service)):
    """Return all active items."""
    return service.find_all_active()


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, service=Depends(get_item_service)):
    """Return a single item by ID, 404 if not found."""
    item = service.find_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, service=Depends(get_item_service)):
    """Create a new item."""
    if not payload.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name must not be blank",
        )
    return service.create(payload.name, payload.description)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, service=Depends(get_item_service)):
    """Soft-delete an item."""
    item = service.find_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    service.delete(item_id)


def _sync_helper(value: int) -> int:
    """A plain synchronous utility function (non-route)."""
    if value < 0:
        raise ValueError("value must be non-negative")
    return value * 2
