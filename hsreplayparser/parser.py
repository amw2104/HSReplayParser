"""A replay parsing module for the HSReplay specification.

The parser converts .hsreplay files into tree like data structures that can be interrogated for game details. The
details of the HSReplay specification can be found at: https://github.com/HearthSim/HSReplay
"""
from hearthstone.enums import *
from xml.parsers.expat import ParserCreate, ExpatError
import xml.parsers.expat.errors as errors
import logging


LOG = logging.getLogger(__name__)
THE_COIN = 'GAME_005'


class ReplayParserError(Exception):
	pass


class HSReplayParser:
	"""A replay parser for the HSReplay specification.

	The parser converts the .hsreplay file into a tree data structure composed of the provided sub-classes of the
	ReplayBaseElement object. The parser stores a pointer to the current element in the tree it is building in the
	_current variable. Each new element encountered in the replay file triggers an invocation of start_element() on the
	current element and the end of each element triggers an invocation of end_element(). The parser expects both methods
	to return an updated reference to the element that is now the current element in the tree data structure. The parser
	uses this reference to update the element to which _current is pointing.
	"""

	def __init__(self):
		self._current = None
		self._hsreplay = None
		self._is_final = False
		self.parser = ParserCreate()
		self.parser.StartElementHandler = self._start_element_handler
		self.parser.EndElementHandler = self._end_element_handler

	def _start_element_handler(self, name, attributes):
		LOG.debug('Start element %s at line %d: %s' % (name, self.parser.CurrentLineNumber, str(attributes)))

		if not self._current:
			if name == 'HSReplay':
				replay_element = ReplayElement(attributes, None, None)
				self._current = replay_element
				self._hsreplay = replay_element
			else:
				raise ReplayParserError("HSReplay files must begin with an HSReplay element.")
		else:
			try:
				self._current = self._current.start_element(name, attributes)
			except ReplayParserError as e:
				raise ReplayParserError("Line %d: %s" % (self.parser.CurrentLineNumber, e))

	def _end_element_handler(self, name):
		LOG.debug('End element %s at line %d' % (name, self.parser.CurrentLineNumber))
		self._current = self._current.end_element(name)

	def parse_file(self, f):
		"""Parse a file-like object open in read binary mode.

		Args:
			f (file handle): The file like object containing the replay.
		"""
		if self._is_final:
			raise ReplayParserError("Parsing already completed. Instantiate a new instance to parse another replay.")

		try:
			self.parser.ParseFile(f)
			self._is_final = True
		except ExpatError as err:
			raise ReplayParserError(
				"Parsing Error on line %d character %d: %s" % (err.lineno, err.offset, errors.messages[err.code]))

	def parse_data(self, data, is_final=False):
		"""Parse a chunk of binary replay data.

		It is acceptable for data to be zero-length. is_final must be set to True at the end of the input.

		Args:
			data (Bytes) - Binary data from a replay file.
			is_final (Boolean) - Indicates the end of input.
		"""
		if self._is_final:
			raise ReplayParserError("Parsing already completed. Instantiate a new instance to parse another replay.")

		try:
			self.parser.Parse(data, is_final)
			self._is_final = is_final
		except ExpatError as err:
			raise ReplayParserError(
				"Parsing Error on line %d character %d: %s" % (err.lineno, err.offset, errors.messages[err.code]))

	@property
	def replay(self):
		"""A reference to the parsed replay. Returns None if parsing has not completed."""
		return self._hsreplay if self._is_final else None


class ReplayBaseElement:
	"""The base class of all elements that participate in the tree data structure created by the parser.

	Override start_element() and end_element() in sub-classes to provide element specific logic for handling replay
	elements. The sub-class implementations of start_element() are responsible for instantiating the correct sub-class
	representation of each child tag encountered by the HSReplayParser. The HSReplayParser expects both start_element()
	and end_element() to return a reference to the now current element of the tree data structure being constructed.

	The default implementation of start_element() and end_element() are designed to work for elements which only
	contain <Tag> elements as children, e.g. <GameEntity>, <Player>, <FullEntity>, and <ShowEntity>. Tags with other
	legal child element types must at least override start_element().

	Args:
		attributes - The dictionary of attributes on the opening tag of the element in the replay file.
		parent - The direct parent element of this instance in the tree.
		game - A reference to the element representing the top level <Game> tag in the replay file.
	"""

	def __init__(self, attributes, parent, game):
		self._attributes = attributes
		self._parent = parent
		self._game = game
		self._tags = {}

	def __repr__(self):
		result = "<%s" % self.element
		if len(self._attributes):
			result += " "
			result += " ".join("%s=%s" % item for item in self._attributes.items())
		result += ">"
		return result

	def start_element(self, name, attributes):
		if name == "Tag":
			tag = ReplayTagElement(attributes, self, self._game)
			self._tags[tag.tag] = tag.value
			return tag
		else:
			raise ReplayParserError(
				"Only <Tag> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))

	def end_element(self, name):
		if self.element == name:
			return self._parent
		else:
			return self

	def process_tag_change(self, tag_change):
		self._tags[tag_change.tag] = tag_change.value

	def _tag_value(self, t):
		k = str(int(t))
		return self._tags[k] if k in self._tags else None

	def _has_tag(self, t):
		k = str(int(t))
		return k in self._tags

	@property
	def id(self):
		return self._attributes["id"]


class ReplayElement(ReplayBaseElement):
	"""The top level <HSReplay> tag found at the beginning of every .hsreplay file."""
	element = "HSReplay"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._games = []

	def start_element(self, name, attributes):

		if name == 'Game':
			game_element = GameElement(attributes, self, None)
			self._games.append(game_element)
			self._game = game_element
			return game_element
		else:
			raise ReplayParserError("Only <Game> elements can descend from <HSReplay> but a <%s> tag was encountered." % name)

	@property
	def games(self):
		return self._games


class GameElement(ReplayBaseElement):
	"""The top level <Game> element expected directly after the <HSReplay> element.

	The game element serves as the primary interface for interrogating the replay tree for game details after parsing is
	completed via public methods like GameElement.winner() or GameElement.first_player().

	During the initial parsing of the replay file the game element is also responsible for dispatching and broadcasting
	state mutations represented via elements like <TagChange> and <ShowEntity>. State mutating elements like these will
	call back to the _process*(...) style methods to ensure that all relevant components of the tree data structure are
	notified of the state change.
	"""
	element = "Game"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._game = self

		self._initialized = False
		self._first_main_stage_started = False

		self._start_element_handlers = {
			"GameEntity": self._start_game_entity,
			"Player": self._start_player_entity,
			"FullEntity": self._start_full_entity,
			"TagChange": self._start_tag_change,
			"Action": self._start_action,
			"Choices": self._start_choices,
			"SendChoices": self._start_send_choices,
			"ChosenEntities": self._start_chosen_entities,
			"Options": self._start_options,
			"SendOption": self._start_send_options,
			"ShowEntity": self._start_show_entity,
		}

		self._game_entity = None
		self._players = []
		self._entities = {}

		self._first_player = None
		self._second_player = None
		self._current_player = None

	def _process_tag_change(self, tag_change):
		if tag_change.entity in self._entities:
			self._entities[tag_change.entity].process_tag_change(tag_change)

		if int(tag_change.tag) == int(GameTag.STEP):
			if int(tag_change.value) == int(Step.BEGIN_MULLIGAN):
				for player in self._players:
					player._capture_deck()
					player._capture_initial_draw()

		if int(tag_change.tag) == int(GameTag.STEP) and int(tag_change.value) == int(Step.MAIN_READY):
			if not self._first_main_stage_started:
				for player in self._players:
					player._capture_post_mulligan_hand()
				self._first_main_stage_started = True

	def _process_show_entity(self, show_entity):
		for player in self._players:
			player._process_show_entity(show_entity)

	def get_player(self, player_id):
		for p in self._players:
			if p.player_id == player_id:
				return p

		return None

	@property
	def first_player(self):
		return self._first_player

	@property
	def second_player(self):
		return self._second_player

	@property
	def winner(self):
		for p in self._players:
			if int(p._tag_value(GameTag.PLAYSTATE)) in (int(PlayState.WINNING), int(PlayState.WON)):
				return p

		return None

	@property
	def complete(self):
		return self.winner != None

	@property
	def looser(self):
		for p in self._players:
			if int(p._tag_value(GameTag.PLAYSTATE)) in (
			int(PlayState.LOSING), int(PlayState.LOST), int(PlayState.CONCEDED)):
				return p

		return None

	def _initialize(self):

		for player in self._players:
			if player.is_current_player:
				self._current_player = player
				self._first_player = player
			else:
				self._second_player = player

		self._initialized = True

	def _initialization_requirements_met(self):
		return self._game_entity and len(self._players) == 2

	def start_element(self, name, attributes):

		if not self._initialized and self._initialization_requirements_met():
			self._initialize()

		if name in self._start_element_handlers:
			return self._start_element_handlers[name](attributes)
		else:
			raise ReplayParserError("<%s> is not a valid child element type of <Game> element." % name)

	def end_element(self, name):
		return super().end_element(name)

	def _start_game_entity(self, attributes):
		game_entity = GameEntityElement(attributes, self, self._game)
		self._game_entity = game_entity
		self._entities[game_entity.id] = game_entity
		return game_entity

	def _start_player_entity(self, attributes):
		player_element = PlayerElement(attributes, self, self._game)
		self._players.append(player_element)
		self._entities[player_element.id] = player_element
		return player_element

	def _start_full_entity(self, attributes):
		full_entity = FullEntityElement(attributes, self, self._game)
		self._entities[full_entity.id] = full_entity
		return full_entity

	def _start_tag_change(self, attributes):
		tag_change = TagChangeElement(attributes, self, self._game)
		return tag_change

	def _start_show_entity(self, attributes):
		show_entity = ShowEntityElement(attributes, self, self._game)
		return show_entity

	def _start_action(self, attributes):
		action = ActionElement(attributes, self, self._game)
		return action

	def _start_choices(self, attributes):
		choices_element = ChoicesElement(attributes, self, self._game)
		return choices_element

	def _start_chosen_entities(self, attributes):
		chosen_entities_element = ChosenEntitiesElement(attributes, self, self._game)
		return chosen_entities_element

	def _start_send_choices(self, attributes):
		send_choices = SendChoicesElement(attributes, self, self._game)
		return send_choices

	def _start_options(self, attributes):
		options = OptionsElement(attributes, self, self._game)
		return options

	def _start_send_options(self, attributes):
		send_option = SendOptionElement(attributes, self, self._game)
		return send_option


class PlayerElement(ReplayBaseElement):
	"""The <Player> element.

	The player elements represent the entities referred to by the other entities which have a GameTag.CONTROLLER Tag.
	They have an ID value similar to all other elements as well as a playerID value which is unique to the player
	elements. The value of the GameTag.CONTROLLER tag will always be a reference to one of the playerID values.
	"""
	element = "Player"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._controlled_entities = []
		self._deck = {}
		self._pre_mulligan_initial_hand = {}
		self._post_mulligan_initial_hand = {}
		self._mulligan_discards = set()

	def _process_show_entity(self, show_entity):
		if show_entity.entity in self._deck:
			self._deck[show_entity.entity] = show_entity.cardID

			if not self._game._first_main_stage_started:
				# The <ShowEntity> tags before the first main stage represent the replacement cards during the mulligan phase
				self._post_mulligan_initial_hand[show_entity.entity] = show_entity.cardID

	def register_controlled_entity(self, entity):
		self._controlled_entities.append(entity)

	def _capture_deck(self):
		"""Invoked immediately before the mulligan phase to cleanly capture the original cards in each player's deck.

		Over the course of the match the controlled entities and cards in each player's deck can be modified via cards
		like Mirror Entity and Entomb.
		"""
		for entity in self._controlled_entities:
			if int(entity._tag_value(GameTag.ZONE)) in (int(Zone.DECK), int(Zone.HAND)):
				cardID = entity._attributes["cardID"] if "cardID" in entity._attributes else None
				if cardID != THE_COIN:
					self._deck[entity.id] = cardID

	def _capture_initial_draw(self):
		# Invoked right before the mulligan phase begins to capture the initial hand.
		for entity in self._controlled_entities:
			if int(entity._tag_value(GameTag.ZONE)) == int(Zone.HAND):
				cardID = entity._attributes["cardID"] if "cardID" in entity._attributes else None
				if cardID != THE_COIN:
					self._pre_mulligan_initial_hand[entity.id] = cardID

	def _capture_post_mulligan_hand(self):
		# Invoked right after the mulligan phase ends, but before the first main phase begins.
		for entity in self._controlled_entities:
			if int(entity._tag_value(GameTag.ZONE)) == int(Zone.HAND):
				cardID = entity._attributes["cardID"] if "cardID" in entity._attributes else None
				if cardID != THE_COIN:
					self._post_mulligan_initial_hand[entity.id] = cardID

		# Set difference used to determine which cards were discarded
		self._mulligan_discards = set(self._pre_mulligan_initial_hand.keys()) - set(self._post_mulligan_initial_hand.keys())

	@property
	def player_id(self):
		return self._attributes["playerID"]

	@property
	def is_current_player(self):
		return self._tag_value(GameTag.CURRENT_PLAYER) == "1"

	@property
	def name(self):
		return self._attributes["name"] if "name" in self._attributes else None

	@property
	def deck(self):
		return self._deck.items()

	@property
	def deck_list(self):
		return [v for k, v in self._deck.items() if v]

	@property
	def mulligan_info(self):
		info = MulliganInfo()

		for k, v in self._pre_mulligan_initial_hand.items():
			info.initial_draw.append(self._deck[k] if self._deck[k] else "UNREVEALED")

		for k in self._mulligan_discards:
			info.discarded.append(self._deck[k] if self._deck[k] else "UNREVEALED")

		for k, v in self._post_mulligan_initial_hand.items():
			info.final_cards.append(self._deck[k] if self._deck[k] else "UNREVEALED")

		return info


class ReplayTagElement(ReplayBaseElement):
	element = "Tag"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)

		if 'tag' not in attributes or 'value' not in attributes:
			raise ReplayParserError(
				"Invalid Tag element. 'tag' and 'value' must be provided, but arguments were: %s" % str(attributes))

		self.tag = attributes['tag']
		self.value = attributes['value']


class GameEntityElement(ReplayBaseElement):
	element = "GameEntity"


class FullEntityElement(ReplayBaseElement):
	element = "FullEntity"

	def end_element(self, name):
		# If the entity has a controller, register the entity with the controller.
		# Do this during end_element() to make sure that all child <Tag> elements have been processed.
		if self._has_tag(GameTag.CONTROLLER):
			controller_id = self._tag_value(GameTag.CONTROLLER)
			player = self._game.get_player(player_id=controller_id)

			player.register_controlled_entity(self)

		return super().end_element(name)

	@property
	def has_card_type(self):
		return self._has_tag(GameTag.CARDTYPE)

	@property
	def is_collectible_card(self):
		card_type_value = self._tag_value(GameTag.CARDTYPE)
		return card_type_value in (CardType.MINION, CardType.SPELL, CardType.WEAPON,)


class TagChangeElement(ReplayBaseElement):
	element = "TagChange"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)

		self._game._process_tag_change(self)

	@property
	def entity(self):
		return self._attributes["entity"]

	@property
	def tag(self):
		return self._attributes["tag"]

	@property
	def value(self):
		return self._attributes["value"]


class ShowEntityElement(ReplayBaseElement):
	element = "ShowEntity"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)

		self._game._process_show_entity(self)

	@property
	def entity(self):
		return self._attributes["entity"]

	@property
	def cardID(self):
		return self._attributes["cardID"]


class HideEntityElement(ReplayBaseElement):
	element = "HideEntity"


class MetaDataElement(ReplayBaseElement):
	element = "MetaData"

	def start_element(self, name, attributes):
		if name == "Info":
			info = InfoElement(attributes, self, self._game)
			return info
		else:
			raise ReplayParserError(
				"Only <Info> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class InfoElement(ReplayBaseElement):
	element = "Info"


class ActionElement(ReplayBaseElement):
	element = "Action"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)

		self._current = None
		self._start_element_handlers = {
			"TagChange": self._start_tag_change,
			"Choices": self._start_choices,
			"SendChoices": self._start_send_choices,
			"ShowEntity": self._start_show_entity,
			"HideEntity": self._start_hide_entity,
			"Action": self._start_action,
			"MetaData": self._start_meta_data,
			"FullEntity": self._start_full_entity,
		}

	def _start_full_entity(self, attributes):
		full_entity = FullEntityElement(attributes, self, self._game)
		self._current = full_entity
		return full_entity

	def _start_meta_data(self, attributes):
		meta_data = MetaDataElement(attributes, self, self._game)
		self._current = meta_data
		return meta_data

	def _start_tag_change(self, attributes):
		tag_change = TagChangeElement(attributes, self, self._game)
		self._current = tag_change
		return tag_change

	def _start_choices(self, attributes):
		choices_element = ChoicesElement(attributes, self, self._game)
		self._current = choices_element
		return choices_element

	def _start_send_choices(self, attributes):
		send_choices_element = SendChoicesElement(attributes, self, self._game)
		self._current = send_choices_element
		return send_choices_element

	def _start_show_entity(self, attributes):
		show_entity = ShowEntityElement(attributes, self, self._game)
		self._current = show_entity
		return show_entity

	def _start_hide_entity(self, attributes):
		hide_entity = HideEntityElement(attributes, self, self._game)
		self._current = hide_entity
		return hide_entity

	def _start_action(self, attributes):
		action = ActionElement(attributes, self, self._game)
		self._current = action
		return action

	def start_element(self, name, attributes):
		if name in self._start_element_handlers:
			return self._start_element_handlers[name](attributes)
		else:
			raise ReplayParserError("<%s> is not a valid child element type of <Action> element." % name)

	def end_element(self, name):
		return super().end_element(name)


class ChoicesElement(ReplayBaseElement):
	element = "Choices"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._choices = []

	def start_element(self, name, attributes):
		if name == "Choice":
			choice = ChoiceElement(attributes, self, self._game)
			self._choices.append(choice)
			return choice
		else:
			raise ReplayParserError(
				"Only <Choice> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class ChoiceElement(ReplayBaseElement):
	element = "Choice"


class SendChoicesElement(ReplayBaseElement):
	"""Represents the result of the friendly player's choice."""
	element = "SendChoices"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._choices = []

	def start_element(self, name, attributes):
		if name == "Choice":
			choice = ChoiceElement(attributes, self, self._game)
			self._choices.append(choice)
			return choice
		else:
			raise ReplayParserError(
				"Only <Choice> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class ChosenEntitiesElement(ReplayBaseElement):
	"""Represents the result of the opposing player's choice."""
	element = "ChosenEntities"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._choices = []

	def start_element(self, name, attributes):
		if name == "Choice":
			choice = ChoiceElement(attributes, self, self._game)
			self._choices.append(choice)
			return choice
		else:
			raise ReplayParserError(
				"Only <Choice> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class OptionsElement(ReplayBaseElement):
	element = "Options"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._option_list = None
		self._options = []

	def start_element(self, name, attributes):
		if name == "OptionList":
			option_list = OptionListElement(attributes, self, self._game)
			self._option_list = option_list
			return option_list
		elif name == "Option":
			option = OptionElement(attributes, self, self._game)
			self._options.append(option)
			return option
		else:
			raise ReplayParserError(
				"Only <OptionList> or <Option> elements can descend from <%s> but a <%s> tag was encountered." % (
				self.element, name))


class OptionListElement(ReplayBaseElement):
	element = "OptionList"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._options = []

	def start_element(self, name, attributes):
		if name == "Option":
			option = OptionElement(attributes, self, self._game)
			self._options.append(option)
			return option
		else:
			raise ReplayParserError(
				"Only <Option> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class OptionElement(ReplayBaseElement):
	element = "Option"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._targets = []

	def start_element(self, name, attributes):
		if name == "Target":
			target = TargetElement(attributes, self, self._game)
			self._targets.append(target)
			return target
		elif name == "SubOption":
			sub_option = SubOptionElement(attributes, self, self._game)
			return sub_option
		else:
			raise ReplayParserError(
				"Only <Target> or <SubOption> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class SubOptionElement(ReplayBaseElement):
	element = "SubOption"

	def __init__(self, attributes, parent, game):
		super().__init__(attributes, parent, game)
		self._targets = []

	def start_element(self, name, attributes):
		if name == "Target":
			target = TargetElement(attributes, self, self._game)
			self._targets.append(target)
			return target
		else:
			raise ReplayParserError(
				"Only <Target> elements can descend from <%s> but a <%s> tag was encountered." % (self.element, name))


class TargetElement(ReplayBaseElement):
	element = "Target"


class SendOptionElement(ReplayBaseElement):
	element = "SendOption"


class MulliganInfo:
	"""A simple container for metadata related to each player's mulligan phase."""

	def __init__(self):
		self.initial_draw = []
		self.discarded = []
		self.final_cards = []
