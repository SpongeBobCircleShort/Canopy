import pytest

from research.audio import fetch_gbif_audio as gb


def test_api_url_defaults_to_ibp():
    url = gb.api_url("IN", "Sound", limit=50, offset=100)
    assert url.startswith("https://api.gbif.org/v1/occurrence/search?")
    assert "country=IN" in url and "mediaType=Sound" in url
    assert "limit=50" in url and "offset=100" in url
    assert gb.IBP_DATASET_KEY in url


def test_api_url_all_datasets_omits_key():
    url = gb.api_url("IN", "Sound", dataset_key=None)
    assert "datasetKey" not in url


@pytest.mark.parametrize(
    "lic,expected",
    [
        ("http://creativecommons.org/licenses/by/4.0/legalcode", True),
        ("CC_BY_4_0", True),
        ("CC0_1_0", True),
        ("CC_BY_SA_4_0", True),
        ("http://creativecommons.org/licenses/by-nc/4.0/legalcode", False),
        ("CC_BY_NC_4_0", False),
        ("CC_BY_NC_SA_4_0", False),
        (None, False),
        ("", False),
    ],
)
def test_is_commercial_safe(lic, expected):
    assert gb.is_commercial_safe(lic) is expected


def _occurrences():
    return [
        {
            "gbifID": "111", "species": "Pycnonotus jocosus", "verbatimLocality": "Nilgiris",
            "license": "CC_BY_NC_4_0",
            "media": [
                {"type": "Sound", "format": "audio/mpeg", "identifier": "https://x/a.mp3",
                 "license": "http://creativecommons.org/licenses/by-nc/4.0/"},
                {"type": "StillImage", "identifier": "https://x/a.jpg"},
            ],
        },
        {
            "gbifID": "222", "species": "Corvus splendens", "locality": "Odisha",
            "license": "CC_BY_4_0",
            "media": [{"type": "Sound", "format": "audio/x-wav", "identifier": "https://x/b.wav"}],
        },
        {"gbifID": "333", "media": [{"type": "Sound"}]},  # no identifier -> skipped
    ]


def test_occurrences_to_rows_parses_sound_media():
    pairs = gb.occurrences_to_rows(_occurrences())
    # a.mp3 (nc) + b.wav = 2 usable; the image and the identifier-less entry are skipped
    assert len(pairs) == 2
    rows = {row.path: (row, url) for row, url in pairs}
    assert "gbif111_0.mp3" in rows and "gbif222_0.wav" in rows
    row_a, url_a = rows["gbif111_0.mp3"]
    assert url_a == "https://x/a.mp3"
    assert row_a.label == "background_unknown" and row_a.source == "gbif"
    assert "gbif:111" in row_a.notes and "Nilgiris" in row_a.notes


def test_occurrences_to_rows_commercial_safe_filters_nc():
    pairs = gb.occurrences_to_rows(_occurrences(), commercial_safe=True)
    # only the CC_BY b.wav survives
    assert [row.path for row, _ in pairs] == ["gbif222_0.wav"]


def test_audio_suffix_from_format_and_url():
    assert gb._audio_suffix({"format": "audio/mpeg"}) == ".mp3"
    assert gb._audio_suffix({"format": "", "identifier": "https://x/y.flac"}) == ".flac"
    assert gb._audio_suffix({"identifier": "https://x/nope"}) == ".mp3"
