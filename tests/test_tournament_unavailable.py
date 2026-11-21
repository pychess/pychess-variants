from datetime import UTC, datetime, timedelta

from const import T_FINISHED
from pychess_global_app_state_utils import get_app_state
from tournament.arena import ArenaTournament
from tournament.rr import RRTournament
from tournament.tournament import upsert_tournament_to_db
from tournament_test_base import TournamentTestCase


class UnavailableTournamentTestCase(TournamentTestCase):
    async def test_missing_tournament_returns_404(self):
        response = await self.client.get("/tournament/HxahGu74")

        self.assertEqual(response.status, 404)
        html = await response.text()
        self.assertIn("<h1>404</h1>", html)
        self.assertIn("Page not found.", html)
        self.assertNotIn('id="placeholder"', html)

    async def test_deleted_variant_without_snapshot_returns_404(self):
        app_state = get_app_state(self.app)
        await app_state.db.tournament.insert_one(
            {"_id": "orphan01", "v": "deleted_catalogued_variant"}
        )

        response = await self.client.get("/tournament/orphan01")

        self.assertEqual(response.status, 404)
        html = await response.text()
        self.assertIn("<h1>404</h1>", html)
        self.assertIn("Page not found.", html)
        self.assertNotIn('id="placeholder"', html)

    async def test_deletion_removes_only_the_deleted_tournaments_calendar_link(self):
        app_state = get_app_state(self.app)
        start = datetime.now(UTC)
        for action in ("finish", "destroy", "save", "destroy_empty_finished_rr"):
            with self.subTest(action=action):
                tournament_class = (
                    RRTournament if action == "destroy_empty_finished_rr" else ArenaTournament
                )
                tournament = tournament_class(
                    app_state, "deleted1", status=T_FINISHED, with_clock=False
                )
                app_state.tournaments[tournament.id] = tournament
                await upsert_tournament_to_db(tournament, app_state)
                app_state.tourney_calendar = [
                    {
                        "title": "chess",
                        "start": start,
                        "end": start + timedelta(minutes=30),
                        "classNames": "d",
                        "url": "/tournament/deleted1",
                    },
                    {
                        "title": "chess",
                        "start": start + timedelta(days=1),
                        "end": start + timedelta(days=1, minutes=30),
                        "classNames": "d",
                        "url": "/tournament/retained",
                    },
                ]

                await getattr(tournament, action)()

                self.assertIsNone(await app_state.db.tournament.find_one({"_id": tournament.id}))
                response = await self.client.get("/api/calendar")
                self.assertEqual(response.status, 200)
                events = await response.json()
                self.assertEqual(len(events), 2)
                self.assertNotIn("url", events[0])
                self.assertEqual(events[0]["borderColor"], "gray")
                self.assertEqual(events[1]["url"], "/tournament/retained")

                # The empty-tournament save path retains its in-memory object until
                # normal cache eviction. An old calendar tab must be safe afterward.
                app_state.tournaments.pop(tournament.id, None)
                response = await self.client.get("/tournament/deleted1")
                self.assertEqual(response.status, 404)
