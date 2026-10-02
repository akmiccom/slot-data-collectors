import json

import pytest

from collectors.pscube.config import get_hall, load_halls


def write_config(tmp_path, rows):
    path = tmp_path / "pscube.json"
    path.write_text(json.dumps({"source": "pscube", "halls": rows}), encoding="utf-8")
    return path


@pytest.fixture
def hall():
    return {"key": "sample", "name": "Sample", "hall_code": "test",
            "base_url": "https://other.example/h/test/"}


def test_registered_halls():
    halls = load_halls()
    assert len(halls) == 6
    assert get_hall("yasuda5").hall_code == "a744203"
    assert get_hall("yasuda_hibarigaoka").name == "やすだひばりヶ丘店"


def test_lookup_and_urls(tmp_path, hall):
    path = write_config(tmp_path, [hall])
    loaded = get_hall("sample", path)
    assert loaded.base_url == hall["base_url"]
    assert loaded.machine_list_url() == hall["base_url"] + "cgi-bin/nc-v03-001.php?cd_ps=2"
    assert loaded.machine_list_url(1).endswith("?cd_ps=1")
    with pytest.raises(ValueError):
        get_hall("unknown", path)
    for value in (True, "2", 3):
        with pytest.raises(ValueError):
            loaded.machine_list_url(value)


def test_duplicate_key(tmp_path, hall):
    with pytest.raises(ValueError, match="Duplicate"):
        load_halls(write_config(tmp_path, [hall, hall]))


@pytest.mark.parametrize("field", ["key", "name", "hall_code", "base_url"])
@pytest.mark.parametrize("value", [None, "", False])
def test_missing_fields(tmp_path, hall, field, value):
    hall[field] = value
    with pytest.raises(ValueError):
        load_halls(write_config(tmp_path, [hall]))
    del hall[field]
    with pytest.raises(ValueError):
        load_halls(write_config(tmp_path, [hall]))


@pytest.mark.parametrize("url", ["invalid", "ftp://other.example/h/test/",
    "https:///h/test/", "https://other.example/h/test", "https://other.example/h/wrong/",
    "https://user:password@other.example/h/test/", "https://other.example/h/test/?key=x",
    "https://other.example/h/test/#fragment", "https://bad host/h/test/",
    "https://other.example:bad/h/test/", "https://other.example/h/test/\n"])
def test_invalid_url(tmp_path, hall, url):
    hall["base_url"] = url
    with pytest.raises(ValueError):
        load_halls(write_config(tmp_path, [hall]))


@pytest.mark.parametrize("payload", [[], {}, {"source": "other", "halls": []},
                                      {"source": "pscube", "halls": {}},
                                      {"source": "pscube", "halls": [None]}])
def test_invalid_structure(tmp_path, payload):
    path = tmp_path / "pscube.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_halls(path)
