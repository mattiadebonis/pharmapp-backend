import re

from fastapi import HTTPException, status
from supabase import Client

from app.schemas.catalog import (
    CatalogPackageDTO,
    CatalogProductDTO,
    CatalogProductSearchResultDTO,
    CatalogSearchResultDTO,
)

_POSTGREST_RESERVED = re.compile(r"[,()*\\]")
_MAX_QUERY_LEN = 80


def _sanitize_query(query: str) -> str:
    cleaned = _POSTGREST_RESERVED.sub(" ", query).strip()
    return cleaned[:_MAX_QUERY_LEN]


# Forniture AIFA "vendibili al pubblico" (farmacia territoriale).
# Filtro applicato lato backend — non nella view DB — così la logica
# di accessibilità del catalogo resta in Python e può evolvere senza
# migration.
#
#   RR    - ricetta ripetibile
#   RNR   - ricetta non ripetibile
#   RRL   - ricetta limitativa, vendibile al pubblico su prescrizione specialista
#   RNRL  - ricetta non ripetibile limitativa (idem)
#   SOP   - non soggetti a prescrizione, non da banco
#   OTC   - da banco
#   RMR   - ricetta ministeriale (stupefacenti) — comunque vendibile in farmacia
#
# Esclusi: OSP (uso ospedaliero esclusivo), USPL (uso esclusivo specialista),
#          ND (non definito / vuoto).
PUBLIC_FORNITURA_CODES: tuple[str, ...] = (
    "RR",
    "RNR",
    "RRL",
    "RNRL",
    "SOP",
    "OTC",
    "RMR",
)


def _is_public(fornitura_code: str | None) -> bool:
    return fornitura_code in PUBLIC_FORNITURA_CODES


async def search_catalog(
    supabase: Client,
    country: str,
    query: str,
    limit: int = 40,
    include_homeopathic: bool = False,
) -> list[CatalogSearchResultDTO]:
    """Search the catalog by name, generic name, principle, or package label.

    Il filtro `fornitura_code` pubblico viene applicato qui via
    PostgREST `in_`, non nella definizione della view.
    """
    safe_query = _sanitize_query(query)
    if not safe_query:
        return []
    pattern = f"*{safe_query}*"
    builder = (
        supabase.from_("catalog_search_v1")
        .select("*")
        .eq("country", country)
        .in_("fornitura_code", list(PUBLIC_FORNITURA_CODES))
        .or_(
            f"display_name.ilike.{pattern},"
            f"generic_name.ilike.{pattern},"
            f"principle.ilike.{pattern},"
            f"package_label.ilike.{pattern}"
        )
    )
    if not include_homeopathic:
        builder = builder.eq("is_homeopathic", False)
    result = builder.limit(limit).execute()
    # Ordinamento lato Python: `.order()` via PostgREST in combinazione con
    # `.or_()` non è sempre affidabile a seconda della versione supabase-py.
    # Prioritizziamo exact-prefix match su display_name, poi alfabetico.
    q_lower = safe_query.lower()
    rows = sorted(
        result.data,
        key=lambda r: (
            0 if (r.get("display_name") or "").lower().startswith(q_lower) else 1,
            (r.get("display_name") or "").lower(),
        ),
    )
    return [CatalogSearchResultDTO.model_validate(row) for row in rows]


async def search_catalog_products(
    supabase: Client,
    country: str,
    query: str,
    limit: int = 30,
    include_homeopathic: bool = False,
) -> list[CatalogProductSearchResultDTO]:
    """Ricerca catalogo aggregata: 1 riga per `cod_farmaco`.

    Usa la RPC `search_catalog_products_v1` (migration 016) che fa GROUP BY
    server-side con conteggi `variant_count`/`package_count` e campi
    `single_*` per il caso 1-tap finale (1 variante × 1 confezione).
    """
    result = supabase.rpc(
        "search_catalog_products_v1",
        {
            "p_country": country,
            "p_query": query,
            "p_limit": limit,
            "p_include_homeopathic": include_homeopathic,
        },
    ).execute()
    rows = result.data or []
    return [CatalogProductSearchResultDTO.model_validate(row) for row in rows]


async def fetch_product(supabase: Client, country: str, product_id: str) -> CatalogProductDTO:
    """Fetch a catalog product by ID using the RPC function.

    La RPC ritorna tutte le confezioni autorizzate; qui filtriamo in Python
    tenendo solo quelle al pubblico.
    """
    result = supabase.rpc("fetch_catalog_product_v1", {"p_country": country, "p_product_id": product_id}).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Product not found"}},
        )

    payload = dict(result.data)
    packages = payload.get("packages") or []
    payload["packages"] = [pkg for pkg in packages if _is_public(pkg.get("fornitura_code"))]
    return CatalogProductDTO.model_validate(payload)


async def fetch_package(supabase: Client, country: str, package_id: str) -> CatalogPackageDTO:
    """Fetch a catalog package by ID using the RPC function.

    Se la confezione non è al pubblico (uso ospedaliero / specialistico)
    restituiamo 404: il client non deve poterla selezionare come farmaco
    in terapia.
    """
    result = supabase.rpc("fetch_catalog_package_v1", {"p_country": country, "p_package_id": package_id}).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Package not found"}},
        )

    payload = result.data
    if not _is_public(payload.get("fornitura_code")):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Package not available to the public"}},
        )
    return CatalogPackageDTO.model_validate(payload)
