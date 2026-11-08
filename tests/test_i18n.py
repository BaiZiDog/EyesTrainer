from eyestrainer.core.i18n import normalize_language, translate


def test_translate_and_templates():
    assert translate("开始训练", "zh") == "开始训练"
    assert translate("开始训练", "en") == "Start training"
    assert translate("已导出到 {path}", "en", path="C:/data") == "Exported to C:/data"
    assert translate("第 {round} 回合", "zh", round=2) == "第 2 回合"
    assert translate("第 {round} 回合", "en", round=2) == "Round 2"


def test_normalize_language():
    assert normalize_language("en") == "en"
    assert normalize_language("EN") == "en"
    assert normalize_language("fr") == "zh"
    assert normalize_language(None) == "zh"
