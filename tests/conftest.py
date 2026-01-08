"""
Pytest configuration and fixtures.
"""

import pytest
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_constituents():
    """Sample constituents for testing."""
    return [
        {"card_id": "card-001", "name": "Charizard", "price": 500, "liquidity_score": 0.9, "weight": 0.4},
        {"card_id": "card-002", "name": "Pikachu", "price": 100, "liquidity_score": 0.8, "weight": 0.3},
        {"card_id": "card-003", "name": "Mewtwo", "price": 200, "liquidity_score": 0.7, "weight": 0.3},
    ]


@pytest.fixture
def sample_prices():
    """Sample price data for testing."""
    return {
        "card-001": 500.0,
        "card-002": 100.0,
        "card-003": 200.0,
    }
