from flyer_extract.safety import evaluate, scan


def test_clean_text_no_flags():
    flags = scan("Come to our free community picnic on Saturday!")
    assert flags == []
    assert evaluate(flags) is False


def test_profanity_soft_flag():
    flags = scan("this is sh1t")
    assert any(f.category == "profanity" for f in flags)
    assert all(f.severity == "soft" for f in flags if f.category == "profanity")


def test_single_soft_flag_does_not_require_review():
    flags = scan("what the shit")
    assert evaluate(flags) is False


def test_two_soft_flags_require_review():
    flags = scan("shit and damn")
    assert evaluate(flags) is True


def test_pii_email_and_phone():
    flags = scan("Contact us: hello@example.com or +49 30 12345678")
    cats = {f.rule_id for f in flags}
    assert "pii/email" in cats
    assert "pii/phone" in cats


def test_credit_card_luhn_valid_flags_hard():
    # 4532015112830366 is Luhn-valid; 4532015112830367 is not
    flags_ok = scan("Card 4532015112830366")
    flags_bad = scan("Card 4532015112830367")
    assert any(f.rule_id == "pii/credit-card" and f.severity == "hard" for f in flags_ok)
    assert not any(f.rule_id == "pii/credit-card" for f in flags_bad)


def test_word_boundary_no_scunthorpe_problem():
    # "shit" should not fire on "shitake" or "sushi"; using a real classic case:
    flags = scan("The mushroom is called shiitake")
    assert not any(f.rule_id.startswith("lex/profanity") for f in flags)


def test_source_label_preserved():
    flags = scan("shit", source="llm")
    assert flags and all(f.source == "llm" for f in flags)


def test_empty_string():
    assert scan("") == []


def test_scam_urgency_heuristic():
    flags = scan("ACT NOW! Guaranteed returns! Send BTC to this wallet")
    assert any(f.rule_id == "scam/urgency" for f in flags)
