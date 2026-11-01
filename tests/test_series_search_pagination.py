import pytest
from core.database import Database
from core.models import Channel


def test_series_search_deduplication_and_pagination(tmp_path):
    db_file = str(tmp_path / "test_series.db")
    db = Database(db_file)

    # Ajouter une playlist et plusieurs entrées
    pl_id = db.add_playlist(type("PlaylistMock", (), {
        "name": "Test", "url_or_path": "http://test", "playlist_type": "xtream",
        "server_url": "", "username": "", "password": "", "epg_url": "",
        "created_at": "", "updated_at": "", "channel_count": 0, "account_status": "",
        "exp_date": "", "max_connections": "", "active_cons": "",
        "last_sync_live": "", "last_sync_vod": "", "last_sync_series": "", "last_sync_epg": ""
    })())

    # Ajouter une série "Brokenwood" et quelques autres
    channels = [
        Channel(id=None, playlist_id=pl_id, name="|FR| Brokenwood (2014) (VF)", stream_url="xtream_series://3264", stream_type="series", stream_id="3264"),
        Channel(id=None, playlist_id=pl_id, name="|FR| Broken (2017)", stream_url="xtream_series://1001", stream_type="series", stream_id="1001"),
        Channel(id=None, playlist_id=pl_id, name="|FR| Broken Arrow", stream_url="http://movie", stream_type="movie", stream_id="2001"),
    ]
    db.save_channels_batch(pl_id, channels)

    # Test 1 : recherche Brokenwood pour series
    res = db.get_channels(search_query="Brokenwood", stream_type="series", limit=40, offset=0)
    assert len(res) == 1
    assert res[0].name == "|FR| Brokenwood (2014) (VF)"

    # Test 2 : offset > 0 ne doit pas renvoyer le même élément
    res_offset = db.get_channels(search_query="Brokenwood", stream_type="series", limit=39, offset=1)
    assert len(res_offset) == 0

    # Test 3 : get_channel_count pour Brokenwood
    count = db.get_channel_count(search_query="Brokenwood", stream_type="series")
    assert count == 1
