from typing import Literal

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.dependencies import get_supabase
from app.schemas.catalog import CatalogPackageDTO, CatalogProductDTO, CatalogSearchResultDTO
from app.services.catalog_service import fetch_package, fetch_product, search_catalog

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/search", response_model=list[CatalogSearchResultDTO])
async def catalog_search(
    country: Literal["it", "us"] = Query(...),
    q: str = Query(..., min_length=1),
    limit: int = Query(40, ge=1, le=100),
    include_homeopathic: bool = Query(False),
    supabase: Client = Depends(get_supabase),
):
    return await search_catalog(supabase, country, q, limit, include_homeopathic)


@router.get("/products/{country}/{product_id}", response_model=CatalogProductDTO)
async def catalog_product(
    country: Literal["it", "us"],
    product_id: str,
    supabase: Client = Depends(get_supabase),
):
    return await fetch_product(supabase, country, product_id)


@router.get("/packages/{country}/{package_id}", response_model=CatalogPackageDTO)
async def catalog_package(
    country: Literal["it", "us"],
    package_id: str,
    supabase: Client = Depends(get_supabase),
):
    return await fetch_package(supabase, country, package_id)
