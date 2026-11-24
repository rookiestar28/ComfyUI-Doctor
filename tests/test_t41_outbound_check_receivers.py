"""The outbound safety check recognises HTTP clients by where they come from, not by what they are called.

``_is_http_client_call`` used to accept a receiver only when its name ended with ``session`` (or it was an
aiohttp alias) and ``_is_session_post`` only the literal name ``session``. A policy session bound to another
name (``http = await SessionManager.get_session()``) escaped both the redirect rule and the
post-sanitization rule. Receivers are now names or ``self.<attribute>`` bound from an HTTP source: the policy
session factory, an aiohttp ``ClientSession``, or a raw client constructor.
"""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_outbound_safety import check_file  # noqa: E402


def rules_of(tmp_path, code: str) -> set:
    path = tmp_path / "client_under_test.py"
    path.write_text(textwrap.dedent(code), encoding="utf-8")
    return {violation.rule for violation in check_file(path, tmp_path)}


# ------------------------------------------------------------------ receivers with any name are caught
RENAMED_RECEIVERS = {
    "policy session bound to http": """
        async def fetch(url):
            http = await SessionManager.get_session()
            async with http.get(url) as response:
                return await response.text()
    """,
    "policy session bound to client": """
        async def fetch(url):
            client = await SessionManager.get_session(bypass_proxy=True)
            return await client.post(url)
    """,
    "policy session factory by bare name": """
        async def fetch(url):
            conn = await get_session()
            return await conn.get(url)
    """,
    "factory reached through an imported alias": """
        from session_manager import SessionManager as SM
        async def fetch(url):
            api = await SM.get_session()
            return await api.put(url)
    """,
    "annotated assignment": """
        async def fetch(url):
            http: object = await SessionManager.get_session()
            return await http.get(url)
    """,
    "walrus assignment": """
        async def fetch(url):
            if (http := await SessionManager.get_session()):
                return await http.get(url)
    """,
    "async with ClientSession as client": """
        import aiohttp
        async def fetch(url):
            async with aiohttp.ClientSession() as client:
                return await client.get(url)
    """,
    "alias of a receiver": """
        async def fetch(url):
            http = await SessionManager.get_session()
            other = http
            return await other.get(url)
    """,
    "self attribute set in another method": """
        class Fetcher:
            async def fetch(self, url):
                return await self.http.get(url)

            async def open(self):
                self.http = await SessionManager.get_session()
    """,
    "raw requests session": """
        import requests
        def fetch(url):
            s = requests.Session()
            return s.get(url)
    """,
    "raw httpx client through an import alias": """
        import httpx as web
        def fetch(url):
            c = web.Client()
            return c.get(url)
    """,
}


@pytest.mark.parametrize("name", list(RENAMED_RECEIVERS))
def test_a_call_on_a_renamed_http_receiver_must_disable_redirects(tmp_path, name):
    assert "REDIRECT_NOT_DISABLED" in rules_of(tmp_path, RENAMED_RECEIVERS[name])


def test_a_module_level_receiver_is_seen_inside_a_function(tmp_path):
    code = """
        import aiohttp
        http = aiohttp.ClientSession()
        async def fetch(url):
            return await http.get(url)
    """

    assert "REDIRECT_NOT_DISABLED" in rules_of(tmp_path, code)


def test_a_post_on_a_renamed_receiver_needs_the_sanitizer(tmp_path):
    code = """
        async def send(url, payload):
            http = await SessionManager.get_session()
            return await http.post(url, json=payload, allow_redirects=False)
    """

    assert "POST_WITHOUT_SANITIZATION" in rules_of(tmp_path, code)


# ------------------------------------------------------------------ compliant and unrelated code stays clean
def test_a_compliant_call_on_a_renamed_receiver_is_clean(tmp_path):
    code = """
        async def send(url, payload, sanitizer):
            http = await SessionManager.get_session()
            body = sanitize_outbound_payload(payload, sanitizer)
            return await http.post(url, json=body, allow_redirects=False)
    """

    assert rules_of(tmp_path, code) == set()


@pytest.mark.parametrize(
    "code",
    [
        """
        def read(settings):
            client = {}
            return client.get("key") or settings.get("other")
        """,
        """
        def read(registry):
            http = registry.lookup("x")
            return http.get("key")
        """,
        """
        async def fetch(http, key):
            return http.get(key)
        """,
    ],
    ids=["dict named client", "name from an unrelated call", "parameter that is not bound from a source"],
)
def test_names_that_are_not_http_receivers_are_not_flagged(tmp_path, code):
    assert rules_of(tmp_path, code) == set()


def test_a_receiver_in_one_function_does_not_taint_another_function(tmp_path):
    code = """
        async def producer(url):
            http = await SessionManager.get_session()
            return await http.get(url, allow_redirects=False)

        def unrelated(http):
            return http.get("key")
    """

    assert rules_of(tmp_path, code) == set()


def test_a_name_that_is_ever_bound_to_a_source_stays_a_receiver_in_its_function(tmp_path):
    # Conservative on purpose: the check is flow-insensitive, so a later rebinding does not clear it.
    code = """
        async def fetch(url):
            http = await SessionManager.get_session()
            http = {}
            return http.get("key")
    """

    assert "REDIRECT_NOT_DISABLED" in rules_of(tmp_path, code)


# ------------------------------------------------------------------ the name heuristic is still there
@pytest.mark.parametrize("receiver", ["session", "my_session", "self.session", "self._session"])
def test_the_name_heuristic_still_flags_session_named_receivers(tmp_path, receiver):
    code = f"""
        async def fetch(session, url):
            return await {receiver}.get(url)
    """

    assert "REDIRECT_NOT_DISABLED" in rules_of(tmp_path, code)
