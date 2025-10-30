"""
Telethon Userbot Bootstrap Module

Handles session creation, authentication, connection management,
and graceful shutdown for the Telethon userbot client.
"""

import asyncio
import logging
import os
import sys
from typing import Optional
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


class UserbotClient:
    """
    Manages Telethon userbot session lifecycle including:
    - Session file creation and persistence
    - Phone-based authentication with 2FA support
    - Connection error handling
    - Flood wait management
    - Graceful disconnect
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone_number: str,
        session_path: str = "userbot_session",
        use_string_session: bool = False,
        session_string: Optional[str] = None
    ):
        """
        Initialize userbot client configuration.
        
        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API hash from my.telegram.org
            phone_number: Phone number in international format (e.g., +1234567890)
            session_path: Path for session file (default: userbot_session)
            use_string_session: Use string session instead of file (for cloud deployment)
            session_string: Pre-existing session string (for Docker/cloud deployment)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_path = session_path
        self.use_string_session = use_string_session
        self.session_string = session_string
        self.client: Optional[TelegramClient] = None
        self._connected = False
        
        logger.info(f"UserbotClient initialized for phone: {self._mask_phone(phone_number)}")
    
    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Mask phone number for logging (show first 4 and last 2 digits)"""
        if len(phone) <= 6:
            return "***"
        return f"{phone[:4]}***{phone[-2:]}"
    
    async def start(self, force_sms: bool = False) -> TelegramClient:
        """
        Start the Telethon client and handle authentication flow.
        
        Args:
            force_sms: Force SMS code instead of Telegram app code
            
        Returns:
            Connected TelegramClient instance
            
        Raises:
            ValueError: If credentials are invalid
            RuntimeError: If connection fails
        """
        try:
            # Create session
            if self.use_string_session or self.session_string:
                # Use SESSION_STRING from environment or provided session_string
                session_str = self.session_string or os.environ.get('SESSION_STRING', None)
                if not session_str:
                    logger.error("❌ SESSION_STRING environment variable not set!")
                    logger.error("For Docker/cloud deployment, you must provide a valid SESSION_STRING")
                    logger.error("Generate one locally first using the userbot.py test function")
                    raise ValueError("SESSION_STRING required for cloud deployment but not found")
                session = StringSession(session_str)
            else:
                session = self.session_path
            
            # Initialize client
            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash,
                device_model="AI618 Bot",
                system_version="1.0",
                app_version="1.0"
            )
            
            logger.info("Connecting to Telegram...")
            
            # Connect to Telegram
            await self.client.connect()
            
            # Check if already authorized
            if not await self.client.is_user_authorized():
                # In Docker/cloud environment with string session, fail immediately
                if self.use_string_session or self.session_string:
                    logger.error("❌ Session not authorized! SESSION_STRING is invalid or expired.")
                    logger.error("Please generate a new session string locally and update SESSION_STRING environment variable")
                    raise RuntimeError("Invalid or expired SESSION_STRING - cannot authenticate interactively in Docker")
                else:
                    logger.info("User not authorized, starting authentication flow...")
                    await self._authenticate(force_sms)
            else:
                logger.info("✅ Session valid, user already authorized")
            
            # Get user info
            me = await self.client.get_me()
            logger.info(f"✅ Logged in as: {me.first_name} (@{me.username or 'no_username'}) [ID: {me.id}]")
            
            self._connected = True
            
            # Save string session if using it and it's a new session
            if (self.use_string_session or self.session_string) and isinstance(session, StringSession):
                session_string = session.save()
                logger.info(f"String session saved (length: {len(session_string)})")
                logger.info("Save this to SESSION_STRING env var for future use:")
                logger.info(f"SESSION_STRING={session_string}")
            
            return self.client
            
        except errors.ApiIdInvalidError:
            logger.error("❌ Invalid API_ID or API_HASH")
            raise ValueError("Invalid API_ID or API_HASH. Get them from https://my.telegram.org")
        
        except errors.PhoneNumberInvalidError:
            logger.error("❌ Invalid phone number format")
            raise ValueError(f"Invalid phone number: {self.phone_number}. Use international format like +1234567890")
        
        except errors.FloodWaitError as e:
            logger.error(f"❌ Flood wait: Need to wait {e.seconds} seconds")
            raise RuntimeError(f"Telegram flood control: wait {e.seconds} seconds before retry")
        
        except errors.NetworkMigrateError as e:
            logger.error(f"❌ Network migration required to DC {e.new_dc}")
            raise RuntimeError("Network migration needed, will retry...")
        
        except Exception as e:
            logger.error(f"❌ Failed to start userbot: {e}", exc_info=True)
            raise RuntimeError(f"Userbot startup failed: {e}")
    
    async def _authenticate(self, force_sms: bool = False):
        """
        Handle phone number authentication with interactive input.
        
        Args:
            force_sms: Force SMS code delivery
        """
        try:
            # Send code request
            logger.info(f"Sending authentication code to {self._mask_phone(self.phone_number)}...")
            await self.client.send_code_request(self.phone_number, force_sms=force_sms)
            
            # Request code from user
            print("\n" + "="*60)
            print("🔐 TELEGRAM AUTHENTICATION REQUIRED")
            print("="*60)
            print(f"Phone: {self.phone_number}")
            print(f"Code sent via: {'SMS' if force_sms else 'Telegram app'}")
            print("="*60)
            
            code = input("Enter the code you received: ").strip()
            
            try:
                # Sign in with code
                await self.client.sign_in(self.phone_number, code)
                logger.info("✅ Successfully authenticated with code")
                
            except errors.SessionPasswordNeededError:
                # 2FA is enabled
                logger.info("🔒 Two-factor authentication (2FA) is enabled")
                print("\n" + "="*60)
                print("🔒 TWO-FACTOR AUTHENTICATION")
                print("="*60)
                
                password = input("Enter your 2FA password: ").strip()
                await self.client.sign_in(password=password)
                logger.info("✅ Successfully authenticated with 2FA")
            
            except errors.PhoneCodeInvalidError:
                logger.error("❌ Invalid code entered")
                raise ValueError("Invalid authentication code")
            
            except errors.PhoneCodeExpiredError:
                logger.error("❌ Code expired")
                raise ValueError("Authentication code expired, please retry")
        
        except Exception as e:
            logger.error(f"Authentication failed: {e}", exc_info=True)
            raise
    
    async def disconnect(self):
        """Gracefully disconnect the client"""
        if self.client and self._connected:
            try:
                logger.info("Disconnecting Telethon client...")
                await self.client.disconnect()
                self._connected = False
                logger.info("✅ Client disconnected successfully")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}", exc_info=True)
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected and self.client and self.client.is_connected()
    
    async def ensure_connected(self):
        """Ensure client is connected, reconnect if needed"""
        if not self.is_connected():
            logger.warning("Client disconnected, attempting to reconnect...")
            try:
                if self.client:
                    await self.client.connect()
                    self._connected = True
                    logger.info("✅ Reconnected successfully")
                else:
                    logger.error("Client not initialized, cannot reconnect")
                    raise RuntimeError("Client not initialized")
            except Exception as e:
                logger.error(f"Reconnection failed: {e}", exc_info=True)
                raise
    
    async def handle_disconnect(self):
        """Handle disconnect events with automatic reconnection"""
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Disconnect detected, attempting reconnection (attempt {attempt + 1}/{max_retries})...")
                await self.ensure_connected()
                return True
            except errors.FloodWaitError as e:
                logger.warning(f"Flood wait: sleeping for {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error("Max reconnection attempts reached")
                    return False
        
        return False


def create_userbot_from_env(
    session_path: Optional[str] = None,
    use_string_session: bool = False
) -> UserbotClient:
    """
    Create UserbotClient from environment variables.
    
    Expected environment variables:
    - API_ID: Telegram API ID
    - API_HASH: Telegram API hash
    - PHONE_NUMBER: Phone number in international format
    - SESSION_PATH (optional): Custom session file path
    - SESSION_STRING (optional): String session for cloud deployment
    
    Args:
        session_path: Override session path from env
        use_string_session: Use string session instead of file
        
    Returns:
        Configured UserbotClient instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Get credentials from environment
    api_id = os.environ.get('API_ID')
    api_hash = os.environ.get('API_HASH')
    phone_number = os.environ.get('PHONE_NUMBER')
    session_string = os.environ.get('SESSION_STRING')
    
    # Validate required credentials
    if not api_id:
        raise ValueError("API_ID environment variable not set")
    if not api_hash:
        raise ValueError("API_HASH environment variable not set")
    if not phone_number:
        raise ValueError("PHONE_NUMBER environment variable not set")
    
    # Get optional session path
    if session_path is None:
        session_path = os.environ.get('SESSION_PATH', 'userbot_session')
    
    # Convert API_ID to int
    try:
        api_id = int(api_id)
    except ValueError:
        raise ValueError(f"Invalid API_ID: {api_id}. Must be a number.")
    
    # Auto-detect if we should use string session (if SESSION_STRING is provided)
    if session_string:
        use_string_session = True
    
    # Create and return userbot client
    return UserbotClient(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        session_path=session_path,
        use_string_session=use_string_session,
        session_string=session_string
    )


async def test_userbot():
    """Test function to verify userbot setup"""
    import asyncio
    
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    try:
        # Create userbot from environment
        userbot = create_userbot_from_env()
        
        # Start and authenticate
        client = await userbot.start()
        
        # Get current user
        me = await client.get_me()
        print(f"\n✅ Successfully connected as: {me.first_name}")
        print(f"   Username: @{me.username or 'no_username'}")
        print(f"   User ID: {me.id}")
        print(f"   Phone: {me.phone}")
        
        # Test getting dialogs
        print("\n📱 Your recent chats:")
        async for dialog in client.iter_dialogs(limit=5):
            print(f"   - {dialog.name}")
        
        # Disconnect
        await userbot.disconnect()
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    """Run test if executed directly"""
    import asyncio
    asyncio.run(test_userbot())
