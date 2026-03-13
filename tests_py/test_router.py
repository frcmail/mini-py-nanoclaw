from mini_py_nanoclaw.router import escape_xml, format_messages, format_outbound, strip_internal_tags
from mini_py_nanoclaw.types import NewMessage


def make_msg(**kwargs: object) -> NewMessage:
    base = NewMessage(
        id="1",
        chat_jid="group@g.us",
        sender="123@s.whatsapp.net",
        sender_name="Alice",
        content="hello",
        timestamp="2024-01-01T00:00:00.000Z",
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_escape_xml() -> None:
    assert escape_xml('a & b < c > d "e"') == "a &amp; b &lt; c &gt; d &quot;e&quot;"


def test_format_messages_includes_header_and_message() -> None:
    result = format_messages([make_msg()], "UTC")
    assert '<context timezone="UTC" />' in result
    assert 'sender="Alice"' in result
    assert ">hello</message>" in result


def test_strip_internal_tags() -> None:
    assert strip_internal_tags("hello <internal>secret</internal> world") == "hello  world"


def test_format_outbound_all_internal() -> None:
    assert format_outbound("<internal>hidden</internal>") == ""
