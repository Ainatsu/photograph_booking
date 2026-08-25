from backend.app.services.web_page_fetcher import _validate_public_url


def test_ssrf_rejects_localhost_and_private_addresses():
    for url in ("http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data"):
        try:
            _validate_public_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unsafe URL: {url}")
