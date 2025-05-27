# calls the endpoint on localhost:8080 in a loop of parametrized size
# but such that: 
# - intermittent errors are retried (the HTTP 503s)
# - calls that are tool slow are ALSO retried
# - statistics are collected:
#   - total calls
#   - total errors
#   - total success
#   - total time taken
#   - average time taken

import requests
import time
import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass
from statistics import mean, stdev
import numpy as np
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class TimeoutStrategy(Enum):
    AGGRESSIVE = "aggressive"  # 300ms timeout
    PATIENT = "patient"        # 35s timeout

@dataclass
class CallStats:
    total_calls: int = 0
    total_errors: int = 0
    total_success: int = 0
    total_time: float = 0.0
    response_times: list[float] = None
    timeout_strategy: TimeoutStrategy = None

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []

    @property
    def average_time(self) -> float:
        return mean(self.response_times) if self.response_times else 0.0
    
    @property
    def stddev_time(self) -> float:
        return stdev(self.response_times) if len(self.response_times) > 1 else 0.0
    
    @property
    def percentile_95(self) -> float:
        return np.percentile(self.response_times, 95) if self.response_times else 0.0

def make_resilient_call(
    url: str,
    max_retries: int = 3,
    timeout_strategy: TimeoutStrategy = TimeoutStrategy.AGGRESSIVE
) -> tuple[Dict[str, Any], CallStats]:
    stats = CallStats(timeout_strategy=timeout_strategy)
    
    # Set timeout based on strategy
    timeout = 0.3 if timeout_strategy == TimeoutStrategy.AGGRESSIVE else 35.0
    
    for attempt in range(max_retries):
        start_time = time.time()
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} - Making request to {url} (timeout: {timeout}s)")
            response = requests.get(url, timeout=timeout)

            # decide whether timeout was hit or response was success
            scenario = "failure"
            if response.status_code == 200:
                scenario = "success"
            elif response.status_code == 503:
                scenario = "intermittent_error"
            elif response.elapsed.total_seconds() > timeout:
                scenario = "slow"
            elif response.status_code == 500:
                scenario = "error"

            elapsed_time = time.time() - start_time            
            stats.total_calls += 1
            stats.response_times.append(elapsed_time)
            stats.total_time += elapsed_time
                        
            if scenario == "intermittent_error" or scenario == "slow":
                stats.total_errors += 1
                if attempt < max_retries - 1:
                    logger.warning(f"Retrying due to {scenario}")
                    continue
            elif scenario == "error":
                # No retries for errors
                stats.total_errors += 1
                return {"error": "Internal Server Error"}, stats
            else: 
                stats.total_success += 1
                return response.json(), stats
            
        except (requests.RequestException, ValueError) as e:
            stats.total_errors += 1
            logger.error(f"Request failed: {str(e)}")
            if attempt == max_retries - 1:
                return {"error": str(e)}, stats
    
    return {"error": "Max retries exceeded"}, stats

def run_test(num_calls: int, timeout_strategy: TimeoutStrategy) -> CallStats:
    url = "http://localhost:8080"
    all_stats = CallStats(timeout_strategy=timeout_strategy)
    
    logger.info(f"\nStarting {num_calls} calls to {url} with {timeout_strategy.value} strategy")
    
    for i in range(num_calls):
        logger.info(f"\nCall {i + 1}/{num_calls}")
        _, call_stats = make_resilient_call(url, timeout_strategy=timeout_strategy)
        all_stats.total_calls += call_stats.total_calls
        all_stats.total_errors += call_stats.total_errors
        all_stats.total_success += call_stats.total_success
        all_stats.total_time += call_stats.total_time
        all_stats.response_times.extend(call_stats.response_times)
    
    return all_stats

def print_statistics(stats: CallStats):
    logger.info(f"\nStatistics for {stats.timeout_strategy.value} strategy:")
    logger.info(f"Total calls: {stats.total_calls}")
    logger.info(f"Total errors: {stats.total_errors}")
    logger.info(f"Total success: {stats.total_success}")
    logger.info(f"Total time: {stats.total_time:.2f}s")
    logger.info(f"Average time: {stats.average_time:.3f}s")
    logger.info(f"Standard deviation: {stats.stddev_time:.3f}s")
    logger.info(f"95th percentile: {stats.percentile_95:.3f}s")
    
    if stats.response_times:
        logger.info("\nResponse Time Distribution:")
        logger.info(f"Min: {min(stats.response_times):.3f}s")
        logger.info(f"Max: {max(stats.response_times):.3f}s")
        logger.info(f"Median: {np.median(stats.response_times):.3f}s")
        logger.info(f"75th percentile: {np.percentile(stats.response_times, 75):.3f}s")
        logger.info(f"99th percentile: {np.percentile(stats.response_times, 99):.3f}s")

def main(num_calls: int = 100):
    # Run both strategies
    aggressive_stats = run_test(num_calls, TimeoutStrategy.AGGRESSIVE)
    patient_stats = run_test(num_calls, TimeoutStrategy.PATIENT)
    
    # Print comparison
    logger.info("\n=== COMPARISON OF STRATEGIES ===")
    print_statistics(aggressive_stats)
    print_statistics(patient_stats)
    
    # Calculate and print differences
    logger.info("\n=== KEY DIFFERENCES ===")
    logger.info(f"Total time difference: {patient_stats.total_time - aggressive_stats.total_time:.2f}s")
    logger.info(f"Success rate difference: {(patient_stats.total_success/patient_stats.total_calls - aggressive_stats.total_success/aggressive_stats.total_calls)*100:.1f}%")
    logger.info(f"Average response time difference: {patient_stats.average_time - aggressive_stats.average_time:.3f}s")

if __name__ == "__main__":
    main()

