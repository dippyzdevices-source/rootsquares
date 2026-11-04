"""Tests for gallery models (2 tests), e.g. album defaults to unpublished; album media is ordered by created at and cascade deleted."""
from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_album_defaults_to_unpublished():
    from app.gallery.models import Album

    app = _new_app()
    with app.app_context():
        album = Album(title="Durga Puja 2026")
        db.session.add(album)
        db.session.commit()

        saved = Album.query.one()
        assert saved.published is False
        assert saved.event_id is None
        db.drop_all()


def test_album_media_is_ordered_by_created_at_and_cascade_deleted():
    from app.gallery.models import Album, Media

    app = _new_app()
    with app.app_context():
        album = Album(title="Durga Puja 2026")
        db.session.add(album)
        db.session.commit()

        db.session.add(
            Media(
                album_id=album.id,
                filename="second.jpg",
                storage_key="gallery/1/second.jpg",
                thumbnail_storage_key="gallery/1/thumbnails/second.jpg",
                mime_type="image/jpeg",
                width=800,
                height=600,
            )
        )
        db.session.commit()
        db.session.add(
            Media(
                album_id=album.id,
                filename="first.jpg",
                storage_key="gallery/1/first.jpg",
                thumbnail_storage_key="gallery/1/thumbnails/first.jpg",
                mime_type="image/jpeg",
                width=800,
                height=600,
            )
        )
        db.session.commit()

        db.session.refresh(album)
        assert [m.filename for m in album.media] == ["second.jpg", "first.jpg"]

        db.session.delete(album)
        db.session.commit()

        assert Media.query.count() == 0
        db.drop_all()
