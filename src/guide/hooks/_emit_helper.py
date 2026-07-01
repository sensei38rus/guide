from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guide.evidence.schemas import GuideEvent

# All check codes that each hook evaluates — used for recording clean passes
_HOOK_CHECKS: dict[str, list[str]] = {
    "commit-msg": ["MSG001", "MSG002", "MSG003", "RAT001", "TEST001"],
    "pre-commit": ["DIFF001", "DIFF002", "TEST001"],
    "pre-push":   ["PUSH001"],
}


def emit_hook_event(
    *,
    hook: str,
    object_label: str,
    violation_codes: list[str],
    hint_text: str,
    config: dict,
    task_ref: str = "",
    commit_hash: str = "",
) -> dict[str, bool]:
    
    show_map: dict[str, bool] = {code: True for code in violation_codes}

    try:
        from guide.evidence.schemas import GuideEvent, Action, EvidenceLinks, build_actor
        from guide.evidence.emitter import emit, _resolve_log_path
        from guide.config import get_strictness
        from guide.profile import (
            load_profile, save_profile,
            update_profile_for_hook, should_show_hint,
        )

        # ── adaptive profile ──────────────────────────────────────────
        profile = load_profile(config)
        all_codes = _HOOK_CHECKS.get(hook, list(violation_codes))
        update_profile_for_hook(violation_codes, all_codes, profile, config)

        # Determine which codes should be shown (quiet-mode filtering)
        for code in violation_codes:
            show_map[code] = should_show_hint(code, profile, config)

        save_profile(profile, config)

        # ── build action verb ─────────────────────────────────────────
        if not violation_codes:
            action = Action.CHECKED
        elif get_strictness(config) == "block":
            action = Action.BLOCKED
        else:
            action = Action.PROMPTED

        actor = build_actor()
        log_path = str(_resolve_log_path(config))

        event = GuideEvent(
            action=action,
            object=object_label,
            actor=actor,
            hook=hook,
            course=config.get("course", ""),
            violation_codes=violation_codes,
            hint_shown=hint_text[:500] if hint_text else "",
            evidence=EvidenceLinks(
                commit_hash=commit_hash,
                local_log_path=log_path,
                task_ref=task_ref,
            ),
        )

        emit(event, config)

    except Exception:
        # Evidence writing must never crash a hook
        pass

    return show_map
