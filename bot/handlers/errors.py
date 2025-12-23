import traceback

from aiogram import Router
from aiogram.types import ErrorEvent

from infrastructure.system_event_logger import log_event


router = Router()


def _extract_user_id(event: ErrorEvent) -> int | None:
    update = event.update
    if update is None:
        return None
    if update.message and update.message.from_user:
        return update.message.from_user.id
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    if update.inline_query and update.inline_query.from_user:
        return update.inline_query.from_user.id
    if update.chosen_inline_result and update.chosen_inline_result.from_user:
        return update.chosen_inline_result.from_user.id
    if update.my_chat_member and update.my_chat_member.from_user:
        return update.my_chat_member.from_user.id
    if update.chat_member and update.chat_member.from_user:
        return update.chat_member.from_user.id
    return None


@router.error()
async def on_error(event: ErrorEvent):
    user_id = _extract_user_id(event)
    update_id = event.update.update_id if event.update else None
    log_event(
        level="ERROR",
        source="bot",
        event="handler_exception",
        message=traceback.format_exc(),
        meta={"user_id": user_id, "update_id": update_id},
    )
