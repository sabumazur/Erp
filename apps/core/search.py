from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q

# Minimum query length to engage full-text search.
# Shorter strings go straight to substring matching.
_FTS_MIN_CHARS = 3


def fts_search(qs, q, fts_fields, trgm_fields=(), config="spanish"):
    """
    Apply PostgreSQL full-text search with trigram / substring fallbacks.

    fts_fields  – field names suitable for SearchVector (natural-language text,
                  e.g. 'name', 'customer__name').  FK traversal is supported.
    trgm_fields – field names for substring / code matching (codes, IDs,
                  references that aren't natural language, e.g. 'encf', 'code').
    config      – PostgreSQL text-search configuration.

    Behaviour
    ---------
    q < 3 chars  → icontains on every field (substring match; GIN trgm index
                   on the column makes this fast).
    q >= 3 chars → SearchVector + SearchQuery on fts_fields, ordered by
                   SearchRank.  TrigramSimilarity (% operator) on fts_fields
                   is OR-ed in so partial-word matches (e.g. "servi" →
                   "servicio") are also returned.  icontains is OR-ed on
                   trgm_fields for reliable code/prefix matching.

    Returns the (possibly re-ordered) queryset.  Callers that need a slice
    should apply it after this function.
    """
    if not q:
        return qs

    fts_fields = list(fts_fields)
    trgm_fields = list(trgm_fields)

    if not fts_fields and not trgm_fields:
        return qs

    # ── Short query: plain substring match on every field ─────────────────────
    if len(q) < _FTS_MIN_CHARS:
        q_filter = Q()
        for field in fts_fields + trgm_fields:
            q_filter |= Q(**{f"{field}__icontains": q})
        return qs.filter(q_filter)

    # ── Long query: FTS primary + trigram + icontains fallbacks ───────────────
    if fts_fields:
        vector = SearchVector(*fts_fields, config=config)
        query_obj = SearchQuery(q, config=config)

        # Include FTS hits and trigram-similar hits on the same text fields
        # (catches partial-word matches that FTS stemming misses).
        # trigram_similar doesn't support JOIN traversal, so FK fields fall back to icontains.
        match_filter = Q(search_rank__gt=0)
        for field in fts_fields:
            lookup = "icontains" if "__" in field else "trigram_similar"
            match_filter |= Q(**{f"{field}__{lookup}": q})
        for field in trgm_fields:
            match_filter |= Q(**{f"{field}__icontains": q})

        return (
            qs.annotate(search_rank=SearchRank(vector, query_obj))
            .filter(match_filter)
            .order_by("-search_rank")
        )

    # Only trgm_fields (no text fields), just icontains
    q_filter = Q()
    for field in trgm_fields:
        q_filter |= Q(**{f"{field}__icontains": q})
    return qs.filter(q_filter)
