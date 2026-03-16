from fastapi import HTTPException, status
from supabase import Client

from app.schemas.catalog import CatalogPackageDTO, CatalogProductDTO, CatalogSearchResultDTO


async def search_catalog(supabase: Client, country: str, query: str, limit: int = 40) -> list[CatalogSearchResultDTO]:
    """Search the catalog by name, generic name, principle, or package label."""
    pattern = f"*{query}*"
    result = (
        supabase.from_("catalog_search_v1")
        .select("*")
        .eq("country", country)
        .or_(
            f"display_name.ilike.{pattern},"
            f"generic_name.ilike.{pattern},"
            f"principle.ilike.{pattern},"
            f"package_label.ilike.{pattern}"
        )
        .limit(limit)
        .execute()
    )
    return [CatalogSearchResultDTO.model_validate(row) for row in result.data]


async def fetch_product(supabase: Client, country: str, product_id: str) -> CatalogProductDTO:
    """Fetch a catalog product by ID using the RPC function."""
    result = supabase.rpc("fetch_catalog_product_v1", {"country": country, "product_id": product_id}).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Product not found"}},
        )
    return CatalogProductDTO.model_validate(result.data)


async def fetch_package(supabase: Client, country: str, package_id: str) -> CatalogPackageDTO:
    """Fetch a catalog package by ID using the RPC function."""
    result = supabase.rpc("fetch_catalog_package_v1", {"country": country, "package_id": package_id}).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Package not found"}},
        )
    return CatalogPackageDTO.model_validate(result.data)
