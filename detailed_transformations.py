#!/usr/bin/env python3
"""
Detailed transformations for Telethon port - Phase 2
Handles all internal references within handler functions
"""

import re

print("Reading current main.py...")
with open('main.py', 'r') as f:
    content = f.read()

print(f"Current file: {len(content.split(chr(10)))} lines\n")

# ========== Replacements ==========
replacements = [
    # Update object references
    ('update.message.chat_id', 'event.chat_id'),
    ('update.message.chat.id', 'event.chat_id'),
    ('update.effective_chat.id', 'event.chat_id'),
    ('update.effective_message.id', 'event.id'),
    ('update.message.message_id', 'event.id'),
    ('update.message.from_user', 'event.sender'),
    ('update.message.text', 'event.text'),
    ('update.message.voice', 'event.voice'),
    ('update.message.photo', 'event.photo'),
    ('update.message.reply_to_message', 'event.reply_to_msg_id and await event.get_reply_message()'),
    ('update.message.reply_text', 'await event.reply'),
    ('update.message.reply_photo', 'await event.respond(file='),
    ('update.message.delete()', 'await event.delete()'),
    
    # Context references
    ('context.bot', 'global_context.bot'),
    ('context.job_queue', 'global_context.job_queue'),
    ('context.args', 'event.text.split()[1:]'),
    
    # Error handling
    ('BadRequest', 'errors.RPCError'),
    ('except BadRequest', 'except errors.RPCError'),
    
    # Other
    ('InputFile(', '('),
    ('.username', '.username or ""'),
    ('.first_name', '.first_name or "User"'),
]

print("Applying replacements:")
for old, new in replacements:
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        print(f"  ✓ {old} → {new} ({count} occurrences)")

# Special case: context.job.data references
content = re.sub(r'context\.job\.data\[([^\]]+)\]', r'context.job.data.get(\1)', content)
print("  ✓ context.job.data references updated")

# Special case: is_user_admin function
is_user_admin_old = '''async def is_user_admin(chat_id: int, user_id: int, context) -> bool:
    if chat_id > 0: return False # No admins in private chats
    try:
        chat_admins = await context.bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in chat_admins)
    except errors.RPCError:
        logger.warning(f"Could not get admins for chat {chat_id}. Assuming user {user_id} is not admin.")
        return False'''

is_user_admin_new = '''async def is_user_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin using Telethon"""
    if chat_id > 0: return False  # No admins in private chats
    try:
        chat_admins = await global_context.bot.get_chat_administrators(chat_id)
        return any(admin.id == user_id for admin in chat_admins)
    except errors.RPCError:
        logger.warning(f"Could not get admins for chat {chat_id}. Assuming user {user_id} is not admin.")
        return False'''

if 'async def is_user_admin' in content:
    # Find and replace the function
    pattern = r'async def is_user_admin\(.*?\).*?return False'
    content = re.sub(pattern, is_user_admin_new, content, flags=re.DOTALL, count=1)
    print("  ✓ is_user_admin function updated")

# Update calls to is_user_admin to remove context parameter
content = re.sub(r'is_user_admin\(([^,]+),\s*([^,]+),\s*context\)', r'is_user_admin(\1, \2)', content)
print("  ✓ is_user_admin calls updated")

# Fix delete_message_callback function
delete_msg_old = '''async def delete_message_callback(context):
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.data['chat_id'], message_id=job.data['message_id'])
    except errors.RPCError: pass # Ignore if message already deleted'''

if 'async def delete_message_callback' in content:
    pattern = r'async def delete_message_callback\(context\):.*?except.*?pass'
    content = re.sub(pattern, delete_msg_old, content, flags=re.DOTALL, count=1)
    print("  ✓ delete_message_callback updated")

# Fix send_deletable_message function
send_deletable_old_pattern = r'async def send_deletable_message\(context.*?\n.*?return None'
send_deletable_new = '''async def send_deletable_message(chat_id: int, text: str, reply_to_message_id: int = None):
    """Send a message that will be deleted after 120 seconds"""
    try:
        sent_message = await global_context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id, parse_mode='Markdown')
        global_context.job_queue.run_once(delete_message_callback, 120, data={'chat_id': chat_id, 'message_id': sent_message.id})
        return sent_message
    except errors.RPCError as e:
        logger.error(f"Failed to send deletable message (Markdown error?): {e}")
        try:
            sent_message = await global_context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id)
            global_context.job_queue.run_once(delete_message_callback, 120, data={'chat_id': chat_id, 'message_id': sent_message.id})
            return sent_message
        except Exception as e2:
            logger.error(f"Failed to send deletable message as plain text: {e2}")
            return None'''

if 'async def send_deletable_message' in content:
    content = re.sub(send_deletable_old_pattern, send_deletable_new, content, flags=re.DOTALL, count=1)
    print("  ✓ send_deletable_message updated")

# Fix send_final_response function signature
content = re.sub(
    r'async def send_final_response\(update.*?context.*?prompt_title',
    'async def send_final_response(event, response_text, thinking_message, prompt_title',
    content
)
print("  ✓ send_final_response signature updated")

# Fix send_or_telegraph_fallback function signature
content = re.sub(
    r'async def send_or_telegraph_fallback\(update.*?context.*?prompt_title',
    'async def send_or_telegraph_fallback(event, response_text, thinking_message, prompt_title',
    content
)
print("  ✓ send_or_telegraph_fallback signature updated")

# Fix generate_call_response signature
content = re.sub(
    r'async def generate_call_response\(chat_id: str, context.*?\)',
    'async def generate_call_response(chat_id: str)',
    content
)
print("  ✓ generate_call_response signature updated")

# Fix handle_call_audio signature
content = re.sub(
    r'async def handle_call_audio\(update.*?context.*?\):',
    'async def handle_call_audio(event):',
    content
)
print("  ✓ handle_call_audio signature updated")

# Fix poll_answer_handler signature and make it work with Telethon
poll_answer_pattern = r'async def poll_answer_handler\(update.*?context.*?\):'
content = re.sub(poll_answer_pattern, 'async def poll_answer_handler(event):', content)
print("  ✓ poll_answer_handler signature updated")

# Fix post_init and post_shutdown
content = re.sub(
    r'async def post_init\(application: Application\)',
    'async def post_init()',
    content
)
content = re.sub(
    r'async def post_shutdown\(application: Application\)',
    'async def post_shutdown()',
    content
)
print("  ✓ post_init/post_shutdown signatures updated")

# Write output
print("\nWriting updated main.py...")
with open('main.py', 'w') as f:
    f.write(content)

final_lines = len(content.split('\n'))
print(f"  ✓ Output file: {final_lines} lines")

print("\n" + "="*50)
print("DETAILED TRANSFORMATIONS COMPLETE!")
print("="*50)
print("\nNext steps:")
print("  1. Manually add @client.on decorators to each handler")
print("  2. Test basic functionality")
print("  3. Fix any remaining edge cases")
