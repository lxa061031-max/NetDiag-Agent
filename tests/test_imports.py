def test_data_module_import() -> None:
    from src import data_processing

    assert callable(data_processing.read_csv)
    assert callable(data_processing.build_data_summary)
