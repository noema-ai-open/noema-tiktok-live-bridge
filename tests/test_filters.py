import pytest

from app.filters.chain import FilterChain
from app.filters.control_chars import ControlCharacterFilter
from app.filters.cooldown import UserCooldownFilter
from app.filters.max_length import MaxLengthFilter
from app.filters.repetition import RepetitionSpamFilter
from app.filters.url import URLFilter
from app.filters.words import WordListFilter


@pytest.mark.asyncio
async def test_url_filter_blocks_links_but_not_plain_text(event_factory) -> None:
    event_filter = URLFilter()
    blocked = await event_filter.apply(event_factory(message="visit https://example.test/path"))
    allowed = await event_filter.apply(event_factory(message="example without a link"))
    assert (blocked.allowed, blocked.reason) == (False, "url")
    assert allowed.allowed is True


@pytest.mark.asyncio
async def test_control_character_filter_sanitizes_message(event_factory) -> None:
    result = await ControlCharacterFilter().apply(event_factory(message="hi\x00there\nnext"))
    assert result.allowed is True
    assert result.event.message == "hithere\nnext"


@pytest.mark.asyncio
async def test_max_length_filter(event_factory) -> None:
    event_filter = MaxLengthFilter(5)
    assert (await event_filter.apply(event_factory(message="12345"))).allowed is True
    result = await event_filter.apply(event_factory(message="123456"))
    assert (result.allowed, result.reason) == (False, "max_length")


@pytest.mark.asyncio
async def test_repetition_filter_is_per_user_and_time_window(event_factory) -> None:
    now = [10.0]
    event_filter = RepetitionSpamFilter(2, 5.0, clock=lambda: now[0])
    assert (await event_filter.apply(event_factory(message="Hello world"))).allowed
    assert (await event_filter.apply(event_factory(message=" hello  WORLD "))).allowed
    blocked = await event_filter.apply(event_factory(message="HELLO WORLD"))
    assert (blocked.allowed, blocked.reason) == (False, "repetition_spam")
    assert (
        await event_filter.apply(event_factory(message="hello world", user_id="another-user"))
    ).allowed
    now[0] = 20.0
    assert (await event_filter.apply(event_factory(message="hello world"))).allowed


@pytest.mark.asyncio
async def test_blacklist_and_whitelist_words(event_factory) -> None:
    event_filter = WordListFilter(blacklist=["blocked"], whitelist=["approved"])
    blocked = await event_filter.apply(event_factory(message="this is BLOCKED"))
    exempt = await event_filter.apply(event_factory(message="blocked but approved"))
    assert (blocked.allowed, blocked.reason) == (False, "blacklist")
    assert exempt.allowed is True


@pytest.mark.asyncio
async def test_user_cooldown(event_factory) -> None:
    now = [100.0]
    event_filter = UserCooldownFilter(2.0, clock=lambda: now[0])
    assert (await event_filter.apply(event_factory())).allowed
    blocked = await event_filter.apply(event_factory(message="second"))
    assert (blocked.allowed, blocked.reason) == (False, "user_cooldown")
    assert (await event_filter.apply(event_factory(user_id="other"))).allowed
    now[0] += 2.0
    assert (await event_filter.apply(event_factory(message="later"))).allowed


@pytest.mark.asyncio
async def test_filter_chain_passes_sanitized_event_and_stops_on_block(event_factory) -> None:
    chain = FilterChain([ControlCharacterFilter(), MaxLengthFilter(5)])
    allowed = await chain.apply(event_factory(message="ab\x00cd"))
    blocked = await chain.apply(event_factory(message="abcdef"))
    assert allowed.event.message == "abcd"
    assert (blocked.allowed, blocked.reason) == (False, "max_length")


@pytest.mark.asyncio
async def test_filters_ignore_non_chat_events(event_factory) -> None:
    event = event_factory(event_type="gift", message=None)
    chain = FilterChain(
        [
            URLFilter(),
            ControlCharacterFilter(),
            MaxLengthFilter(1),
            RepetitionSpamFilter(1),
            WordListFilter(["bad"]),
            UserCooldownFilter(10),
        ]
    )
    assert (await chain.apply(event)).allowed is True

