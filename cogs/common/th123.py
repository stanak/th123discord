from datetime import datetime
import dataclasses
from typing import List, Tuple

id2characcter_hash = {
    0: 'reimu',
    1: 'marisa',
    2: 'sakuya',
    3: 'alice',
    4: 'patchouli',
    5: 'youmu',
    6: 'remilia',
    7: 'yuyuko',
    8: 'yukari',
    9: 'suika',
    10: 'reisen',
    11: 'aya',
    12: 'komachi',
    13: 'iku',
    14: 'tenshi',
    15: 'sanae',
    16: 'cirno',
    17: 'meirin',
    18: 'utsuho',
    19: 'suwako',
}


def id2character(c_id):
    return id2characcter_hash[c_id]


class Th123ReplayBuilder:
    def __init__(self):
        self.replay = [0] * 0x7a
        self._set_version()
        self._set_mode()
        self._set_player_flag()
        self._set_positions()

    def _set_version(self):
        # 1.10a
        self.replay[0x00:0x01] = bytes.fromhex('d200')

    def set_date(self, date):
        month = date.month
        day = date.day
        self.replay[0x06:0x08] = [month, day]

    def _set_mode(self):
        self.replay[0x08] = 0x06

    def set_match_id(self, match_id):
        self.replay[0x0b] = match_id

    def _set_player_flag(self):
        self.replay[0x0c] = 0x03

    def set_characters(self, p1, p2):
        self.replay[0x0e] = p1
        self.replay[0x3f] = p2

    def set_colors(self, p1, p2):
        self.replay[0x0f] = p1
        self.replay[0x40] = p2

    def set_deck_sizes(self, p1, p2):
        self.replay[0x10] = p1
        self.replay[0x41] = p2

    def set_decks(self, p1, p2):
        expanded_p1 = [b1 for b2 in p1 for b1 in b2]
        expanded_p2 = [b1 for b2 in p2 for b1 in b2]
        p1_offset = 0x14
        p1_end = 0x14 + 40
        p2_offset = 0x45
        p2_end = 0x45 + 40
        self.replay[p1_offset:p1_end] = expanded_p1
        self.replay[p2_offset:p2_end] = expanded_p2

    def _set_positions(self):
        self.replay[0x3c] = 0
        self.replay[0x6d] = 1

    def set_simultaneous_buttons(self, p1, p2):
        self.replay[0x3e] = p1
        self.replay[0x6f] = p2

    def set_stage(self, stage_id):
        self.replay[0x71] = stage_id

    def set_bgm(self, bgm_id):
        self.replay[0x72] = bgm_id

    def set_seed(self, seed):
        self.replay[0x73:0x73+4] = seed.to_bytes(4, 'little')

    def set_input_size(self, size):
        self.replay[0x77:0x79] = size.to_bytes(4, 'little')

    def set_inputs(self, game_inputs):
        self.replay += game_inputs

    def build_replay(self, replay_meta):
        self.set_date(replay_meta.date)
        self.set_match_id(replay_meta.match_id)
        self.set_characters(*replay_meta.characters)
        self.set_colors(*replay_meta.colors)
        self.set_deck_sizes(*replay_meta.deck_sizes)
        self.set_decks(*replay_meta.decks)
        self.set_simultaneous_buttons(*replay_meta.simultaneous_buttons)
        self.set_stage(replay_meta.stage)
        self.set_bgm(replay_meta.bgm)
        self.set_seed(replay_meta.seed)
        self.set_input_size(replay_meta.input_size)
        self.set_inputs(replay_meta.game_inputs)
        return bytearray(self.replay)


@dataclasses.dataclass
class Th123ReplayMeta():
    deck_type = Tuple[int, int, int, int, int, int, int, int, int, int, int, int, int, int, int, int, int, int, int, int]
    date: datetime = dataclasses.field(default=datetime(2000, 1, 1, 0, 0, 0), init=False)
    match_id: int = dataclasses.field(default=1, init=False)
    characters: Tuple[int, int] = dataclasses.field(default=(0, 0), init=False)
    colors: Tuple[int, int] = dataclasses.field(default=(0, 0), init=False)
    deck_sizes: Tuple[int, int] = dataclasses.field(default=(0, 0), init=False)
    decks: Tuple[deck_type, deck_type] = dataclasses.field(default=(tuple([0]*20), tuple([0]*20)), init=False)
    simultaneous_buttons: Tuple[int, int] = dataclasses.field(default=(0, 0), init=False)
    stage: int = dataclasses.field(default=0, init=False)
    bgm: int = dataclasses.field(default=0, init=False)
    seed: Tuple[int, int, int, int] = dataclasses.field(default=(0, 0, 0, 0), init=False)
    input_size: int = dataclasses.field(default=0, init=False)
    game_inputs: List[int] = dataclasses.field(default_factory=list, init=False)


