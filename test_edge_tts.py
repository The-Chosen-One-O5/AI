#!/usr/bin/env python3
"""
Test script for Edge TTS audio generation.
"""

import asyncio
import os
import edge_tts

async def test_edge_tts():
    """Test Edge TTS audio generation."""
    text = "Hello, this is a test of Edge TTS audio generation."
    voice = "en-US-GuyNeural"
    output_file = "/tmp/test_tts_output.mp3"
    
    print(f"Testing Edge TTS with voice: {voice}")
    print(f"Text: {text}")
    print(f"Output file: {output_file}")
    
    try:
        # Generate audio using Edge TTS
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        # Check if file was created
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"✓ Audio file created successfully!")
            print(f"✓ File size: {file_size} bytes")
            
            # Read the file
            with open(output_file, 'rb') as f:
                audio_bytes = f.read()
            print(f"✓ Audio bytes read: {len(audio_bytes)} bytes")
            
            # Clean up
            os.remove(output_file)
            print(f"✓ Cleaned up test file")
            
            return True
        else:
            print("✗ Audio file was not created")
            return False
            
    except Exception as e:
        print(f"✗ Error during audio generation: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_multiple_voices():
    """Test multiple voices."""
    voices = [
        "en-US-GuyNeural",
        "en-US-JennyNeural",
        "en-GB-RyanNeural"
    ]
    
    print("\nTesting multiple voices...")
    for voice in voices:
        print(f"\nTesting voice: {voice}")
        text = f"Testing voice {voice}"
        output_file = f"/tmp/test_{voice.replace('-', '_')}.mp3"
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_file)
            
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"  ✓ {voice}: {file_size} bytes")
                os.remove(output_file)
            else:
                print(f"  ✗ {voice}: File not created")
        except Exception as e:
            print(f"  ✗ {voice}: {e}")

if __name__ == "__main__":
    print("=== Edge TTS Test Suite ===\n")
    
    # Test basic functionality
    success = asyncio.run(test_edge_tts())
    
    if success:
        print("\n=== Basic test PASSED ===")
        # Test multiple voices
        asyncio.run(test_multiple_voices())
    else:
        print("\n=== Basic test FAILED ===")
        print("Note: Edge TTS requires internet connectivity to Microsoft's speech service.")
