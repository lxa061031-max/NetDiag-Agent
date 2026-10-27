import pandas as pd

from src.reporting.visualization import create_trend_figure


def test_create_trend_figure() -> None:
    dataframe = pd.DataFrame(
        {
            "timestamp": ["2026-10-01 08:00", "2026-10-01 08:01"],
            "latency_ms": [20.0, 35.0],
            "packet_loss_pct": [0.0, 1.2],
        }
    )

    figure = create_trend_figure(
        dataframe, ["latency_ms", "packet_loss_pct"], "timestamp"
    )

    assert len(figure.data) == 2
    assert figure.data[0].name == "latency_ms"
    assert list(figure.data[0].y) == [20.0, 35.0]
