# ═══════════════════════════════════════════════════════════════
# tests / test_seo_insights.py
#
# PURPOSE: Unit tests for the SEO Insights keyword extractor.
# ═══════════════════════════════════════════════════════════════

from src.domains.agents.seo_insights.api import _extract_keywords


# ─── Keyword extraction logic ─────────────────────────────────

def test_extract_keywords_basic():
    """Should tokenize titles into lowercase words 4+ chars."""
    titles = ["Classic Cotton Tee", "Cotton Hoodie"]
    keywords = _extract_keywords(titles)

    assert "classic" in keywords
    assert "cotton" in keywords
    assert "tee" not in keywords  # 3 chars — filtered out
    assert keywords["cotton"] == 2  # appears in both titles


def test_extract_keywords_empty_input():
    """Empty list should return empty dict."""
    assert _extract_keywords([]) == {}


def test_extract_keywords_handles_none():
    """None entries in the list should be skipped gracefully."""
    titles = ["Running Sneakers", None, "Running Shoes"]
    keywords = _extract_keywords(titles)
    assert keywords["running"] == 2
    assert keywords["sneakers"] == 1


def test_extract_keywords_counts_case_insensitive():
    """Same word in different cases should count as one entry."""
    titles = ["COTTON shirt", "cotton pants", "Cotton hat"]
    keywords = _extract_keywords(titles)
    assert keywords["cotton"] == 3


def test_extract_keywords_skips_short_words():
    """Words shorter than min_length should be excluded."""
    titles = ["a b c de fghij"]
    keywords = _extract_keywords(titles, min_length=4)
    # "de" is 2 chars, "fghij" is 5 chars (one word, not split)
    assert "de" not in keywords
    assert "fghij" in keywords
    # Note: the regex matches \b[a-zA-Z]{4,}\b as one token, not split mid-word
