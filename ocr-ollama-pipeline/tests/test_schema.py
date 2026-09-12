import pytest
from pydantic import ValidationError

from flyer_extract.schema import (
    Adapter, AdapterData, Item, LLMItemExtraction, LLMPosterExtraction, SafetyFlag,
)


def test_item_defaults_include_required_fields():
    i = Item(title="Test")
    assert i.state == "suggestion"
    assert i.brief == {}
    assert i.description == {}


def test_item_state_enum_enforced():
    with pytest.raises(ValidationError):
        Item(title="Test", state="not-a-real-state")


def test_adapterdata_roundtrip():
    ad = AdapterData(
        adapter=Adapter(name="flyer-extract", sourceName="foo.jpg"),
        lastUpdate=1234567890,
        version="0.1.0",
        itemsRecord={
            "my-item": Item(
                title="Netzwerk Älter werden",
                brief={"de": "Kurzinfo"},
                description={"de": "Lange Beschreibung"},
                tags=["senioren", "beratung"],
                city="Potsdam",
            ),
        },
    )
    dumped = ad.model_dump_json()
    reloaded = AdapterData.model_validate_json(dumped)
    assert "my-item" in reloaded.itemsRecord
    assert reloaded.itemsRecord["my-item"].tags == ["senioren", "beratung"]


def test_llm_extraction_all_optional():
    # Empty JSON must validate — LLM is allowed to leave every field blank.
    ext = LLMItemExtraction.model_validate_json("{}")
    assert ext.title is None
    assert ext.tags == []


def test_llm_extraction_schema_export_has_no_required():
    schema = LLMItemExtraction.model_json_schema()
    assert "properties" in schema
    # No required fields — the model must not fabricate to satisfy validation
    assert schema.get("required", []) == []


def test_poster_extraction_multi_item():
    poster = LLMPosterExtraction.model_validate_json(
        '{"items":[{"title":"A","tags":["x"]},{"title":"B"}]}'
    )
    assert [i.title for i in poster.items] == ["A", "B"]
    assert poster.items[0].tags == ["x"]


def test_poster_extraction_empty_items_allowed():
    poster = LLMPosterExtraction.model_validate_json('{"items":[]}')
    assert poster.items == []


def test_safety_flag_shape():
    f = SafetyFlag(category="pii", rule_id="pii/email", severity="soft",
                   matched_span="x@y.z", source="ocr")
    assert f.category == "pii"
