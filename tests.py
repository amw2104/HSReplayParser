import unittest
from parser import HSReplayReader


class HSReplayReaderTests(unittest.TestCase):

	def setUp(self):
		with open('./Power_2.log.xml', mode='rb') as f:
			self.power_2_reader = HSReplayReader(f)

	def test_player_names(self):
		self.assertEqual(self.power_2_reader.replay.game.first_player.name, "Veritas")
		self.assertEqual(self.power_2_reader.replay.game.second_player.name, "TheKEG")

	def test_deck_capture(self):
		self.assertEqual(len(self.power_2_reader.replay.game.first_player.deck), 30)
		self.assertEqual(len(self.power_2_reader.replay.game.second_player.deck), 30)

	def test_deck_lists(self):
		expected_winning_deck = ['CS1_112', 'EX1_091', 'EX1_284', 'BRM_034', 'BRM_034', 'BRM_004', 'CS2_235', 'AT_017', 'GVG_008']
		expected_loosing_deck = ['EX1_354', 'EX1_382', 'AT_104', 'GVG_061', 'GVG_060', 'NEW1_019', 'GVG_061', 'EX1_005', 'GVG_096', 'EX1_383', 'CS2_203', 'AT_104', 'EX1_382']

		actual_winning_deck = self.power_2_reader.replay.game.winner.deck_list
		actual_loosing_deck = self.power_2_reader.replay.game.looser.deck_list

		self.assertCountEqual(actual_winning_deck, expected_winning_deck)
		self.assertCountEqual(actual_loosing_deck, expected_loosing_deck)