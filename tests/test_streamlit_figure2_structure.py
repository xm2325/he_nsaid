from pathlib import Path


def test_figure2_tab_is_defined_only_in_article_view() -> None:
    source = (Path(__file__).resolve().parents[1] / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
    assert source.count("with figure2_tab:") == 1
    assert 'summary_tab, figure2_tab, models_tab, validation_tab = st.tabs(' in source
    assert '"Figure 2 PSA cloud"' in source
