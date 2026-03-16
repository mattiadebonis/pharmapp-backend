from supabase import Client, create_client

_client: Client | None = None


def get_supabase_client(url: str, key: str) -> Client:
    """Return a singleton Supabase client using the service_role key."""
    global _client
    if _client is None:
        _client = create_client(url, key)
    return _client


def reset_client() -> None:
    """Reset the singleton client (for testing)."""
    global _client
    _client = None
