"""Tests for seatbelt.tooltier — tier resolver precedence."""
from seatbelt.tooltier import resolve_tier


def test_operator_override_beats_everything():
    """(a) Operator override wins even with trusted readonly annotation."""
    assert resolve_tier('send_email', {'send_email': 'medium'}, ['srv'],
                        annotations={'readOnlyHint': True}, server='srv') == 'medium'


def test_trusted_server_readonly_hint():
    """(b) Trusted server readOnlyHint True -> 'low'."""
    assert resolve_tier('do_thing', {}, ['srv'],
                        annotations={'readOnlyHint': True}, server='srv') == 'low'


def test_trusted_server_destructive_hint():
    """(c) Trusted server destructiveHint True -> 'high'."""
    assert resolve_tier('do_thing', {}, ['srv'],
                        annotations={'destructiveHint': True}, server='srv') == 'high'


def test_trusted_server_empty_annotations():
    """(d) Empty annotations {} -> 'high' (omitted destructive defaults destructive)."""
    assert resolve_tier('do_thing', {}, ['srv'],
                        annotations={}, server='srv') == 'high'


def test_untrusted_server_annotations_ignored():
    """(e) Annotations from untrusted server ignored; no heuristic -> 'high'."""
    assert resolve_tier('summarize', {}, ['trusted_one'],
                        annotations={'readOnlyHint': True}, server='evil') == 'high'


def test_heuristic_read_prefix():
    """(f) get_menu -> 'low' via heuristic."""
    assert resolve_tier('get_menu', {}, []) == 'low'


def test_heuristic_write_token():
    """(f) send_email -> 'high' via heuristic."""
    assert resolve_tier('send_email', {}, []) == 'high'


def test_default_sensitive():
    """(f) Unknown 'frobnicate' -> 'high' (default)."""
    assert resolve_tier('frobnicate', {}, []) == 'high'
