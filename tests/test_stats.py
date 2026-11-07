from eyestrainer.core.stats import (
    clamp,
    median,
    median_iqr,
    percentile,
    safe_div,
    weighted_mean,
)


def test_median():
    assert median([]) is None
    assert median([3]) == 3
    assert median([1, 3]) == 2
    assert median([4, 1, 3, 2]) == 2.5


def test_percentile():
    assert percentile([], 50) is None
    assert percentile([10], 50) == 10
    assert percentile([0, 10], 0) == 0
    assert percentile([0, 10], 100) == 10
    assert percentile([0, 10], 50) == 5
    assert percentile([0, 1, 2, 3], 25) == 0.75


def test_median_iqr():
    med, p25, p75 = median_iqr([1, 2, 3, 4, 5])
    assert med == 3
    assert p25 == 2
    assert p75 == 4
    assert median_iqr([]) == (None, None, None)


def test_weighted_mean_and_safe_div():
    assert weighted_mean([(10, 1), (20, 3)]) == 17.5
    assert weighted_mean([]) is None
    assert weighted_mean([(10, 0)]) is None
    assert safe_div(4, 2) == 2
    assert safe_div(1, 0) is None


def test_clamp():
    assert clamp(5, 0, 3) == 3
    assert clamp(-1, 0, 3) == 0
    assert clamp(2, 0, 3) == 2
