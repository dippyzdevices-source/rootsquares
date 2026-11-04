"""The Vipps sweep job starts without reading the server's default database in many-squares mode (W27-R8)."""
from types import SimpleNamespace

from app.jobs import vipps_sweep


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _app(tenancy):
    return SimpleNamespace(config={"TESTING": False}, extensions={"tenancy": tenancy} if tenancy else {}, app_context=lambda: _Ctx())


def test_many_squares_mode_starts_the_loop_without_asking_the_default_database(monkeypatch):
    started = []

    class _T:
        def __init__(self, target, args, daemon):
            started.append(target)

        def start(self):
            pass

    monkeypatch.setattr(vipps_sweep.threading, "Thread", _T)
    monkeypatch.setattr(vipps_sweep.click, "get_current_context", lambda silent=True: None)
    import app.payments.vipps as vipps

    def boom():
        raise AssertionError("the default database must not be asked in many-squares mode")

    monkeypatch.setattr(vipps, "is_enabled", boom)
    vipps_sweep.start_vipps_sweep_job(_app(object()))
    assert started == [vipps_sweep._sweep_loop]


def test_single_database_mode_still_needs_vipps_to_be_set_up(monkeypatch):
    started = []
    monkeypatch.setattr(vipps_sweep.threading, "Thread", lambda **kw: started.append(1))
    monkeypatch.setattr(vipps_sweep.click, "get_current_context", lambda silent=True: None)
    import app.payments.vipps as vipps

    monkeypatch.setattr(vipps, "is_enabled", lambda: False)
    vipps_sweep.start_vipps_sweep_job(_app(None))
    assert started == []
