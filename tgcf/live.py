"""The module responsible for operating tgcf in live mode."""
import json
import logging
import os
import sys
from typing import Union
import requests

from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message
import datetime
from tgcf import config, const
from tgcf import storage as st
from tgcf.bot import get_events
from tgcf.config import CONFIG, get_SESSION
from tgcf.plugins import apply_plugins, load_async_plugins
from tgcf.utils import clean_session_files, send_message
from .MinioUploader import MinioUploader
from telethon.network.mtprotostate import MSG_TOO_OLD_DELTA

async def new_message_handler(event: Union[Message, events.NewMessage]) -> None:
    """Process new incoming messages."""
    chat_id = event.chat_id

    if chat_id not in config.from_to:
        return
    logging.info(f"New message received in {chat_id}")
    current_datetime = datetime.datetime.now()
    logging.info(f"current_datetime {current_datetime}")
    print(MSG_TOO_OLD_DELTA)


    message = event.message

    message_data = {
        'telegram_id': event.message.peer_id.channel_id,
        'post_id': event.message.id,
        'date': event.message.date.isoformat(),
        'type': 'text',
        'photo': None,
        'view_count': event.message.views,
    }
    if len(f"{event.message.message}") > 2:
        message_data['text'] = event.message.message,


    # Check if media in the message is a photo

    if event.message.media and hasattr(event.message.media, 'photo'):
        photo = event.message.media.photo
        file_name = await event.client.download_media(photo, file=f'{photo.id}')

        minio_client = MinioUploader(file_name)
        result = minio_client.upload_to_minio(have_thumbnail=True)

        logging.info(f"result {result}")
        if result:
            photo_data = {
                'id': f"{photo.id}",
                'thumb': f"{photo.id}.thumb_411",
                'type': 'photo',
                'width': photo.sizes[-1].w,
                'height': photo.sizes[-1].h,
                # 'size': photo.sizes[-1].size,
            }
            message_data['photo'] = photo_data
            message_data['media__telegram_id'] = photo.id
            message_data['type'] = "photo"

    message_create_url = os.getenv("MESSAGE_CREATE_URL", "localhost")
    response = requests.post(message_create_url, json=json.dumps(message_data), timeout=60)
    logging.info(f"message_data {message_data},status: {response.status_code}")
    logging.info(f"message_created_datetime {current_datetime}")

    event_uid = st.EventUid(event)

    length = len(st.stored)
    exceeding = length - const.KEEP_LAST_MANY

    if exceeding > 0:
        for key in st.stored:
            del st.stored[key]
            break

    dest = config.from_to.get(chat_id)

    tm = await apply_plugins(message)
    if not tm:
        return

    if event.is_reply:
        r_event = st.DummyEvent(chat_id, event.reply_to_msg_id)
        r_event_uid = st.EventUid(r_event)

    st.stored[event_uid] = {}
    # for d in dest:
    #     if event.is_reply and r_event_uid in st.stored:
    #         tm.reply_to = st.stored.get(r_event_uid).get(d)
    #     fwded_msg = await send_message(d, tm)
    #     st.stored[event_uid].update({d: fwded_msg})
    tm.clear()


async def edited_message_handler(event) -> None:
    """Handle message edits."""
    message = event.message

    chat_id = event.chat_id

    if chat_id not in config.from_to:
        return

    logging.info(f"Message edited in {chat_id}")

    event_uid = st.EventUid(event)

    tm = await apply_plugins(message)

    if not tm:
        return

    fwded_msgs = st.stored.get(event_uid)

    if fwded_msgs:
        for _, msg in fwded_msgs.items():
            if config.CONFIG.live.delete_on_edit == message.text:
                await msg.delete()
                await message.delete()
            else:
                await msg.edit(tm.text)
        return

    dest = config.from_to.get(chat_id)

    for d in dest:
        await send_message(d, tm)
    tm.clear()


async def deleted_message_handler(event):
    """Handle message deletes."""
    chat_id = event.chat_id
    if chat_id not in config.from_to:
        return

    logging.info(f"Message deleted in {chat_id}")

    event_uid = st.EventUid(event)
    fwded_msgs = st.stored.get(event_uid)
    if fwded_msgs:
        for _, msg in fwded_msgs.items():
            await msg.delete()
        return


ALL_EVENTS = {
    "new": (new_message_handler, events.NewMessage()),
    # "edited": (edited_message_handler, events.MessageEdited()),
    # "deleted": (deleted_message_handler, events.MessageDeleted()),
}


async def start_sync() -> None:
    """Start tgcf live sync."""
    # clear past session files
    clean_session_files()
    print("hello2")
    print(MSG_TOO_OLD_DELTA)

    # load async plugins defined in plugin_models
    await load_async_plugins()

    SESSION = get_SESSION()
    client = TelegramClient(
        SESSION,
        CONFIG.login.API_ID,
        CONFIG.login.API_HASH,
        sequential_updates=CONFIG.live.sequential_updates,
    )
    if CONFIG.login.user_type == 0:
        if CONFIG.login.BOT_TOKEN == "":
            logging.warning("Bot token not found, but login type is set to bot.")
            sys.exit()
        await client.start(bot_token=CONFIG.login.BOT_TOKEN)
    else:
        await client.start()
    config.is_bot = await client.is_bot()
    logging.info(f"config.is_bot={config.is_bot}")
    command_events = get_events()

    await config.load_admins(client)

    ALL_EVENTS.update(command_events)

    for key, val in ALL_EVENTS.items():
        if config.CONFIG.live.delete_sync is False and key == "deleted":
            continue
        client.add_event_handler(*val)
        logging.info(f"Added event handler for {key}")

    if config.is_bot and const.REGISTER_COMMANDS:
        await client(
            functions.bots.SetBotCommandsRequest(
                scope=types.BotCommandScopeDefault(),
                lang_code="en",
                commands=[
                    types.BotCommand(command=key, description=value)
                    for key, value in const.COMMANDS.items()
                ],
            )
        )
    config.from_to = await config.load_from_to(client, config.CONFIG.forwards)
    await client.run_until_disconnected()
