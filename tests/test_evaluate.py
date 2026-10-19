from text2sql.evaluate import results_match


def test_ignores_row_and_column_order():
    assert results_match([("a", 1), ("b", 2)], [(2, "b"), (1, "a")])


def test_numbers_compare_to_two_decimals():
    assert results_match([(3, 10.0)], [(3.0, 9.999)])


def test_different_values_do_not_match():
    assert not results_match([("a", 1)], [("a", 2)])


def test_missing_or_extra_rows_do_not_match():
    assert not results_match([("a",), ("b",)], [("a",)])
    assert not results_match([("a",)], [("a",), ("a",)])
