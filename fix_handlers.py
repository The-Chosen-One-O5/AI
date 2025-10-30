#!/usr/bin/env python3
"""
Fix handler signatures and main function for Telethon.
"""

import re

# Read the current file
with open('main.py', 'r') as f:
    lines = f.readlines()

# Find all handler function definitions and modify signatures
modified_lines = []
for i, line in enumerate(lines):
    # Replace Update, context: ContextTypes.DEFAULT_TYPE with event for handlers
    if 'async def ' in line and ('update: Update' in line or 'Update, context: ContextTypes.DEFAULT_TYPE' in line):
        # Extract function name
        match = re.search(r'async def (\w+)\(', line)
        if match:
            func_name = match.group(1)
            # Replace the signature
            new_line = f"async def {func_name}(event):\n"
            modified_lines.append(new_line)
            print(f"Modified: {func_name}")
            continue
    
    # Replace references to update.message with event
    if 'update.message' in line and 'async def' not in line:
        line = line.replace('update.message', 'event')
    
    # Replace update.effective_chat.id with event.chat_id
    if 'update.effective_chat.id' in line:
        line = line.replace('update.effective_chat.id', 'event.chat_id')
    
    # Replace update.effective_message.id with event.id
    if 'update.effective_message.id' in line:
        line = line.replace('update.effective_message.id', 'event.id')
    
    # Replace context.bot with global_context.bot
    if 'context.bot' in line and 'def ' not in line:
        line = line.replace('context.bot', 'global_context.bot')
    
    # Replace context.job_queue with global_context.job_queue
    if 'context.job_queue' in line:
        line = line.replace('context.job_queue', 'global_context.job_queue')
    
    # Replace context.args with event.text.split()[1:]
    if 'context.args' in line:
        line = line.replace('context.args', 'event.text.split()[1:]')
    
    # Replace BadRequest with errors.RPCError
    if 'BadRequest' in line:
        line = line.replace('BadRequest', 'errors.RPCError')
    
    # Replace Application with TelegramClient
    if 'Application' in line and 'from' not in line:
        line = line.replace('Application', 'TelegramClient')
    
    # Replace InputFile with just the file object
    if 'InputFile(' in line:
        line = re.sub(r'InputFile\((.*?),\s*filename=.*?\)', r'\1', line)
    
    modified_lines.append(line)

print(f"\nModified {len([l for l in modified_lines if l != lines[modified_lines.index(l)]])} lines")

# Write back
with open('main.py', 'w') as f:
    f.writelines(modified_lines)

print("Handler signatures updated")
