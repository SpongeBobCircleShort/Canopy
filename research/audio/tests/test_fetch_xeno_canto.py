import pytest

from research.audio import fetch_xeno_canto as fx


def test_build_query_and_api_url():
    assert fx.build_query("india", "soundscape") == "cnt:india type:soundscape"
    url = fx.api_url("cnt:india type:soundscape", page=2, key="demo")
    assert url.startswith("https://xeno-canto.org/api/3/recordings?")
    assert "page=2" in url and "cnt%3Aindia" in url and "key=demo" in url


@pytest.mark.parametrize(
    "lic,expected",
    [
        ("//creativecommons.org/licenses/by/4.0/", True),
        ("//creativecommons.org/licenses/by-sa/4.0/", True),
        ("//creativecommons.org/publicdomain/zero/1.0/", True),
        ("//creativecommons.org/licenses/by-nc/4.0/", False),
        ("//creativecommons.org/licenses/by-nc-sa/4.0/", False),
        ("//creativecommons.org/licenses/by-nd/4.0/", False),
        (None, False),
        ("", False),
    ],
)
def test_is_commercial_safe(lic, expected):
    assert fx.is_commercial_safe(lic) is expected


@pytest.mark.parametrize(
    "length,seconds",
    [("2:34", 154.0), ("1:00:00", 3600.0), ("0:05", 5.0), (None, None), ("", None), ("bad", None)],
)
def test_parse_length_seconds(length, seconds):
    assert fx.parse_length_seconds(length) == seconds


def test_clip_url_prefixes_scheme_relative():
    assert fx.clip_url({"file": "//xeno-canto.org/1/download"}) == "https://xeno-canto.org/1/download"
    assert fx.clip_url({"file": "https://xeno-canto.org/2/download"}) == "https://xeno-canto.org/2/download"
    assert fx.clip_url({"file": ""}) is None


def test_recordings_to_rows_filters_license_and_url():
    recordings = [
        {"id": "1", "file": "//xeno-canto.org/1/download", "lic": "//creativecommons.org/licenses/by/4.0/",
         "length": "1:00", "loc": "Nilgiris", "file-name": "a.mp3"},
        {"id": "2", "file": "//xeno-canto.org/2/download", "lic": "//creativecommons.org/licenses/by-nc/4.0/",
         "length": "0:30", "loc": "X"},
        {"id": "3", "file": "", "lic": "//creativecommons.org/licenses/by/4.0/", "length": "0:30", "loc": "Y"},
    ]
    rows = fx.recordings_to_rows(recordings, commercial_safe=True)
    assert len(rows) == 1
    row = rows[0]
    assert row.path == "xc1.mp3"
    assert row.label == "background_unknown"
    assert row.source == "xeno_canto"
    assert row.duration_seconds == 60.0
    assert "xc:1" in row.notes and "Nilgiris" in row.notes

    # Without the commercial-safe guard, the NC clip is kept too.
    assert len(fx.recordings_to_rows(recordings, commercial_safe=False)) == 2
