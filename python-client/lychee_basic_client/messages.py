from typing import Any

from .config import Config


def registration_message(config: Config) -> dict[str, Any]:
    return {
        "msg_name": "registration",
        "msg_data": {
            "playerId": config.player_id,
            "playerName": config.player_name,
            "version": config.version,
        },
    }


def ready_message(match_id: str, round_no: int, player_id: int) -> dict[str, Any]:
    return {
        "msg_name": "ready",
        "msg_data": {
            "matchId": match_id,
            "round": round_no,
            "playerId": player_id,
        },
    }


def action_message(
    match_id: str,
    round_no: int,
    player_id: int,
    actions: list[dict[str, Any]],
    *,
    window_card_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    msg_data: dict[str, Any] = {
        "matchId": match_id,
        "round": round_no,
        "playerId": player_id,
        "actions": actions,
    }
    if window_card_action is not None:
        msg_data["windowCardAction"] = window_card_action
    return {
        "msg_name": "action",
        "msg_data": msg_data,
    }


def heartbeat_action(match_id: str, round_no: int, player_id: int) -> dict[str, Any]:
    return action_message(match_id, round_no, player_id, [])
