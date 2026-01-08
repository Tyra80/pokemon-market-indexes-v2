"""
Tests for critical calculation functions.

Run with: pytest tests/ -v
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    CONDITION_WEIGHTS, LIQUIDITY_CAP, VOLUME_CAP,
    LIQUIDITY_WEIGHTS, MIN_AVG_VOLUME_30D
)


# =============================================================================
# TEST: Laspeyres Formula
# =============================================================================

class TestLaspeyresFormula:
    """Tests for the Laspeyres chain-linking calculation."""

    def calculate_laspeyres(self, prev_value: float, constituents: list,
                            prev_prices: dict, current_prices: dict) -> float:
        """
        Simplified Laspeyres calculation for testing.

        Formula: Index_t = Index_{t-1} × [Σ(w_i × P_i,t) / Σ(w_i × P_i,t-1)]
        """
        numerator = 0.0
        denominator = 0.0

        for c in constituents:
            card_id = c["card_id"]
            weight = c["weight"]

            if card_id in current_prices and card_id in prev_prices:
                prev_price = prev_prices[card_id]
                current_price = current_prices[card_id]

                if prev_price > 0:
                    numerator += weight * current_price
                    denominator += weight * prev_price

        if denominator == 0:
            return prev_value

        ratio = numerator / denominator
        return round(prev_value * ratio, 4)

    def test_no_change(self):
        """Index should stay the same if prices don't change."""
        prev_value = 100.0
        constituents = [
            {"card_id": "A", "weight": 0.5},
            {"card_id": "B", "weight": 0.5},
        ]
        prev_prices = {"A": 10.0, "B": 20.0}
        current_prices = {"A": 10.0, "B": 20.0}

        result = self.calculate_laspeyres(prev_value, constituents, prev_prices, current_prices)
        assert result == 100.0

    def test_all_prices_double(self):
        """Index should double if all prices double."""
        prev_value = 100.0
        constituents = [
            {"card_id": "A", "weight": 0.5},
            {"card_id": "B", "weight": 0.5},
        ]
        prev_prices = {"A": 10.0, "B": 20.0}
        current_prices = {"A": 20.0, "B": 40.0}

        result = self.calculate_laspeyres(prev_value, constituents, prev_prices, current_prices)
        assert result == 200.0

    def test_weighted_change(self):
        """Test weighted price changes."""
        prev_value = 100.0
        constituents = [
            {"card_id": "A", "weight": 0.8},  # 80% weight
            {"card_id": "B", "weight": 0.2},  # 20% weight
        ]
        prev_prices = {"A": 100.0, "B": 100.0}
        # A goes up 10%, B goes down 10%
        current_prices = {"A": 110.0, "B": 90.0}

        # Expected: 0.8 * (110/100) + 0.2 * (90/100) = 0.8 * 1.1 + 0.2 * 0.9 = 0.88 + 0.18 = 1.06
        # Index = 100 * 1.06 = 106
        result = self.calculate_laspeyres(prev_value, constituents, prev_prices, current_prices)
        assert result == 106.0

    def test_missing_price_excluded(self):
        """Cards with missing prices should be excluded."""
        prev_value = 100.0
        constituents = [
            {"card_id": "A", "weight": 0.5},
            {"card_id": "B", "weight": 0.5},
        ]
        prev_prices = {"A": 10.0, "B": 20.0}
        current_prices = {"A": 15.0}  # B is missing

        # Only A is used: ratio = 15/10 = 1.5
        result = self.calculate_laspeyres(prev_value, constituents, prev_prices, current_prices)
        assert result == 150.0

    def test_zero_prev_price_excluded(self):
        """Cards with zero previous price should be excluded."""
        prev_value = 100.0
        constituents = [
            {"card_id": "A", "weight": 0.5},
            {"card_id": "B", "weight": 0.5},
        ]
        prev_prices = {"A": 10.0, "B": 0.0}
        current_prices = {"A": 12.0, "B": 5.0}

        # Only A is used: ratio = 12/10 = 1.2
        result = self.calculate_laspeyres(prev_value, constituents, prev_prices, current_prices)
        assert result == 120.0


# =============================================================================
# TEST: Weight Calculation
# =============================================================================

class TestWeightCalculation:
    """Tests for liquidity-adjusted price-weighted calculation."""

    def calculate_weights(self, constituents: list) -> list:
        """
        Calculate weights: weight_i = (price_i × liquidity_i) / Σ(price × liquidity)
        """
        for c in constituents:
            liquidity = c.get("liquidity_score", 0) or 0.1
            c["adjusted_value"] = c.get("price", 0) * liquidity

        total_adjusted = sum(c.get("adjusted_value", 0) for c in constituents)

        if total_adjusted == 0:
            equal_weight = 1.0 / len(constituents) if constituents else 0
            for c in constituents:
                c["weight"] = equal_weight
            return constituents

        for c in constituents:
            c["weight"] = c.get("adjusted_value", 0) / total_adjusted

        return constituents

    def test_equal_price_and_liquidity(self):
        """Equal price and liquidity should give equal weights."""
        constituents = [
            {"card_id": "A", "price": 100, "liquidity_score": 0.5},
            {"card_id": "B", "price": 100, "liquidity_score": 0.5},
        ]

        result = self.calculate_weights(constituents)

        assert result[0]["weight"] == pytest.approx(0.5)
        assert result[1]["weight"] == pytest.approx(0.5)

    def test_higher_price_higher_weight(self):
        """Higher price should give higher weight (same liquidity)."""
        constituents = [
            {"card_id": "A", "price": 200, "liquidity_score": 0.5},
            {"card_id": "B", "price": 100, "liquidity_score": 0.5},
        ]

        result = self.calculate_weights(constituents)

        # A: 200*0.5=100, B: 100*0.5=50, Total=150
        # A weight = 100/150 = 0.6667, B weight = 50/150 = 0.3333
        assert result[0]["weight"] == pytest.approx(0.6667, rel=0.01)
        assert result[1]["weight"] == pytest.approx(0.3333, rel=0.01)

    def test_higher_liquidity_higher_weight(self):
        """Higher liquidity should give higher weight (same price)."""
        constituents = [
            {"card_id": "A", "price": 100, "liquidity_score": 0.8},
            {"card_id": "B", "price": 100, "liquidity_score": 0.2},
        ]

        result = self.calculate_weights(constituents)

        # A: 100*0.8=80, B: 100*0.2=20, Total=100
        # A weight = 80/100 = 0.8, B weight = 20/100 = 0.2
        assert result[0]["weight"] == pytest.approx(0.8)
        assert result[1]["weight"] == pytest.approx(0.2)

    def test_weights_sum_to_one(self):
        """All weights should sum to 1.0."""
        constituents = [
            {"card_id": "A", "price": 150, "liquidity_score": 0.7},
            {"card_id": "B", "price": 80, "liquidity_score": 0.3},
            {"card_id": "C", "price": 200, "liquidity_score": 0.9},
        ]

        result = self.calculate_weights(constituents)
        total_weight = sum(c["weight"] for c in result)

        assert total_weight == pytest.approx(1.0)

    def test_zero_liquidity_uses_floor(self):
        """Zero liquidity should use floor of 0.1."""
        constituents = [
            {"card_id": "A", "price": 100, "liquidity_score": 0},
            {"card_id": "B", "price": 100, "liquidity_score": 0.5},
        ]

        result = self.calculate_weights(constituents)

        # A: 100*0.1=10 (floor), B: 100*0.5=50, Total=60
        # A weight = 10/60 = 0.1667, B weight = 50/60 = 0.8333
        assert result[0]["weight"] == pytest.approx(0.1667, rel=0.01)
        assert result[1]["weight"] == pytest.approx(0.8333, rel=0.01)


# =============================================================================
# TEST: Liquidity Score Calculation
# =============================================================================

class TestLiquidityScore:
    """Tests for the 50/30/20 liquidity formula."""

    def calculate_liquidity_smart(self, avg_volume: float, weighted_listings: float,
                                   consistency: float) -> float:
        """
        Calculate liquidity score: 50% Volume + 30% Listings + 20% Consistency
        """
        W_VOL = LIQUIDITY_WEIGHTS.get("volume", 0.50)
        W_LIST = LIQUIDITY_WEIGHTS.get("listings", 0.30)
        W_CONS = LIQUIDITY_WEIGHTS.get("consistency", 0.20)

        volume_score = min(avg_volume / VOLUME_CAP, 1.0)
        listings_score = min(weighted_listings / LIQUIDITY_CAP, 1.0)
        consistency_score = consistency  # Already 0-1

        return round(W_VOL * volume_score + W_LIST * listings_score + W_CONS * consistency_score, 4)

    def test_max_liquidity(self):
        """Max volume, listings, and consistency should give score of 1.0."""
        result = self.calculate_liquidity_smart(
            avg_volume=VOLUME_CAP,  # 10
            weighted_listings=LIQUIDITY_CAP,  # 50
            consistency=1.0
        )
        assert result == 1.0

    def test_zero_liquidity(self):
        """Zero everything should give score of 0."""
        result = self.calculate_liquidity_smart(
            avg_volume=0,
            weighted_listings=0,
            consistency=0
        )
        assert result == 0.0

    def test_volume_dominates(self):
        """Volume should be 50% of the score."""
        # Only volume, max value
        result = self.calculate_liquidity_smart(
            avg_volume=VOLUME_CAP,
            weighted_listings=0,
            consistency=0
        )
        assert result == pytest.approx(0.5)

    def test_listings_contribution(self):
        """Listings should be 30% of the score."""
        # Only listings, max value
        result = self.calculate_liquidity_smart(
            avg_volume=0,
            weighted_listings=LIQUIDITY_CAP,
            consistency=0
        )
        assert result == pytest.approx(0.3)

    def test_consistency_contribution(self):
        """Consistency should be 20% of the score."""
        # Only consistency, max value
        result = self.calculate_liquidity_smart(
            avg_volume=0,
            weighted_listings=0,
            consistency=1.0
        )
        assert result == pytest.approx(0.2)

    def test_capped_values(self):
        """Values above cap should be capped at 1.0."""
        result = self.calculate_liquidity_smart(
            avg_volume=100,  # Way above cap of 10
            weighted_listings=500,  # Way above cap of 50
            consistency=1.0
        )
        assert result == 1.0  # Capped


# =============================================================================
# TEST: Ranking Score
# =============================================================================

class TestRankingScore:
    """Tests for ranking_score = price × liquidity."""

    def calculate_ranking_score(self, price: float, liquidity_score: float) -> float:
        return price * liquidity_score

    def test_basic_calculation(self):
        """Basic ranking score calculation."""
        result = self.calculate_ranking_score(100, 0.5)
        assert result == 50.0

    def test_high_price_low_liquidity(self):
        """High price with low liquidity should have moderate score."""
        high_price_low_liq = self.calculate_ranking_score(1000, 0.1)
        low_price_high_liq = self.calculate_ranking_score(200, 0.8)

        # 1000 * 0.1 = 100
        # 200 * 0.8 = 160
        # The liquid card should rank higher
        assert low_price_high_liq > high_price_low_liq

    def test_zero_liquidity(self):
        """Zero liquidity should give zero ranking."""
        result = self.calculate_ranking_score(1000, 0)
        assert result == 0


# =============================================================================
# TEST: Method D Filter
# =============================================================================

class TestMethodDFilter:
    """Tests for the 30-day volume eligibility filter."""

    def is_eligible_method_d(self, avg_volume: float, days_with_volume: int,
                              min_days: int = 10) -> bool:
        """
        Method D eligibility check:
        - avg_volume >= MIN_AVG_VOLUME_30D (0.5)
        - days_with_volume >= min_days (10)
        """
        has_sufficient_volume = avg_volume >= MIN_AVG_VOLUME_30D
        has_regular_trading = days_with_volume >= min_days
        return has_sufficient_volume and has_regular_trading

    def test_eligible_card(self):
        """Card meeting both criteria should be eligible."""
        result = self.is_eligible_method_d(avg_volume=1.0, days_with_volume=15)
        assert result is True

    def test_low_volume(self):
        """Card with low average volume should be ineligible."""
        result = self.is_eligible_method_d(avg_volume=0.3, days_with_volume=15)
        assert result is False

    def test_few_trading_days(self):
        """Card with few trading days should be ineligible."""
        result = self.is_eligible_method_d(avg_volume=1.0, days_with_volume=5)
        assert result is False

    def test_borderline_eligible(self):
        """Card exactly at thresholds should be eligible."""
        result = self.is_eligible_method_d(
            avg_volume=MIN_AVG_VOLUME_30D,  # 0.5
            days_with_volume=10
        )
        assert result is True

    def test_borderline_ineligible(self):
        """Card just below thresholds should be ineligible."""
        result = self.is_eligible_method_d(
            avg_volume=MIN_AVG_VOLUME_30D - 0.01,
            days_with_volume=10
        )
        assert result is False


# =============================================================================
# TEST: Condition Weights
# =============================================================================

class TestConditionWeights:
    """Tests for condition weighting consistency."""

    def calculate_weighted_listings(self, nm: int, lp: int, mp: int, hp: int, dmg: int) -> float:
        """Calculate weighted listings using CONDITION_WEIGHTS."""
        return (
            nm * CONDITION_WEIGHTS["Near Mint"] +
            lp * CONDITION_WEIGHTS["Lightly Played"] +
            mp * CONDITION_WEIGHTS["Moderately Played"] +
            hp * CONDITION_WEIGHTS["Heavily Played"] +
            dmg * CONDITION_WEIGHTS["Damaged"]
        )

    def test_nm_has_full_weight(self):
        """Near Mint should have weight 1.0."""
        assert CONDITION_WEIGHTS["Near Mint"] == 1.0

    def test_weights_decrease_with_condition(self):
        """Weights should decrease as condition worsens."""
        assert CONDITION_WEIGHTS["Near Mint"] > CONDITION_WEIGHTS["Lightly Played"]
        assert CONDITION_WEIGHTS["Lightly Played"] > CONDITION_WEIGHTS["Moderately Played"]
        assert CONDITION_WEIGHTS["Moderately Played"] > CONDITION_WEIGHTS["Heavily Played"]
        assert CONDITION_WEIGHTS["Heavily Played"] > CONDITION_WEIGHTS["Damaged"]

    def test_weighted_calculation(self):
        """Test weighted listings calculation."""
        # 10 NM + 10 LP + 10 MP + 10 HP + 10 DMG
        # = 10*1.0 + 10*0.8 + 10*0.6 + 10*0.4 + 10*0.2
        # = 10 + 8 + 6 + 4 + 2 = 30
        result = self.calculate_weighted_listings(10, 10, 10, 10, 10)
        assert result == 30.0

    def test_only_nm(self):
        """Only NM listings should equal raw count."""
        result = self.calculate_weighted_listings(50, 0, 0, 0, 0)
        assert result == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
