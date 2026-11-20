from __future__ import annotations

from menschheit.debate.models import ScoreBlock


def test_moderation_flags_are_real_booleans() -> None:
    from menschheit.storage import Database, Repository

    db = Database("sqlite:///:memory:")
    repo = Repository(db)
    debate = repo.create_debate(
        topic="Ein ausreichend langes Thema",
        language="de",
        rounds_requested=1,
        models={"pro": "p", "contra": "c", "judge": "j", "moderator": "m"},
    )
    repo.add_turn(
        debate_id=debate["id"],
        round_no=1,
        role="pro",
        steelman="Gegenposition",
        public_argument="These",
        internal_reasoning="privat",
        confidence=80,
        conceded=[],
        falsification="Bedingung",
    )
    repo.add_moderation(
        debate_id=debate["id"],
        round_no=1,
        summary="Runde",
        sycophancy=True,
        drift=False,
        decision="CONTINUE_REFINE",
        directive="Weiter",
    )
    moderation = repo.list_moderations(debate["id"])[0]
    assert moderation["sycophancy"] is True
    assert moderation["drift"] is False
    debate = repo.get_debate(debate["id"])
    assert debate["moderations"][0]["sycophancy"] is True


def test_score_block_ignores_model_total() -> None:
    block = ScoreBlock.model_validate(
        {"claims": 8, "logic": 9, "qualifiers": 7, "rebuttals": 8, "realism": 8, "total": 999}
    )
    assert block.computed_total() == 40
    block.total = block.computed_total()
    assert block.total == 40