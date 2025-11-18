import logging
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is an admin."""
    if update.effective_chat.type == "private":
        return False
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"Admin check error: {e}")
        return False

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("🚫 Admins only.")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user to ban them.")
        return

    user_to_ban = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user_to_ban.id)
        await update.message.reply_text(f"🔨 Banned {user_to_ban.first_name}.")
    except BadRequest as e:
        await update.message.reply_text(f"Failed to ban: {e.message}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("🚫 Admins only.")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user to mute them.")
        return

    user_to_mute = update.message.reply_to_message.from_user
    try:
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(update.effective_chat.id, user_to_mute.id, permissions)
        await update.message.reply_text(f"😶 Muted {user_to_mute.first_name}.")
    except BadRequest as e:
        await update.message.reply_text(f"Failed to mute: {e.message}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    
    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user
    try:
        # Default permissions for a normal user
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True
        )
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions)
        await update.message.reply_text(f"🔊 Unmuted {user.first_name}.")
    except BadRequest as e:
        await update.message.reply_text(f"Error: {e.message}")

async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to delete.")
        return

    try:
        await update.message.reply_to_message.delete()
        await update.message.delete() # Delete command too
    except BadRequest:
        await update.message.reply_text("I can't delete that.")
