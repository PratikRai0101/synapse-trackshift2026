from scripts.generate_synthetic_training import generate


def test_synthetic_generator_is_deterministic_and_labelled():
    first = list(generate(2, 4, 11))
    second = list(generate(2, 4, 11))
    assert first == second
    assert len(first) == 8
    assert all(row["synthetic_label"] for row in first)
    assert {row["ers_mode"] for row in first} <= {"H", "M", "Lharvest", "Lderate"}
