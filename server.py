# HTTP server with explicit reliability scenarios
# Three possible scenarios:
# 1. Normal case (90%): Returns 200 with ~120ms response time
# 2. Intermittent error (5%): Returns 503 Service Unavailable
# 3. Unexpected delay (5%): Returns 200 after 30-second delay

from fastapi import FastAPI, HTTPException
import uvicorn
import random
import asyncio
import logging
from enum import Enum
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Resilient HTTP Server")

class ResponseScenario(Enum):
    NORMAL = "normal"
    INTERMITTENT_ERROR = "intermittent_error"
    UNEXPECTED_DELAY = "unexpected_delay"
    ERROR = "error"

def determine_scenario() -> ResponseScenario:
    INTERMITTENT_ERROR_PROBABILITY = 0.10
    UNEXPECTED_DELAY_PROBABILITY = 0.05
    ERROR_RATE = 0.05

    """Determine which scenario to execute based on probabilities."""
    value = random.random()
    if value < INTERMITTENT_ERROR_PROBABILITY:
        return ResponseScenario.INTERMITTENT_ERROR
    elif value < INTERMITTENT_ERROR_PROBABILITY + UNEXPECTED_DELAY_PROBABILITY:
        return ResponseScenario.UNEXPECTED_DELAY
    elif value < INTERMITTENT_ERROR_PROBABILITY + UNEXPECTED_DELAY_PROBABILITY + ERROR_RATE:
        return ResponseScenario.ERROR
    return ResponseScenario.NORMAL

@app.get("/")
async def root() -> Dict[str, Any]:
    scenario = determine_scenario()
    logger.info(f"Handling request with scenario: {scenario.value}")
    
    if scenario == ResponseScenario.INTERMITTENT_ERROR:
        logger.info("Returning 503 Service Unavailable")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        )
    
    elif scenario == ResponseScenario.UNEXPECTED_DELAY:
        logger.info("Starting 10-second delay")
        await asyncio.sleep(10)
        logger.info("Completed 10-second delay")
        return {
            "scenario": scenario.value,
            "message": "Hello, World!",
            "delay_seconds": 10
        }
    
    elif scenario == ResponseScenario.ERROR:
        logger.info("Returning 500 Internal Server Error")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
    
    else:  # NORMAL
        delay = random.expovariate(1/0.12)  # Mean = 120ms
        logger.info(f"Normal response with delay: {delay:.3f}s")
        await asyncio.sleep(delay)
        return {
            "scenario": scenario.value,
            "message": "Hello, World!",
            "response_time_ms": round(delay * 1000, 2)
        }

if __name__ == "__main__":
    logger.info("Starting server with scenarios:")
    logger.info(f"1. Normal case (90%):")
    logger.info(f"   - Returns 200 OK")
    logger.info(f"   - Average response time: 120ms")
    logger.info(f"2. Intermittent error (10%):")
    logger.info(f"   - Returns 503 Service Unavailable")
    logger.info(f"3. Unexpected delay (5%):")
    logger.info(f"   - Returns 200 OK")
    logger.info(f"   - 30-second delay before response")
    logger.info(f"4. Error (5%):")
    logger.info(f"   - Returns 500 Internal Server Error")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)


