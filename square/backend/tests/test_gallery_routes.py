"""Tests for gallery routes (15 tests), e.g. list albums only returns published albums; list albums includes cover thumbnail and photo count; list albums filters by event id."""
from app import create_app
from app.extensions import db
from app.gallery.models import Album, Media


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_album(**overrides):
    defaults = {"title": "Durga Puja 2026", "published": False}
    defaults.update(overrides)
    album = Album(**defaults)
    db.session.add(album)
    db.session.commit()
    return album


def _add_media(album_id, **overrides):
    defaults = {
        "album_id": album_id,
        "filename": "photo.jpg",
        "storage_key": f"gallery/{album_id}/photo.jpg",
        "thumbnail_storage_key": f"gallery/{album_id}/thumbnails/photo.jpg",
        "mime_type": "image/jpeg",
        "width": 800,
        "height": 600,
    }
    defaults.update(overrides)
    media = Media(**defaults)
    db.session.add(media)
    db.session.commit()
    return media


def test_list_albums_only_returns_published_albums():
    app = _new_app()
    with app.app_context():
        _add_album(title="Draft", published=False)
        _add_album(title="Live", published=True)

        response = app.test_client().get("/api/gallery/albums")
        titles = {item["title"] for item in response.get_json()["items"]}

        assert titles == {"Live"}
        db.drop_all()


def test_list_albums_includes_cover_thumbnail_and_photo_count():
    app = _new_app()
    with app.app_context():
        album = _add_album(published=True)
        _add_media(album.id)
        _add_media(album.id, filename="photo2.jpg", storage_key=f"gallery/{album.id}/photo2.jpg")

        response = app.test_client().get("/api/gallery/albums")
        item = response.get_json()["items"][0]

        assert item["photo_count"] == 2
        assert item["cover_thumbnail_url"] == "fake://storage/gallery/1/thumbnails/photo.jpg"
        assert item["cover_width"] == 800
        assert item["cover_height"] == 600
        db.drop_all()


def test_list_albums_filters_by_event_id():
    app = _new_app()
    with app.app_context():
        _add_album(title="Tagged to event 1", published=True, event_id=1)
        _add_album(title="Tagged to event 2", published=True, event_id=2)
        _add_album(title="Not tagged", published=True)

        response = app.test_client().get("/api/gallery/albums?event_id=1")
        titles = {item["title"] for item in response.get_json()["items"]}

        assert titles == {"Tagged to event 1"}
        db.drop_all()


def test_list_albums_rejects_a_non_integer_event_id():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/gallery/albums?event_id=bogus")
        assert response.status_code == 400
        db.drop_all()


def test_list_albums_filters_by_category():
    app = _new_app()
    with app.app_context():
        _add_album(title="Durga Puja", published=True, category="festivals")
        _add_album(title="Volunteer day", published=True, category="community")
        _add_album(title="Uncategorized", published=True)

        response = app.test_client().get("/api/gallery/albums?category=festivals")
        titles = {item["title"] for item in response.get_json()["items"]}

        assert titles == {"Durga Puja"}
        db.drop_all()


def test_list_albums_rejects_an_unknown_category():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/gallery/albums?category=not-a-category")
        assert response.status_code == 400
        db.drop_all()


def test_album_summary_includes_category():
    app = _new_app()
    with app.app_context():
        _add_album(title="Durga Puja", published=True, category="festivals")

        response = app.test_client().get("/api/gallery/albums")

        assert response.get_json()["items"][0]["category"] == "festivals"
        db.drop_all()


def test_get_album_returns_404_for_an_unpublished_album():
    app = _new_app()
    with app.app_context():
        album = _add_album(published=False)

        response = app.test_client().get(f"/api/gallery/albums/{album.id}")

        assert response.status_code == 404
        db.drop_all()


def test_get_album_returns_404_for_an_unknown_id():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/gallery/albums/999")
        assert response.status_code == 404
        db.drop_all()


def test_get_album_returns_media_ordered_by_created_at():
    app = _new_app()
    with app.app_context():
        album = _add_album(published=True)
        _add_media(album.id, filename="first.jpg", storage_key=f"gallery/{album.id}/first.jpg")
        _add_media(album.id, filename="second.jpg", storage_key=f"gallery/{album.id}/second.jpg")

        response = app.test_client().get(f"/api/gallery/albums/{album.id}")
        data = response.get_json()

        assert [m["filename"] for m in data["media"]] == ["first.jpg", "second.jpg"]
        assert data["media"][0]["width"] == 800
        db.drop_all()


def test_list_media_pools_photos_across_every_published_album():
    app = _new_app()
    with app.app_context():
        album1 = _add_album(title="Durga Puja", published=True)
        album2 = _add_album(title="Saraswati Puja", published=True)
        draft = _add_album(title="Draft album", published=False)
        _add_media(album1.id, filename="a1.jpg", storage_key=f"gallery/{album1.id}/a1.jpg")
        _add_media(album1.id, filename="a2.jpg", storage_key=f"gallery/{album1.id}/a2.jpg")
        _add_media(album2.id, filename="b1.jpg", storage_key=f"gallery/{album2.id}/b1.jpg")
        _add_media(draft.id, filename="hidden.jpg", storage_key=f"gallery/{draft.id}/hidden.jpg")

        response = app.test_client().get("/api/gallery/media")
        items = response.get_json()["items"]

        filenames = {item["filename"] for item in items}
        assert filenames == {"a1.jpg", "a2.jpg", "b1.jpg"}
        assert all(item["album_title"] in {"Durga Puja", "Saraswati Puja"} for item in items)
        db.drop_all()


def test_list_media_respects_and_caps_limit():
    app = _new_app()
    with app.app_context():
        album = _add_album(published=True)
        for i in range(5):
            _add_media(album.id, filename=f"photo{i}.jpg", storage_key=f"gallery/{album.id}/photo{i}.jpg")

        response = app.test_client().get("/api/gallery/media?limit=2")
        assert len(response.get_json()["items"]) == 2

        response = app.test_client().get("/api/gallery/media?limit=99999")
        assert response.status_code == 200
        db.drop_all()


def test_list_media_rejects_a_non_integer_limit():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/gallery/media?limit=bogus")
        assert response.status_code == 400
        db.drop_all()


def test_coverage_counts_published_photos_per_five_year_era():
    app = _new_app()
    with app.app_context():
        old = _add_album(year=2011, published=True)
        for i in range(3):
            _add_media(old.id, filename=f"a{i}.jpg", storage_key=f"k{i}", thumbnail_storage_key=f"t{i}")
        draft = _add_album(year=2011, published=False)
        _add_media(draft.id, filename="d.jpg", storage_key="kd", thumbnail_storage_key="td")

        items = app.test_client().get("/api/gallery/coverage").get_json()["items"]

        assert items[0]["era"] == "2010–2014"
        assert items[0]["photo_count"] == 3  # the draft album's photo isn't counted
        assert items[0]["state"] == "very_few"
        assert items[1]["photo_count"] == 0 and items[1]["state"] == "none"
        assert items[-1]["start_year"] % 5 == 0
        db.drop_all()


def test_list_media_random_samples_from_all_published_photos():
    app = _new_app()
    with app.app_context():
        album = _add_album(published=True)
        for i in range(5):
            _add_media(album.id, filename=f"photo{i}.jpg", storage_key=f"gallery/{album.id}/photo{i}.jpg")

        response = app.test_client().get("/api/gallery/media?random=1&limit=5")
        assert response.status_code == 200
        assert len(response.get_json()["items"]) == 5
        db.drop_all()
