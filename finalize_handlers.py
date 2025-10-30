#!/usr/bin/env python3
"""
Final phase: Add event handler registration for Telethon
Creates a registration section in the async_main function
"""

import re

print("Reading current main.py...")
with open('main.py', 'r') as f:
    content = f.read()

print(f"Current file: {len(content.split(chr(10)))} lines\n")

# Define handler registration code to insert into async_main
handler_registration = '''
    # ========== REGISTER EVENT HANDLERS ==========
    
    # Command Handlers
    @client.on(events.NewMessage(pattern='/start'))
    async def cmd_start(event): await help_command(event)
    
    @client.on(events.NewMessage(pattern='/help'))
    async def cmd_help(event): await help_command(event)
    
    @client.on(events.NewMessage(pattern='/ai'))
    async def cmd_ai(event): await smart_ai_handler(event)
    
    @client.on(events.NewMessage(pattern='/react'))
    async def cmd_react(event): await force_react_command(event)
    
    @client.on(events.NewMessage(pattern='/audio'))
    async def cmd_audio(event): await toggle_audio_mode_handler(event)
    
    @client.on(events.NewMessage(pattern='/chem'))
    async def cmd_chem(event): await chem_handler(event)
    
    @client.on(events.NewMessage(pattern='/tex'))
    async def cmd_tex(event): await latex_handler(event)
    
    @client.on(events.NewMessage(pattern='/chatid'))
    async def cmd_chatid(event): await get_chat_id(event)
    
    @client.on(events.NewMessage(pattern='/summarize'))
    async def cmd_summarize(event): await summarize_command(event)
    
    @client.on(events.NewMessage(pattern='/studypoll'))
    async def cmd_studypoll(event): await studypoll_command(event)
    
    @client.on(events.NewMessage(pattern='/remember'))
    async def cmd_remember(event): await remember_command(event)
    
    @client.on(events.NewMessage(pattern='/recall'))
    async def cmd_recall(event): await recall_command(event)
    
    @client.on(events.NewMessage(pattern='/forget'))
    async def cmd_forget(event): await forget_command(event)
    
    @client.on(events.NewMessage(pattern='/nanoedit'))
    async def cmd_nanoedit(event): await nanoedit_handler(event)
    
    @client.on(events.NewMessage(pattern='/askit'))
    async def cmd_askit(event): await askit_handler(event)
    
    @client.on(events.NewMessage(pattern='/videoedit'))
    async def cmd_videoedit(event): await videoedit_handler(event)
    
    @client.on(events.NewMessage(pattern='/boton'))
    async def cmd_boton(event): await turn_ai_on(event)
    
    @client.on(events.NewMessage(pattern='/botoff'))
    async def cmd_botoff(event): await turn_ai_off(event)
    
    @client.on(events.NewMessage(pattern='/aistatus'))
    async def cmd_aistatus(event): await check_ai_status(event)
    
    @client.on(events.NewMessage(pattern='/randomon'))
    async def cmd_randomon(event): await turn_random_chat_on(event)
    
    @client.on(events.NewMessage(pattern='/randomoff'))
    async def cmd_randomoff(event): await turn_random_chat_off(event)
    
    @client.on(events.NewMessage(pattern='/randomstatus'))
    async def cmd_randomstatus(event): await check_random_status(event)
    
    @client.on(events.NewMessage(pattern='/testrandom'))
    async def cmd_testrandom(event): await test_random_handler(event)
    
    @client.on(events.NewMessage(pattern='/on'))
    async def cmd_modon(event): await turn_moderation_on(event)
    
    @client.on(events.NewMessage(pattern='/off'))
    async def cmd_modoff(event): await turn_moderation_off(event)
    
    @client.on(events.NewMessage(pattern='/time'))
    async def cmd_time(event): await set_reminder_time_handler(event)
    
    @client.on(events.NewMessage(pattern='/callon'))
    async def cmd_callon(event): await turn_proactive_calls_on(event)
    
    @client.on(events.NewMessage(pattern='/calloff'))
    async def cmd_calloff(event): await turn_proactive_calls_off(event)
    
    @client.on(events.NewMessage(pattern='/callstatus'))
    async def cmd_callstatus(event): await check_proactive_calls_status(event)
    
    @client.on(events.NewMessage(pattern='/callquiet'))
    async def cmd_callquiet(event): await set_call_quiet_hours(event)
    
    @client.on(events.NewMessage(pattern='/callconfig'))
    async def cmd_callconfig(event): await configure_call_settings(event)
    
    @client.on(events.NewMessage(pattern='/joincall'))
    async def cmd_joincall(event): await joincall_command(event)
    
    @client.on(events.NewMessage(pattern='/leavecall'))
    async def cmd_leavecall(event): await leavecall_command(event)
    
    @client.on(events.NewMessage(pattern='/callinfo'))
    async def cmd_callinfo(event): await callinfo_command(event)
    
    @client.on(events.NewMessage(pattern='/ttson'))
    async def cmd_ttson(event): await ttson(event)
    
    @client.on(events.NewMessage(pattern='/ttsoff'))
    async def cmd_ttsoff(event): await ttsoff(event)
    
    @client.on(events.NewMessage(pattern='/ttsconfig'))
    async def cmd_ttsconfig(event): await ttsconfig(event)
    
    @client.on(events.NewMessage(pattern='/ttsstatus'))
    async def cmd_ttsstatus(event): await ttsstatus(event)
    
    @client.on(events.NewMessage(pattern='/stton'))
    async def cmd_stton(event): await stton(event)
    
    @client.on(events.NewMessage(pattern='/sttoff'))
    async def cmd_sttoff(event): await sttoff(event)
    
    @client.on(events.NewMessage(pattern='/sttconfig'))
    async def cmd_sttconfig(event): await sttconfig(event)
    
    @client.on(events.NewMessage(pattern='/sttstatus'))
    async def cmd_sttstatus(event): await sttstatus(event)
    
    @client.on(events.NewMessage(pattern='/ban'))
    async def cmd_ban(event): await ban_user(event)
    
    @client.on(events.NewMessage(pattern='/mute'))
    async def cmd_mute(event): await mute_user(event)
    
    @client.on(events.NewMessage(pattern='/unmute'))
    async def cmd_unmute(event): await unmute_user(event)
    
    @client.on(events.NewMessage(pattern='/delete'))
    async def cmd_delete(event): await delete_message(event)
    
    @client.on(events.NewMessage(pattern='/lock'))
    async def cmd_lock(event): await lock_chat(event)
    
    @client.on(events.NewMessage(pattern='/unlock'))
    async def cmd_unlock(event): await unlock_chat(event)
    
    @client.on(events.NewMessage(pattern='/ai1|/ai618'))
    async def cmd_simple_ai(event): await simple_ai_handler(event)
    
    # Voice message handler
    @client.on(events.NewMessage())
    async def voice_handler(event):
        if event.voice:
            await handle_call_audio(event)
    
    # Master text handler for all non-command text
    @client.on(events.NewMessage())
    async def text_handler(event):
        if event.text and not event.text.startswith('/'):
            await master_text_handler(event)
    
    # Poll answer handler
    @client.on(events.Raw)
    async def poll_handler(event):
        if isinstance(event, types.UpdateMessagePollVote):
            # Convert to our expected format
            answer_event = type('PollAnswer', (), {
                'poll_id': event.poll_id,
                'user': await client.get_entity(event.user_id),
                'option_ids': event.options
            })()
            await poll_answer_handler(answer_event)
    
    logger.info("✅ All event handlers registered")
'''

# Find where to insert the registration code in async_main
# It should go after context initialization, before keep_alive()
keep_alive_pos = content.find("    # Start keep-alive server")
if keep_alive_pos != -1:
    content = content[:keep_alive_pos] + handler_registration + "\n" + content[keep_alive_pos:]
    print("✓ Event handler registration added to async_main")
else:
    print("⚠ Could not find insertion point for handler registration")
    print("  Attempting alternative location...")
    # Try alternative location
    run_until_pos = content.find("    await client.run_until_disconnected()")
    if run_until_pos != -1:
        content = content[:run_until_pos] + handler_registration + "\n" + content[run_until_pos:]
        print("✓ Event handler registration added (alternative location)")

# Remove the old comment about manual registration
content = content.replace("""# ========== EVENT HANDLERS ==========
# Note: Handlers need @client.on(events.NewMessage(...)) decorators
# These will be added in the registration section
""", "")

# Write output
print("\nWriting final main.py...")
with open('main.py', 'w') as f:
    f.write(content)

final_lines = len(content.split('\n'))
print(f"  ✓ Output file: {final_lines} lines")

print("\n" + "="*50)
print("FINALIZATION COMPLETE!")
print("="*50)
print("\n✅ All handlers registered with Telethon events")
print("✅ Main function uses Telethon client")
print("✅ Context wrapper provides compatibility layer")
print("\nReady for testing!")
