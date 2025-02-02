#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Jins Mathew | UFSBotz

import os
import random
import time
import asyncio
import logging
import pyrogram

from PIL import Image
from pyrogram.errors import FloodWait

from helper_funcs.help_Nekmo_ffmpeg import take_screen_shot
from helper_funcs.progress import Progress
from helper_funcs.thumbnail_fixation import fix_thumb
from script import script
from pyrogram import Client, filters
from database.ufs_db import rename_db
from pyrogram.types import ForceReply
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from helper_funcs.display_progress import progress_for_pyrogram

if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config, temp
else:
    from config import Config, temp

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


async def force_name(bot, message):
    await bot.send_message(
        message.reply_to_message.from_user.id,
        "**Enter New Name For Your Media.\n\nNote :-** `Extension Not Required`",
        reply_to_message_id=message.reply_to_message.id,
        reply_markup=ForceReply(True)
    )


@Client.on_message(filters.private & filters.reply & filters.text)
async def cus_name(bot, message):
    if message.reply_to_message.reply_markup and isinstance(message.reply_to_message.reply_markup, ForceReply):
        asyncio.create_task(rename_doc(bot, message, False))
    else:
        print('No Media Present')


async def rename_doc(bot, message, default):
    # actual_name = None
    # file_name = None
    try:
        media = await bot.get_messages(
            message.chat.id,
            message.reply_to_message.id
        )

        if not default:
            await bot.delete_messages(
                chat_id=message.chat.id,
                message_ids=message.reply_to_message.id
            )
            media = media.reply_to_message

        if media.empty:
            await message.reply_text('Why Did You Delete That 😕', True)
            return

        filetype = media.document or media.video or media.audio or media.voice or media.video_note
        try:
            actual_name = filetype.file_name
            file_name = filetype.file_name
            # splitit = file_name.split(".")
            file_name = file_name[0:-4]
            extension = (actual_name[-3:])
        except:
            extension = "mkv"

        await bot.delete_messages(
            chat_id=message.chat.id,
            message_ids=message.id,
            revoke=True
        )

        BANNED_USERS = await rename_db.get_banned()

        if message.reply_to_message.from_user.id not in BANNED_USERS:
            if not default:
                file_name = message.text
            description = script.CUSTOM_CAPTION_UL_FILE.format(newname=file_name)
            download_location = Config.DOWNLOAD_LOCATION + "/"

            sendmsg = await bot.send_message(
                chat_id=message.chat.id,
                text=script.DOWNLOAD_START,
                reply_to_message_id=media.id
            )

            c_time = time.time()
            the_real_download_location = await bot.download_media(
                message=media,
                file_name=download_location,
                progress=progress_for_pyrogram,
                progress_args=(
                    "**Status :** `Download Starting 📥`\n\n**• FileName :** `{}`".format(actual_name),
                    sendmsg,
                    c_time
                )
            )
            if the_real_download_location is not None:
                try:
                    await sendmsg.edit_text(
                        text=script.SAVED_RECVD_DOC_FILE)
                except:
                    await sendmsg.delete()
                    sendmsg = await message.reply_text(script.SAVED_RECVD_DOC_FILE, quote=True)

                new_file_name = download_location + file_name + "." + extension
                os.rename(the_real_download_location, new_file_name)
                try:
                    await sendmsg.edit_text(
                        text="**Status :** `Upload Starting 📤`\n\n**• FileName :** `{}`".format(
                            file_name + "." + extension)
                    )
                except Exception as e:
                    await sendmsg.delete()
                    sendmsg = await message.reply_text(script.UPLOAD_START, quote=True)
                # logger.info(the_real_download_location)

                thumb_image_path = download_location + str(media.from_user.id) + ".jpg"
                thumb_image = await rename_db.get_thumb(media.from_user.id)
                g_doc, bot_up = await rename_db.get_user_by_id(media.from_user.id)

                if not os.path.exists(thumb_image_path):
                    if thumb_image is not None:
                        await bot.download_media(message=thumb_image, file_name=thumb_image_path)
                        thumb_image = thumb_image_path
                    else:
                        thumb_image = None
                else:
                    thumb_image = thumb_image_path

                if thumb_image:
                    d_thumb = thumb_image
                else:
                    d_thumb = None

                width, height, d_thumb = await fix_thumb(d_thumb)

                c_time = time.time()
                prog = Progress(media.from_user.id, bot, sendmsg)
                if g_doc:
                    sent_message = await bot.send_document(
                        chat_id=message.chat.id,
                        document=new_file_name,
                        thumb=d_thumb,
                        caption=description,
                        # reply_markup=reply_markup,
                        reply_to_message_id=media.id,
                        progress=prog.progress_for_pyrogram,
                        progress_args=(
                            f"**• Uploading 📤 :** `{file_name}.{extension}`",
                            c_time,
                        )
                    )
                    if message.id != sendmsg.id:
                        try:
                            await sendmsg.delete()
                        except FloodWait as gf:
                            time.sleep(gf.x)
                        except Exception as rr:
                            logging.warning(str(rr))
                    os.remove(new_file_name)
                    if thumb_image_path is not None:
                        os.remove(thumb_image_path)
                else:
                    if actual_name.upper().endswith(
                            ("MKV", "MP4", "WEBM", "FLV", "3GP", "AVI", "MOV", "OGG", "WMV", "M4V",
                             "TS", "MPG", "MTS", "M2TS")):
                        duration = 0
                        try:
                            metadata = extractMetadata(createParser(new_file_name))
                            if metadata.has("duration"):
                                duration = metadata.get("duration").seconds
                        except Exception as g_e:
                            logging.info(g_e)
                        width = 0
                        height = 0
                        d_thumb = None

                        if not thumb_image:
                            logging.info("Taking Screenshot..")
                            try:
                                d_thumb = await take_screen_shot(new_file_name, os.path.dirname(
                                    os.path.abspath(new_file_name)), random.randint(0, duration - 1))
                            except Exception as e:
                                logger.error(e)
                                d_thumb = None
                        else:
                            d_thumb = thumb_image

                        width, height, d_thumb = await fix_thumb(d_thumb)

                        sent_message = await message.reply_video(
                            video=new_file_name,
                            caption=description,
                            duration=duration,
                            width=width,
                            height=height,
                            thumb=d_thumb,
                            supports_streaming=True,
                            disable_notification=True,
                            reply_to_message_id=media.id,
                            progress=prog.progress_for_pyrogram,
                            progress_args=(
                                f"**• Uploading 📤 :** `{file_name}.{extension}`",
                                c_time,
                            ),
                        )
                        if message.id != sendmsg.id:
                            try:
                                await sendmsg.delete()
                            except FloodWait as gf:
                                time.sleep(gf.x)
                            except Exception as rr:
                                logging.warning(str(rr))
                        os.remove(new_file_name)

                        if thumb_image_path is not None:
                            os.remove(thumb_image_path)

                if media.from_user.id not in Config.ADMINS:
                    try:
                        await bot.edit_message_text(
                            text=script.AFTER_SUCCESSFUL_UPLOAD_MSG,
                            chat_id=message.chat.id,
                            message_id=sendmsg.id,
                            disable_web_page_preview=True
                        )
                    except:
                        await sendmsg.delete()
                        await message.reply_text(script.AFTER_SUCCESSFUL_UPLOAD_MSG, quote=True)

                if not media.from_user.id in Config.AUTH_USERS:
                    FRM_USER = f"By User <b>[<a href='tg://user?id={media.from_user.id}'>{media.from_user.first_name}</a>]</b>" \
                               f"<code>[{media.from_user.id}]</code> "
                    caption = FRM_USER if not sent_message.caption else sent_message.caption.html + "\n\n" + FRM_USER
                    try:
                        channel = await bot.get_chat(Config.USER_LOG_CHANNEL)
                        chat_name = channel.title if channel.type != 'private' else channel.first_name
                        if chat_name:
                            await sent_message.copy(chat_id=Config.USER_LOG_CHANNEL, caption=caption)
                    except Exception as e:
                        await sent_message.copy(chat_id=Config.USER_LOG_CHANNEL, caption=caption)


        else:
            await bot.send_message(
                chat_id=message.chat.id,
                text="You're B A N N E D",
                reply_to_message_id=message.id
            )
    except Exception as e:
        await bot.send_message(bot, Config.LOG_CHANNEL, str(e))
