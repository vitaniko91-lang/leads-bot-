from leads_bot.analyzer.prompts import ANALYZER_SYSTEM, build_analyzer_prompt


def test_system_prompt_has_required_fields():
    assert "is_lead" in ANALYZER_SYSTEM
    assert "project_type" in ANALYZER_SYSTEM
    assert "budget_usd" in ANALYZER_SYSTEM
    assert "client_country" in ANALYZER_SYSTEM
    assert "relevance_score" in ANALYZER_SYSTEM
    assert "reasoning" in ANALYZER_SYSTEM


def test_user_prompt_includes_message_and_context():
    prompt = build_analyzer_prompt(
        message_text="Ищу дизайнера на лендинг",
        channel_title="Design Jobs UA",
        channel_language="ru",
    )
    assert "Ищу дизайнера на лендинг" in prompt
    assert "Design Jobs UA" in prompt
