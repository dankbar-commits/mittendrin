from flyer_extract.pipeline import _dedupe_slugs, _poster_slug, _slug
from flyer_extract.schema import Item


def test_slug_handles_umlauts_as_ae_oe_ue_ss():
    assert _slug("Ältere Menschen in Straße", "x") == "aeltere-menschen-in-strasse"
    assert _slug("Über Grüße", "x") == "ueber-gruesse"


def test_slug_strips_special_chars_and_lowercases():
    assert _slug("65PLUS - TANZ!", "x") == "65plus-tanz"
    assert _slug("  Kaffee & Kuchen  ", "x") == "kaffee-kuchen"


def test_slug_falls_back_when_empty():
    assert _slug("", "fallback-id") == "fallback-id"
    assert _slug("---", "fb") == "fb"


def test_poster_slug_strips_camera_ids():
    cases = {
        "Foto_Netzwerk Älter werden in Potsdam 1_PXL_20260909_174935695": "netzwerk-aelter-werden-in-potsdam",
        "Foto_TPF_Potsdam_PXL_20240913_114911561": "tpf-potsdam",
        "Foto_Netzwerk Gemeinsamkeit im Alter_1000281131": "netzwerk-gemeinsamkeit-im-alter",
        "Foto_Mehrgenerationenhaus am Heiligensee_PXL_20240913_114824546": "mehrgenerationenhaus-am-heiligensee",
    }
    for stem, expected in cases.items():
        assert _poster_slug(stem) == expected, f"{stem} → got {_poster_slug(stem)!r}"


def test_poster_slug_preserves_when_no_camera_id():
    assert _poster_slug("simple-flyer") == "simple-flyer"
    assert _poster_slug("Programm Bürgerhaus") == "programm-buergerhaus"


def test_dedupe_slugs_appends_counter_on_collision():
    items = [
        Item(title="Chor Cantamus", state="suggestion", brief={"de": ""}, description={"de": ""}),
        Item(title="Chor Cantamus", state="suggestion", brief={"de": ""}, description={"de": ""}),
        Item(title="Chor Cantamus", state="suggestion", brief={"de": ""}, description={"de": ""}),
    ]
    record = _dedupe_slugs(items, "poster")
    assert list(record.keys()) == ["chor-cantamus", "chor-cantamus-2", "chor-cantamus-3"]


def test_dedupe_slugs_falls_back_when_title_empty():
    items = [Item(title="   ", state="suggestion", brief={"de": ""}, description={"de": ""})]
    record = _dedupe_slugs(items, "myposter")
    assert list(record.keys()) == ["myposter-item-1"]
