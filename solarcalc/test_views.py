import pytest
from solarcalc.views import make_random_name


def test_make_random_name_length():
    # Test that the generated name is always 8 characters long
    random_name = make_random_name()
    assert len(random_name) == 8

def test_make_random_name_characters():
    # Test that the generated name contains only lowercase letters and digits
    random_name = make_random_name()
    for char in random_name:
        assert char.isdigit() or ('a' <= char <= 'z')

def test_make_random_name_uniqueness():
    # Test that multiple calls to make_random_name produce different results
    names = {make_random_name() for _ in range(1000)}
    assert len(names) == 1000  # Ensure all names are unique
