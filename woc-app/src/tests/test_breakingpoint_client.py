from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from src.breakingpoint_client import BreakingPointClient, BreakingPointError, PAGE_SIZE


def make_response(status_code, payload):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def make_client(session):
    return BreakingPointClient(
        base_url='https://example.test',
        api_key='key',
        access_token='token',
        session=session,
    )


class BreakingPointClientCredentialTests(TestCase):
    @override_settings(BREAKINGPOINT_API_KEY=None, BREAKINGPOINT_ACCESS_TOKEN=None)
    def test_missing_credentials_raise(self):
        with self.assertRaises(BreakingPointError):
            BreakingPointClient(base_url='https://example.test', session=MagicMock())

    def test_explicit_credentials_are_used_over_settings(self):
        client = make_client(MagicMock())
        headers = client._headers()

        self.assertEqual(headers['apikey'], 'key')
        self.assertEqual(headers['Authorization'], 'Bearer token')


class BreakingPointClientPaginationTests(TestCase):
    def test_fetch_all_stops_on_short_page(self):
        session = MagicMock()
        session.get.return_value = make_response(200, [{'id': 1}, {'id': 2}])
        client = make_client(session)

        rows = client.fetch_all('widgets', {'select': '*'})

        self.assertEqual(rows, [{'id': 1}, {'id': 2}])
        session.get.assert_called_once()
        self.assertEqual(
            session.get.call_args.kwargs['headers']['Range'],
            f'0-{PAGE_SIZE - 1}',
        )

    def test_fetch_all_paginates_until_short_page(self):
        full_page = [{'id': i} for i in range(PAGE_SIZE)]
        last_page = [{'id': PAGE_SIZE}]
        session = MagicMock()
        session.get.side_effect = [
            make_response(200, full_page),
            make_response(200, last_page),
        ]
        client = make_client(session)

        rows = client.fetch_all('widgets', {'select': '*'})

        self.assertEqual(len(rows), PAGE_SIZE + 1)
        self.assertEqual(session.get.call_count, 2)
        first_range = session.get.call_args_list[0].kwargs['headers']['Range']
        second_range = session.get.call_args_list[1].kwargs['headers']['Range']
        self.assertEqual(first_range, f'0-{PAGE_SIZE - 1}')
        self.assertEqual(second_range, f'{PAGE_SIZE}-{2 * PAGE_SIZE - 1}')

    def test_fetch_all_raises_on_401(self):
        session = MagicMock()
        session.get.return_value = make_response(401, {'message': 'bad token'})
        client = make_client(session)

        with self.assertRaises(BreakingPointError):
            client.fetch_all('widgets', {'select': '*'})


class BreakingPointClientQueryBuildingTests(TestCase):
    def test_fetch_player_stats_builds_expected_params(self):
        session = MagicMock()
        session.get.return_value = make_response(200, [])
        client = make_client(session)

        client.fetch_player_stats(season_id=2026, player_tags=['Huke', 'Simp'])

        params = session.get.call_args.kwargs['params']
        self.assertEqual(params['season_id'], 'eq.2026')
        self.assertEqual(params['player_tag'], 'in.("Huke","Simp")')
        self.assertIn('kills', params['select'])
        self.assertIn('deaths', params['select'])

    def test_fetch_events_returns_empty_without_request_when_no_ids(self):
        session = MagicMock()
        client = make_client(session)

        result = client.fetch_events(set())

        self.assertEqual(result, {})
        session.get.assert_not_called()

    def test_fetch_events_builds_in_filter_and_indexes_by_id(self):
        session = MagicMock()
        session.get.return_value = make_response(
            200,
            [{
                'id': 10,
                'name': 'Major 1',
                'start_date': '2026-01-01',
                'end_date': '2026-02-01',
            }],
        )
        client = make_client(session)

        result = client.fetch_events({10})

        self.assertEqual(
            result,
            {10: {
                'id': 10,
                'name': 'Major 1',
                'start_date': '2026-01-01',
                'end_date': '2026-02-01',
            }},
        )
        self.assertEqual(session.get.call_args.kwargs['params']['id'], 'in.(10)')

    def test_fetch_teams_indexes_multiple_ids_by_id(self):
        session = MagicMock()
        session.get.return_value = make_response(
            200,
            [
                {'id': 1, 'name': 'Team A'},
                {'id': 2, 'name': 'Team B'},
            ],
        )
        client = make_client(session)

        result = client.fetch_teams({2, 1})

        self.assertEqual(
            result,
            {1: {'id': 1, 'name': 'Team A'}, 2: {'id': 2, 'name': 'Team B'}},
        )
        self.assertEqual(session.get.call_args.kwargs['params']['id'], 'in.(1,2)')
