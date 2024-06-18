"""The module for running tgcf in past mode.

- past mode can only operate with a user account.
- past mode deals with all existing messages.
"""

import asyncio
import json
import logging
import time
import os
import requests
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.tl.custom.message import Message
from telethon.tl.patched import MessageService

from tgcf import config
from tgcf import storage as st
from tgcf.MinioUploader import MinioUploader
import datetime
from tgcf.config import CONFIG, get_SESSION, write_config
from tgcf.plugins import apply_plugins, load_async_plugins
from tgcf.utils import clean_session_files, send_message


async def forward_job() -> None:
    """Forward all existing messages in the concerned chats."""
    clean_session_files()

    # load async plugins defined in plugin_models
    await load_async_plugins()    

    if CONFIG.login.user_type != 1:
        logging.warning(
            "You cannot use bot account for tgcf past mode. Telegram does not allow bots to access chat history."
        )
        return
    SESSION = get_SESSION()
    async with TelegramClient(
        SESSION, CONFIG.login.API_ID, CONFIG.login.API_HASH
    ) as client:
        config.from_to = await config.load_from_to(client, config.CONFIG.forwards)
        client: TelegramClient
        for from_to, forward in zip(config.from_to.items(), config.CONFIG.forwards):
            src, dest = from_to
            last_id = 0
            forward: config.Forward
            logging.info(f"Forwarding messages from {src} to {dest}")
            date_from = datetime.datetime.now() - datetime.timedelta(days=int(os.getenv("DURATION", 1)))
            try:
                async for message in client.iter_messages(
                    src, reverse=True, offset_id=forward.offset, offset_date=date_from
                ):
                    message: Message
                    event = st.DummyEvent(message.chat_id, message.id)
                    event_uid = st.EventUid(event)

                    logging.info(f"New message received ")
                    current_datetime = datetime.datetime.now()
                    logging.info(f"current_datetime {current_datetime}")

                    message_data = {
                        'telegram_id': message.peer_id.channel_id,
                        'post_id': message.id,
                        'date': message.date.isoformat(),
                        'type': 'text',
                        'photo': None,
                        'view_count': message.views,
                    }
                    if len(f"{message.message}") > 2:
                        message_data['text'] = message.message

                    # Check if media in the message is a photo

                    if message.media and hasattr(message.media, 'photo'):
                        photo = message.media.photo
                        file_name = await client.download_media(photo, file=f'{photo.id}')

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
                    try:
                        message_create_url = os.getenv("MESSAGE_CREATE_URL", "localhost")
                        response = requests.post(message_create_url, json=message_data, timeout=60)
                        logging.info(f"message_data {message_data},status: {response.status_code}")
                        logging.info(f"message_created_datetime {current_datetime}")
                    except Exception as e:
                        logging.info(f"message create error : {e}")

                    if forward.end and last_id > forward.end:
                        continue
                    if isinstance(message, MessageService):
                        continue
                    try:
                        tm = await apply_plugins(message)
                        if not tm:
                            continue
                        st.stored[event_uid] = {}

                        if message.is_reply:
                            r_event = st.DummyEvent(
                                message.chat_id, message.reply_to_msg_id
                            )
                            r_event_uid = st.EventUid(r_event)
                        for d in dest:
                            if message.is_reply and r_event_uid in st.stored:
                                tm.reply_to = st.stored.get(r_event_uid).get(d)
                            # fwded_msg = await send_message(d, tm)
                            # st.stored[event_uid].update({d: fwded_msg.id})
                        tm.clear()
                        last_id = message.id
                        logging.info(f"forwarding message with id = {last_id}")
                        forward.offset = last_id
                        write_config(CONFIG, persist=False)
                        time.sleep(CONFIG.past.delay)
                        logging.info(f"slept for {CONFIG.past.delay} seconds")

                    except FloodWaitError as fwe:
                        logging.info(f"Sleeping for {fwe}")
                        await asyncio.sleep(delay=fwe.seconds)
                    except Exception as err:
                        logging.exception(err)

            except Exception as e:
                import sys
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                # print(exc_type, fname, exc_tb.tb_lineno)
                logging.info(f"iter message error for: {e} , {exc_type},{fname},{exc_tb.tb_lineno}")

