from desktop_agent.config import load_settings


def test_defaults_match_spec():
    s = load_settings()
    assert s.ollama_base == "http://127.0.0.1:11434"
    assert s.model_main == "gemma4:31b-cloud"
    assert (s.max_steps, s.max_seconds, s.max_llm_calls) == (30, 600, 120)
