from app.utils.pagination import PageParams
from app.utils.slug import generate_slug, generate_unique_slug


def test_generate_slug_basic():
    assert generate_slug("Hello World") == "hello-world"


def test_generate_slug_special_characters():
    assert generate_slug("FastAPI & SQLAlchemy: A Guide!") == "fastapi-sqlalchemy-a-guide"


def test_generate_slug_unicode():
    assert generate_slug("Café Résumé") == "cafe-resume"


def test_generate_slug_extra_whitespace():
    assert generate_slug("  Too   Many   Spaces  ") == "too-many-spaces"


def test_generate_unique_slug_has_expected_prefix():
    slug = generate_unique_slug("My Post Title")
    assert slug.startswith("my-post-title-")


def test_generate_unique_slug_is_unique_across_calls():
    first = generate_unique_slug("Same Title")
    second = generate_unique_slug("Same Title")
    assert first != second


def test_generate_unique_slug_suffix_length():
    slug = generate_unique_slug("Post")
    suffix = slug.rsplit("-", 1)[-1]
    assert len(suffix) == 8


def test_page_params_offset_first_page():
    params = PageParams(page=1, page_size=20)
    assert params.offset == 0
    assert params.limit == 20


def test_page_params_offset_second_page():
    params = PageParams(page=2, page_size=20)
    assert params.offset == 20


def test_page_params_offset_arbitrary_page():
    params = PageParams(page=5, page_size=10)
    assert params.offset == 40
    assert params.limit == 10
