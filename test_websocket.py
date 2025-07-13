#!/usr/bin/env python3
"""
Simple WebSocket test script to verify connectivity
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to the backend"""
    uri = "ws://localhost:8000/ws/market"
    
    try:
        logger.info(f"Attempting to connect to {uri}")
        async with websockets.connect(uri) as websocket:
            logger.info("Connected successfully!")
            
            # Wait for initial message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                logger.info(f"Received initial message: {data}")
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for initial message")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {e}")
            
            # Wait for another message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=35)
                data = json.loads(message)
                logger.info(f"Received update message: {data}")
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for update message")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse update message: {e}")
                
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Connection closed: {e}")
    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection()) 