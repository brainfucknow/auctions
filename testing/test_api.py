#!/usr/bin/env python3
"""
Python port of ApiSpec.hs
API tests for the auction site using pytest and requests.
"""

import json
import os
import pytest
import requests
from typing import Optional
import time


# Configuration
BASE_URL = os.environ.get("URL", "http://127.0.0.1:8080")
SELLER1 = "eyJzdWIiOiJhMSIsICJuYW1lIjoiVGVzdCIsICJ1X3R5cCI6IjAifQo="
BUYER1 = "eyJzdWIiOiJhMiIsICJuYW1lIjoiQnV5ZXIiLCAidV90eXAiOiIwIn0K"

# Counter for unique auction IDs
_auction_id_counter = int(time.time() * 1000) % 1000000


class ApiClient:
    """Helper class for making API requests with authentication."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def get(self, path: str, jwt_payload: Optional[str] = None) -> requests.Response:
        """Make GET request with optional JWT header."""
        headers = {}
        if jwt_payload:
            headers["x-jwt-payload"] = jwt_payload
        return self.session.get(f"{self.base_url}{path}", headers=headers)

    def post(self, path: str, data: dict, jwt_payload: Optional[str] = None) -> requests.Response:
        """Make POST request with JSON data and optional JWT header."""
        headers = {"Content-Type": "application/json"}
        if jwt_payload:
            headers["x-jwt-payload"] = jwt_payload
        return self.session.post(
            f"{self.base_url}{path}",
            json=data,
            headers=headers
        )


def get_unique_auction_id():
    """Generate a unique auction ID for each test."""
    global _auction_id_counter
    _auction_id_counter += 1
    return _auction_id_counter


@pytest.fixture
def client():
    """Fixture providing a fresh API client for each test."""
    return ApiClient()


@pytest.fixture
def auction_id():
    """Fixture providing a unique auction ID for each test."""
    return get_unique_auction_id()


# Expected response values (from ApiSpec.hs)
FIRST_AUCTION_REQUEST = {
    "id": 1,
    "startsAt": "2018-01-01T10:00:00.000Z",
    "endsAt": "2019-01-01T10:00:00.000Z",
    "title": "First auction",
    "currency": "VAC"
}

AUCTION_ADDED_EVENT = {
    "$type": "AuctionAdded",
    "at": "2018-08-04T00:00:00Z",
    "auction": {
        "id": 1,
        "startsAt": "2018-01-01T10:00:00Z",
        "title": "First auction",
        "expiry": "2019-01-01T10:00:00Z",
        "user": "BuyerOrSeller|a1|Test",
        "type": "English|0|0|0",
        "currency": "VAC"
    }
}

BID_ACCEPTED_EVENT = {
    "$type": "BidAccepted",
    "at": "2018-08-04T00:00:00Z",
    "bid": {
        "auction": 1,
        "user": "BuyerOrSeller|a2|Buyer",
        "amount": 11,
        "at": "2018-08-04T00:00:00Z"
    }
}

AUCTION_WITHOUT_BIDS = {
    "currency": "VAC",
    "expiry": "2019-01-01T10:00:00Z",
    "id": 1,
    "startsAt": "2018-01-01T10:00:00Z",
    "title": "First auction",
    "bids": [],
    "winner": None,
    "winnerPrice": None
}

AUCTION_WITH_BID = {
    "currency": "VAC",
    "expiry": "2019-01-01T10:00:00Z",
    "id": 1,
    "startsAt": "2018-01-01T10:00:00Z",
    "title": "First auction",
    "bids": [
        {
            "amount": 11,
            "bidder": "BuyerOrSeller|a2|Buyer"
        }
    ],
    "winner": None,
    "winnerPrice": None
}


class TestAddAuction:
    """Test suite for adding auctions (POST /auctions)."""

    def test_possible_to_add_auction(self, client, auction_id):
        """Test that it's possible to add an auction."""
        auction_request = {**FIRST_AUCTION_REQUEST, "id": auction_id}
        response = client.post("/auctions", auction_request, SELLER1)
        assert response.status_code == 200

        # Verify response structure (timestamps may vary)
        data = response.json()
        assert data["$type"] == "AuctionAdded"
        assert "at" in data  # Timestamp exists but value may vary
        assert data["auction"]["id"] == auction_id
        assert data["auction"]["title"] == "First auction"

    def test_not_possible_to_add_same_auction_twice(self, client, auction_id):
        """Test that adding the same auction twice fails."""
        auction_request = {**FIRST_AUCTION_REQUEST, "id": auction_id}

        # First auction should succeed
        response1 = client.post("/auctions", auction_request, SELLER1)
        assert response1.status_code == 200

        # Second attempt should fail with 400
        response2 = client.post("/auctions", auction_request, SELLER1)
        assert response2.status_code == 400
        assert response2.json() == f"AuctionAlreadyExists {auction_id}"

    def test_returns_added_auction(self, client, auction_id):
        """Test that GET /auctions/:id returns the added auction."""
        auction_request = {**FIRST_AUCTION_REQUEST, "id": auction_id}

        # Add auction
        response = client.post("/auctions", auction_request, SELLER1)
        assert response.status_code == 200

        # Retrieve it
        get_response = client.get(f"/auctions/{auction_id}")
        assert get_response.status_code == 200

        auction_data = get_response.json()
        assert auction_data["id"] == auction_id
        assert auction_data["title"] == "First auction"
        assert auction_data["bids"] == []
        assert auction_data["winner"] is None

    def test_returns_added_auctions_list(self, client, auction_id):
        """Test that GET /auctions returns list with the added auction."""
        auction_request = {**FIRST_AUCTION_REQUEST, "id": auction_id}

        # Add auction
        response = client.post("/auctions", auction_request, SELLER1)
        assert response.status_code == 200

        # Get list
        list_response = client.get("/auctions")
        assert list_response.status_code == 200
        auctions = list_response.json()
        assert isinstance(auctions, list)
        assert len(auctions) >= 1

        # Find our auction in the list
        our_auction = next((a for a in auctions if a["id"] == auction_id), None)
        assert our_auction is not None
        assert our_auction["title"] == "First auction"
        assert our_auction["currency"] == "VAC"


class TestAddBids:
    """Test suite for adding bids to auctions (POST /auctions/:id/bids)."""

    def test_possible_to_add_bid_to_auction(self, client, auction_id):
        """Test that it's possible to add a bid to an auction."""
        auction_request = {**FIRST_AUCTION_REQUEST, "id": auction_id}

        # First add auction
        auction_response = client.post("/auctions", auction_request, SELLER1)
        assert auction_response.status_code == 200

        # Then add bid
        bid_response = client.post(
            f"/auctions/{auction_id}/bids",
            {"amount": 11},
            BUYER1
        )
        assert bid_response.status_code == 200

        # Verify bid response structure (timestamps may vary)
        bid_data = bid_response.json()
        assert bid_data["$type"] == "BidAccepted"
        assert "at" in bid_data
        assert bid_data["bid"]["auction"] == auction_id
        assert bid_data["bid"]["amount"] == 11

    def test_possible_to_see_the_added_bids(self, client, auction_id):
        """Test that bids appear when retrieving the auction."""
        auction_request = {**FIRST_AUCTION_REQUEST, "id": auction_id}

        # Add auction
        auction_response = client.post("/auctions", auction_request, SELLER1)
        assert auction_response.status_code == 200

        # Add bid
        bid_response = client.post(
            f"/auctions/{auction_id}/bids",
            {"amount": 11},
            BUYER1
        )
        assert bid_response.status_code == 200

        # Get auction and verify bid is present
        get_response = client.get(f"/auctions/{auction_id}")
        assert get_response.status_code == 200

        auction_data = get_response.json()
        assert auction_data["id"] == auction_id
        assert len(auction_data["bids"]) == 1
        assert auction_data["bids"][0]["amount"] == 11
        assert "BuyerOrSeller|a2|Buyer" in auction_data["bids"][0]["bidder"]

    def test_not_possible_to_add_bid_to_non_existent_auction(self, client, auction_id):
        """Test that adding a bid to a non-existent auction fails with 400."""
        # Use a very high ID that definitely doesn't exist
        non_existent_id = auction_id + 999999

        response = client.post(
            f"/auctions/{non_existent_id}/bids",
            {"amount": 10},
            BUYER1
        )
        assert response.status_code == 400
        assert "UnknownAuction" in response.text


if __name__ == "__main__":
    # Allow running tests directly with: python test_api.py
    pytest.main([__file__, "-v"])
