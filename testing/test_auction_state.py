import pytest
from datetime import datetime, timedelta
import time
from test_api import ApiClient, SELLER1, BUYER1, get_unique_auction_id


@pytest.fixture
def client():
    return ApiClient()


@pytest.fixture
def auction_id():
    return get_unique_auction_id()


def create_auction(client, auction_id, starts_at, ends_at):
    auction_request = {
        "id": auction_id,
        "startsAt": starts_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "endsAt": ends_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "title": "Time test auction",
        "currency": "VAC",
    }
    response = client.post("/auctions", auction_request, SELLER1)
    assert response.status_code == 200
    return response.json()


def place_bid(client, auction_id, amount=10):
    return client.post(f"/auctions/{auction_id}/bids", {"amount": amount}, BUYER1)


class TestAuctionState:
    def test_wont_end_just_after_start(self, client, auction_id):
        """
        Haskell:
        it "wont end just after start" $
          let state = S.inc (addUTCTime (toEnum 1) sampleStartsAt) baseState
          in S.hasEnded state `shouldBe` False
        """
        # startsAt = now - 2s (to be safe)
        now = datetime.utcnow()
        starts_at = now - timedelta(seconds=2)
        ends_at = now + timedelta(hours=1)

        create_auction(client, auction_id, starts_at, ends_at)

        # Try to place a bid
        response = place_bid(client, auction_id)

        # Should succeed
        assert response.status_code == 200

    def test_wont_end_just_before_end(self, client, auction_id):
        """
        Haskell:
        it "wont end just before end" $
          let state = S.inc (addUTCTime (toEnum (- 1)) sampleEndsAt) baseState
          in S.hasEnded state `shouldBe` False
        """
        # endsAt = now + 5s (give enough time for request)
        now = datetime.utcnow()
        starts_at = now - timedelta(hours=1)
        ends_at = now + timedelta(seconds=5)

        create_auction(client, auction_id, starts_at, ends_at)

        response = place_bid(client, auction_id)

        # Should succeed
        assert response.status_code == 200

    def test_wont_end_just_before_start(self, client, auction_id):
        """
        Haskell:
        it "wont end just before start" $
          let state = S.inc (addUTCTime (toEnum (- 1)) sampleStartsAt) baseState
          in S.hasEnded state `shouldBe` False
        """
        # startsAt = now + 5s
        now = datetime.utcnow()
        starts_at = now + timedelta(seconds=5)
        ends_at = now + timedelta(hours=1)

        create_auction(client, auction_id, starts_at, ends_at)

        response = place_bid(client, auction_id)

        # It should fail because it hasn't started, but NOT because it has ended.
        # We expect an error, but we want to verify it's NOT "AuctionHasEnded".
        if response.status_code != 200:
            assert "AuctionHasEnded" not in response.text
        else:
            # If it succeeds, that's weird for an auction not started, but definitely not ended.
            pass

    def test_will_have_ended_just_after_end(self, client, auction_id):
        """
        Haskell:
        it "will have ended just after end" $
          let state = S.inc (addUTCTime (toEnum 1) sampleEndsAt) baseState
          in S.hasEnded state `shouldBe` True
        """
        # endsAt = now - 2s
        now = datetime.utcnow()
        starts_at = now - timedelta(hours=1)
        ends_at = now - timedelta(seconds=2)

        create_auction(client, auction_id, starts_at, ends_at)

        response = place_bid(client, auction_id)

        # Should fail with AuctionHasEnded
        assert response.status_code == 400
        assert "AuctionHasEnded" in response.text
