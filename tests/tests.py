import unittest
from hsreplayparser.parser import HSReplayParser, ReplayParserError


class HSReplayParserParsingTests(unittest.TestCase):
	"""Tests related to the various modes of providing data for parsing."""

	def test_parsing_binary_chunks(self):
		data = open('./Power_2.log.xml', mode='rb').read()
		start_index = 0
		batch_size = 1000

		parser = HSReplayParser()
		self.assertIsNone(parser.replay)

		while start_index < len(data):
			end_index = 0
			is_final = False

			if start_index + batch_size >= len(data):
				end_index = len(data)
				is_final = True
			else:
				end_index = start_index + batch_size

			chunk = data[start_index: end_index]
			parser.parse_data(chunk, is_final)
			start_index = end_index

			if not is_final:
				self.assertIsNone(parser.replay)

		self.assertIsNotNone(parser.replay)
		self.assertRaises(ReplayParserError, parser.parse_data, data[0:100])


class HSReplayParserGameInspectionTests(unittest.TestCase):
	"""Tests related to inspecting the game state after parsing has completed."""

	def setUp(self):

		with open('./Power_2.log.xml', mode='rb') as f:
			self.parser = HSReplayParser()
			self.parser.parse_file(f)

	def test_player_names(self):
		self.assertEqual(self.parser.replay.games[0].first_player.name, "Veritas")
		self.assertEqual(self.parser.replay.games[0].second_player.name, "TheKEG")

	def test_deck_capture(self):
		self.assertEqual(len(self.parser.replay.games[0].first_player.deck), 30)
		self.assertEqual(len(self.parser.replay.games[0].second_player.deck), 30)

	def test_deck_lists(self):
		expected_winning_deck = ['CS1_112', 'EX1_091', 'EX1_284', 'BRM_034', 'BRM_034', 'BRM_004', 'CS2_235', 'AT_017', 'GVG_008']
		expected_loosing_deck = ['EX1_354', 'EX1_382', 'AT_104', 'GVG_061', 'GVG_060', 'NEW1_019', 'GVG_061', 'EX1_005', 'GVG_096', 'EX1_383', 'CS2_203', 'AT_104', 'EX1_382']

		actual_winning_deck = self.parser.replay.games[0].winner.deck_list
		actual_loosing_deck = self.parser.replay.games[0].looser.deck_list

		self.assertCountEqual(actual_winning_deck, expected_winning_deck)
		self.assertCountEqual(actual_loosing_deck, expected_loosing_deck)

	def test_mulligan_info(self):
		# FIRST PLAYER
		first_player = self.parser.replay.games[0].first_player
		first_player_mulligan_info = first_player.mulligan_info

		expected_first_player_initial_draw = ['UNREVEALED', 'AT_017', 'UNREVEALED']
		expected_first_player_discarded = ['UNREVEALED', 'UNREVEALED']
		expected_first_player_final_cards = ['CS2_235', 'UNREVEALED', 'AT_017']

		self.assertCountEqual(expected_first_player_initial_draw, first_player_mulligan_info.initial_draw)
		self.assertCountEqual(expected_first_player_discarded, first_player_mulligan_info.discarded)
		self.assertCountEqual(expected_first_player_final_cards, first_player_mulligan_info.final_cards)

		# SECOND PLAYER
		second_player = self.parser.replay.games[0].second_player
		second_player_mulligan_info = second_player.mulligan_info

		expected_second_player_initial_draw = ['EX1_382', 'GVG_096', 'AT_104', 'GVG_061']
		expected_second_player_discarded = ['EX1_382', 'AT_104']
		expected_second_player_final_cards = ['GVG_061', 'GVG_096', 'GVG_060', 'NEW1_019']

		self.assertCountEqual(expected_second_player_initial_draw, second_player_mulligan_info.initial_draw)
		self.assertCountEqual(expected_second_player_discarded, second_player_mulligan_info.discarded)
		self.assertCountEqual(expected_second_player_final_cards, second_player_mulligan_info.final_cards)