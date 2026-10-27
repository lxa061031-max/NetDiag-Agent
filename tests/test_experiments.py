import pytest

from scripts.run_experiments import evaluate, row_predictions


def test_row_level_aggregation_deduplicates_metrics() -> None:
    predictions = row_predictions(4, [{"row_index": 1}, {"row_index": 1}, {"row_index": 3}])
    assert predictions == [0, 1, 0, 1]


def test_metrics_and_confusion_matrix() -> None:
    result = evaluate([1, 1, 0, 0], [1, 0, 1, 0])
    assert (result["TP"], result["FP"], result["TN"], result["FN"]) == (1, 1, 1, 1)
    assert result["precision"] == result["recall"] == result["f1"] == 0.5


def test_zero_denominators_and_empty_data() -> None:
    result = evaluate([0, 0], [0, 0])
    assert (result["precision"], result["recall"], result["f1"]) == (0, 0, 0)
    assert row_predictions(0, []) == []
    with pytest.raises(ValueError):
        evaluate([], [])
    with pytest.raises(ValueError):
        row_predictions(1, [{"row_index": 1}])
