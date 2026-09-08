from taxrag.retrieval import authority_multiplier


def test_authority_multiplier_is_bounded_and_defaults_to_neutral() -> None:
    """Authority may rerank lexical candidates but must not dominate relevance unboundedly."""
    assert authority_multiplier("primary_legislation") == 1.35
    assert authority_multiplier("regulation") == 1.25
    assert authority_multiplier("tax_authority_norm") == 1.20
    assert authority_multiplier("official_guidance") == 1.00
    assert authority_multiplier("unknown") == 1.00
