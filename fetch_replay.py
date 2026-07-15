#!/usr/bin/env python3
"""非想天則ホストのリプレイを観戦接続で取得する単一スクリプト。

使い方:
    python fetch_replay.py <IP:Port> [--autopunch] [--out DIR] [--once] [-v]

仕組み (delthas の touhou-protocol-docs 準拠):
  1. ホストへ INIT_REQUEST(観戦) をプローブ送信し、対戦中なら REDIRECT (0x08)
     で対戦相手 (client) のアドレスが返る。
  2. ホスト経由のホールパンチ (HELLO) で client に接続し、観戦セッションを
     確立 (INIT_REQUEST -> INIT_SUCCESS でプロファイル名も得る)。
  3. GAME_REPLAY_REQUEST を送り続け、GAME_MATCH でキャラ・デッキ・ステージ・
     シードを、GAME_REPLAY (zlib) で両者の入力列を集める。
  4. end_frame まで揃ったらゲーム本体と同じ形式 (ヘッダ 0x7B バイト +
     1 フレームあたり [P1 入力 2B, P2 入力 2B] の計 4 バイト) の .rep を書き出す。

注意:
  - 観戦を許可しているホストのみ取得できる。
  - 対戦の先頭からの入力はホストが保持しているので、途中から観戦しても
    その試合の最初から復元できる。
  - GAME_REPLAY の frame_id は「16bit 入力の通し番号」で、1 ゲームフレームに
    つき P1/P2 の 2 入力ぶん進む。配られる入力列は .rep 本体と同じ並びなので
    番号順に連結してそのまま書き出す。
"""
from __future__ import annotations

import argparse
import re
import socket
import struct
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path

# Hisoutensoku 1.10ac (SWR リンクあり・Sokuroll なし) の game_id
GAME_ID = bytes.fromhex("6e7365d9ffc4" "6e488d7ca192" "31347295")
INIT_STUFF = bytes.fromhex("0000000028000000")

# autopunch リレー (https://github.com/delthas/autopunch)
AUTOPUNCH_RELAY = ("delthas.fr", 14763)

CHAR_NAMES = {
    0: "reimu", 1: "marisa", 2: "sakuya", 3: "alice", 4: "patchouli",
    5: "youmu", 6: "remilia", 7: "yuyuko", 8: "yukari", 9: "suika",
    10: "reisen", 11: "aya", 12: "komachi", 13: "iku", 14: "tenshi",
    15: "sanae", 16: "cirno", 17: "meiling", 18: "utsuho", 19: "suwako",
}

PROBE_INTERVAL = 1.0
HELLO_INTERVAL = 0.2
INIT_INTERVAL = 0.5
REPLAY_REQ_INTERVAL = 0.05
SESSION_TIMEOUT = 20.0
# 新しい入力が来ないままこの秒数経ったら状況を警告する (保存はしない)
INPUT_STALL_WARN_SEC = 15.0
# 追いついて入力が途絶えたとき、末尾を再要求して end_frame を引き出す間隔
STALL_REREQUEST_SEC = 2.0
PROGRESS_LOG_INTERVAL = 5.0
# ホスト側 autopunch DLL の punch マッピングは 10 秒で失効するので、
# リレーへの lookup を定期的に再送してホスト→こちらの穴あけを維持する
AUTOPUNCH_KEEPALIVE = 4.0


# ----------------------------------------------------------------------------
# パケット生成
# ----------------------------------------------------------------------------
def sockaddr_in(addr: tuple[str, int]) -> bytes:
    ip, port = addr
    return b"\x02\x00" + struct.pack("!H", port) + socket.inet_aton(ip) + bytes(8)


def pkt_hello(peer: tuple[str, int], target: tuple[str, int]) -> bytes:
    return b"\x01" + sockaddr_in(peer) + sockaddr_in(target) + bytes(4)


def pkt_chain_ack() -> bytes:
    # 末端観戦者の spectator_count = 1 + 3*1 = 4
    return b"\x04" + (4).to_bytes(4, "little")


def pkt_init_spectate() -> bytes:
    # 0x05 <game_id> <stuff> 0x00(観戦) ... 全体 65 バイト
    p = b"\x05" + GAME_ID + INIT_STUFF + b"\x00" + b"\x00" + bytes(24) + bytes(14)
    assert len(p) == 65
    return p


def pkt_quit() -> bytes:
    return b"\x0b"


def pkt_replay_request(frame: int, match_id: int) -> bytes:
    return b"\x0e\x0b" + (frame & 0xFFFFFFFF).to_bytes(4, "little") + bytes([match_id & 0xFF])


def parse_sockaddr(data: bytes) -> tuple[str, int]:
    port = struct.unpack("!H", data[2:4])[0]
    ip = socket.inet_ntoa(data[4:8])
    return ip, port


# ----------------------------------------------------------------------------
# GAME_MATCH (0x0d 0x04) のパース
# ----------------------------------------------------------------------------
class PlayerInfo:
    def __init__(self, char: int, skin: int, deck: list[bytes], simul: int):
        self.char = char
        self.skin = skin
        self.deck = deck
        self.simul = simul


class MatchInfo:
    def __init__(self, p1: PlayerInfo, p2: PlayerInfo, stage: int, music: int,
                 seed: bytes, match_id: int):
        self.p1 = p1
        self.p2 = p2
        self.stage = stage
        self.music = music
        self.seed = seed
        self.match_id = match_id


def parse_game_match(data: bytes) -> MatchInfo:
    """観戦者向け GAME_MATCH。両プレイヤーのフルデッキを含む。"""
    off = 2  # 0x0d 0x04 の後

    def player() -> PlayerInfo:
        nonlocal off
        char, skin, _deck_id, deck_size = data[off], data[off + 1], data[off + 2], data[off + 3]
        off += 4
        deck = [data[off + 2 * i: off + 2 * i + 2] for i in range(deck_size)]
        off += 2 * deck_size
        simul = data[off]
        off += 1
        return PlayerInfo(char, skin, deck, simul)

    p1 = player()
    p2 = player()
    stage = data[off]
    music = data[off + 1]
    seed = bytes(data[off + 2: off + 6])
    match_id = data[off + 6]
    return MatchInfo(p1, p2, stage, music, seed, match_id)


# ----------------------------------------------------------------------------
# .rep 組み立て (ゲーム本体形式: ヘッダ 0x7B バイト + 入力列)
# 実ファイル解析より: 本体は 16bit LE 入力が P1/P2 交互にフレーム順で並び
# (1 フレーム = 4 バイト)、ヘッダ 0x77 の値は 16bit 入力の総数。
# GAME_REPLAY が配る入力列はこれと同じ並びなので、そのまま連結して書けばよい。
# ----------------------------------------------------------------------------
def build_replay(info: MatchInfo, units: list[bytes], date: datetime) -> bytes:
    h = bytearray(0x7B)
    h[0x00:0x02] = (0x00D2).to_bytes(2, "little")  # 1.10a
    h[0x06] = date.month
    h[0x07] = date.day
    h[0x08] = 0x06  # ネット観戦リプレイ
    h[0x0B] = info.match_id & 0xFF
    h[0x0C] = 0x03  # 両プレイヤーの入力を含む

    def put_player(p: PlayerInfo, base: int) -> None:
        h[base + 0x00] = p.char
        h[base + 0x01] = p.skin
        h[base + 0x02] = min(len(p.deck), 20)
        deck_off = base + 0x06
        for i, card in enumerate(p.deck[:20]):
            h[deck_off + 2 * i: deck_off + 2 * i + 2] = card

    put_player(info.p1, 0x0E)
    h[0x3C] = 0  # P1 位置
    h[0x3E] = info.p1.simul
    put_player(info.p2, 0x3F)
    h[0x6D] = 1  # P2 位置
    h[0x6F] = info.p2.simul

    h[0x71] = info.stage
    h[0x72] = info.music
    h[0x73:0x77] = info.seed
    # 0x77 は 16bit 入力の総数 (P1+P2 交互なのでフレーム数の約 2 倍)
    h[0x77:0x7B] = len(units).to_bytes(4, "little")
    return bytes(h) + b"".join(units)


def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name) or "unknown"


# ----------------------------------------------------------------------------
# 観戦セッション
# ----------------------------------------------------------------------------
class Spectator:
    def __init__(self, host: tuple[str, int], out_dir: Path, verbose: bool):
        self.host = host
        self.probe_targets = [host]  # autopunch 時は内部ポートと NAT ポートの両方
        self.out_dir = out_dir
        self.verbose = verbose

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.settimeout(0.05)

        self.relay: tuple[str, int] | None = None  # autopunch 有効時のみ
        self.last_relay_send = 0.0

        self.p1_name = ""
        self.p2_name = ""
        self.complete_ids: set[int] = set()  # end_frame まで揃って保存できた試合
        self.reset_session()

    def reset_session(self) -> None:
        self.state = "probe"  # probe -> punch -> init -> watch
        self.parent: tuple[str, int] | None = None  # 接続先 (通常は対戦の client)
        self.redirector: tuple[str, int] | None = None  # パンチを仲介するノード
        self.match: MatchInfo | None = None
        self.inputs: dict[int, bytes] = {}  # 入力通し番号 -> 16bit 入力 (2 バイト)
        self.next_frame = 0
        self.end_frame = 0
        self.last_recv = time.monotonic()
        self.last_send = 0.0
        self.redirect_count = 0
        self.last_input_ts = 0.0  # 新しい入力を最後に受信した時刻
        self._last_progress_log = 0.0
        self._stall_warned = False

    def log(self, msg: str) -> None:
        print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)

    def debug(self, msg: str) -> None:
        if self.verbose:
            self.log(msg)

    # ---------------- 送信 (状態ごとの定期処理) ----------------
    def tick(self) -> None:
        now = time.monotonic()
        if self.relay is not None and now - self.last_relay_send >= AUTOPUNCH_KEEPALIVE:
            # lookup 再送でリレー上のマッピングとホスト側のパンチを維持する
            lookup = (
                struct.pack("!H", self.sock.getsockname()[1])
                + socket.inet_aton(self.host[0])
                + struct.pack("!H", self.host[1])
            )
            try:
                self.sock.sendto(lookup, self.relay)
            except OSError:
                pass
            self.last_relay_send = now
        if self.state == "probe" and now - self.last_send >= PROBE_INTERVAL:
            for target in self.probe_targets:
                self.sock.sendto(pkt_init_spectate(), target)
            self.last_send = now
        elif self.state == "punch" and now - self.last_send >= HELLO_INTERVAL:
            assert self.parent is not None
            if self.redirector is not None:
                # 仲介ノード経由で相手に PUNCH してもらう
                self.sock.sendto(pkt_hello(self.redirector, self.parent), self.redirector)
            self.sock.sendto(pkt_hello(self.parent, self.parent), self.parent)
            self.last_send = now
        elif self.state == "init" and now - self.last_send >= INIT_INTERVAL:
            assert self.parent is not None
            self.sock.sendto(pkt_init_spectate(), self.parent)
            self.last_send = now
        elif self.state == "watch" and now - self.last_send >= REPLAY_REQ_INTERVAL:
            assert self.parent is not None
            if self.match is None:
                # 現在の試合情報を要求 (frame=-1 が初回キック)
                self.sock.sendto(pkt_replay_request(0xFFFFFFFF, 0), self.parent)
            else:
                req = self.next_frame
                stalled = self.last_input_ts and now - self.last_input_ts >= STALL_REREQUEST_SEC
                if stalled and not self.end_frame:
                    # 追いついた後は末尾を要求し直して end_frame 付き応答を促す
                    req = max(self.next_frame - 1, 0)
                self.sock.sendto(
                    pkt_replay_request(req, self.match.match_id),
                    self.parent,
                )
                # 入力が長時間途絶えたら状況を警告する (保存はしない)
                if (
                    self.inputs
                    and self.last_input_ts
                    and not self._stall_warned
                    and now - self.last_input_ts >= INPUT_STALL_WARN_SEC
                ):
                    self._stall_warned = True
                    self.log(
                        f"入力が {int(INPUT_STALL_WARN_SEC)} 秒途絶えています "
                        f"({len(self.inputs)} 入力, end={self.end_frame or '未受信'})"
                    )
            self.last_send = now

    # ---------------- 受信ディスパッチ ----------------
    def handle(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.relay is not None and addr == self.relay:
            # リレーからの NAT マッピング通知 (8 バイト)。ゲームパケットではない
            self.debug(f"relay notify {data.hex()}")
            return
        if data == b"\x00":
            # autopunch DLL のホールパンチ用パケット。送信元ポートは相手の
            # 実フロー NAT ポートなので、プローブ候補として利用する
            if (
                self.state == "probe"
                and addr[0] == self.host[0]
                and addr not in self.probe_targets
            ):
                self.debug(f"punch from {addr[0]}:{addr[1]} -> プローブ候補に追加")
                self.probe_targets.append(addr)
            return
        self.last_recv = time.monotonic()
        if not data:
            return
        head = data[0]

        if head == 0x07 and self.state == "probe":  # INIT_ERROR (プローブ応答)
            reason = int.from_bytes(data[1:5], "little") if len(data) >= 5 else 255
            if reason == 0:
                self.log("ホストが観戦を許可していません")
                raise SystemExit(2)
            self.debug("ホストは募集中 (対戦開始待ち)")

        elif head == 0x08:  # REDIRECT: 子ノードへ誘導される
            if len(data) < 13:
                return
            target = parse_sockaddr(data[5:13])
            self.redirect_count += 1
            if self.redirect_count > 8:
                self.log("リダイレクトが多すぎます (観戦ツリーが深い?)")
                raise SystemExit(2)
            self.redirector = addr
            self.parent = target
            self.state = "punch"
            self.last_send = 0.0
            self.debug(f"redirect -> {target[0]}:{target[1]} (via {addr[0]}:{addr[1]})")

        elif head == 0x03:  # OLLEH: 接続受理
            if self.state in ("probe", "punch"):
                self.parent = addr
                self.state = "init"
                self.last_send = 0.0
                self.debug(f"connected to {addr[0]}:{addr[1]}")

        elif head == 0x07 and self.state == "init":  # INIT_ERROR
            reason = int.from_bytes(data[1:5], "little") if len(data) >= 5 else 255
            if reason == 0:
                self.log("観戦が許可されていません")
                raise SystemExit(2)
            self.debug("対戦がまだ始まっていません。待機します")
            time.sleep(1.0)

        elif head == 0x06:  # INIT_SUCCESS
            if self.state == "init":
                if len(data) >= 77:
                    self.p1_name = data[13:45].split(b"\x00")[0].decode("shift-jis", "replace")
                    self.p2_name = data[45:77].split(b"\x00")[0].decode("shift-jis", "replace")
                self.state = "watch"
                self.last_send = 0.0
                self.log(f"観戦開始: {self.p1_name or '?'} vs {self.p2_name or '?'}")

        elif head == 0x04:  # CHAIN: 生存応答を返す
            if self.parent is not None and addr == self.parent:
                self.sock.sendto(pkt_chain_ack(), addr)

        elif head == 0x0D and len(data) >= 2:  # HOST_GAME
            self.handle_host_game(data)

        elif head == 0x0B:  # QUIT: 親が切断
            if self.state != "probe":
                self.discard_note("親ノードが切断")
                self.log("親ノードが切断しました。再接続します")
                self.reset_session()

        else:
            self.debug(f"unknown packet {data[:2].hex()} from {addr[0]}:{addr[1]}")

    def handle_host_game(self, data: bytes) -> None:
        sub = data[1]
        if sub == 0x04:  # GAME_MATCH
            try:
                info = parse_game_match(data)
            except IndexError:
                return
            if info.match_id in self.complete_ids:
                return  # 完全保存済みの試合。次の試合が始まるのを待つ
            if self.match is None or info.match_id != self.match.match_id:
                self.discard_note("試合が切り替わり")
                self.match = info
                self.inputs = {}
                self.next_frame = 0
                self.end_frame = 0
                self.last_input_ts = 0.0
                self._stall_warned = False
                p1c = CHAR_NAMES.get(info.p1.char, "?")
                p2c = CHAR_NAMES.get(info.p2.char, "?")
                self.log(f"match {info.match_id}: {p1c} vs {p2c} (stage={info.stage})")
        elif sub == 0x09 and self.match is not None:  # GAME_REPLAY (zlib)
            try:
                raw = zlib.decompress(data[3:])
            except zlib.error:
                return
            if len(raw) < 10:
                return
            # frame_id / end_frame_id は「16bit 入力の通し番号」(0 始まり)。
            # 1 ゲームフレームで P1 と P2 の 2 入力ぶん進む。
            # frame_id はこのパケットに含まれる最新入力の番号で、
            # 入力は 2 バイトずつ新しい順 (番号降順) に並ぶ。
            # end_frame_id は試合最後の入力の番号 (試合中は 0)。
            frame_id = int.from_bytes(raw[0:4], "little")
            end_frame = int.from_bytes(raw[4:8], "little")
            match_id = raw[8]
            count = raw[9]  # このパケットに含まれる 16bit 入力の個数
            if match_id != self.match.match_id:
                return
            if end_frame:
                self.end_frame = end_frame
            n_inputs = min(count, (len(raw) - 10) // 2)
            # 要求位置より先の入力しか含まないパケットを格納すると入力列に
            # 歯抜けができ、以後どれだけ記録しても復元不能になる。
            # (リプレイは先頭から連続していないと再生できない)
            # Go 実装 (youmu-hisoutensoku-spectacle) と同様に破棄する。
            oldest = frame_id - n_inputs + 1
            if n_inputs and oldest > max(self.next_frame, 1):
                self.debug(
                    f"ahead packet dropped: oldest {oldest} > next {self.next_frame}"
                )
                return
            added = 0
            for i in range(n_inputs):
                idx = frame_id - i
                if idx < 0 or idx in self.inputs:
                    continue
                self.inputs[idx] = raw[10 + 2 * i: 12 + 2 * i]
                added += 1
            now_mono = time.monotonic()
            if added:
                self.last_input_ts = now_mono
            self.advance_next_frame()
            saved = self.maybe_save()
            if not saved and now_mono - self._last_progress_log >= PROGRESS_LOG_INTERVAL:
                self._last_progress_log = now_mono
                self.log(
                    f"取得中 match {match_id}: {len(self.inputs)} 入力 "
                    f"(~{len(self.inputs) // 120} 秒ぶん, end={self.end_frame or '未定'})"
                )

    def advance_next_frame(self) -> None:
        """next_frame を「まだ受信していない最小の入力番号」に進める。"""
        f = self.next_frame
        if f == 0 and 0 not in self.inputs and 1 in self.inputs:
            f = 1  # 1 始まりの実装
        while f in self.inputs:
            f += 1
        self.next_frame = f

    def maybe_save(self) -> bool:
        """end_frame (試合最後の入力番号) まで全部揃った時のみ .rep を書き出す。

        途中経過での部分保存はしない (不完全なリプレイを作らない)。
        """
        if self.match is None or self.match.match_id in self.complete_ids:
            return False
        if not self.inputs or not self.end_frame:
            return False

        # end_frame は試合最後の入力の通し番号。0 始まりか 1 始まりかは
        # 実装差があり得るので、届いた最小番号 (0 or 1) を先頭とみなす
        start = 0 if 0 in self.inputs else 1
        if start not in self.inputs:
            return False  # 先頭が欠けている (取得失敗)

        contig = start
        while contig + 1 in self.inputs:
            contig += 1
        if contig < self.end_frame:
            return False  # まだ揃っていない

        units = [self.inputs[i] for i in range(start, self.end_frame + 1)]
        now = datetime.now()
        rep = build_replay(self.match, units, now)
        p1c = CHAR_NAMES.get(self.match.p1.char, "unknown")
        p2c = CHAR_NAMES.get(self.match.p2.char, "unknown")
        name = (
            f"{now:%Y%m%d%H%M%S}"
            f"_{sanitize(self.p1_name)}({p1c})_vs_{sanitize(self.p2_name)}({p2c}).rep"
        )
        path = self.out_dir / name
        path.write_bytes(rep)
        self.complete_ids.add(self.match.match_id)
        self.log(f"saved: {path} ({len(units) // 2} frames, {len(rep)} bytes)")
        return True

    def discard_note(self, reason: str) -> None:
        """完全なリプレイにならないままデータを破棄するとき、状況を残す。"""
        if self.match is None or not self.inputs:
            return
        if self.match.match_id in self.complete_ids:
            return
        self.log(
            f"{reason}: match {self.match.match_id} は end_frame まで揃わなかった"
            f"ため破棄します ({len(self.inputs)} 入力, end={self.end_frame or '未受信'})"
        )

    # ---------------- メインループ ----------------
    def run(self, once: bool) -> None:
        self.log(f"host {self.host[0]}:{self.host[1]} をプローブ中...")
        while True:
            self.tick()
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                data, addr = None, None
            if data is not None:
                self.handle(data, addr)
                if once and self.complete_ids:
                    self.log("1 試合分を保存したので終了します")
                    self.quit()
                    return
            if time.monotonic() - self.last_recv > SESSION_TIMEOUT:
                if self.state == "probe":
                    self.log("ホストから応答がありません (ホスト未起動/ポート違い/AP 必要?)")
                    raise SystemExit(1)
                self.discard_note("タイムアウト")
                self.log("タイムアウト。最初から接続し直します")
                self.reset_session()

    def quit(self) -> None:
        try:
            self.discard_note("終了")
        except Exception:
            pass
        if self.parent is not None:
            try:
                self.sock.sendto(pkt_quit(), self.parent)
            except OSError:
                pass


# ----------------------------------------------------------------------------
# autopunch: リレーから NAT ポートを引く (asobby と同じ手順)
# ----------------------------------------------------------------------------
def autopunch_nat_port(
    sock: socket.socket, host: tuple[str, int]
) -> tuple[int, tuple[str, int]] | None:
    """リレーへ lookup を送り (NAT ポート, リレーアドレス) を返す。

    lookup を受けたリレーはホスト側 DLL にもこちらのアドレスを通知するので、
    ホストからのホールパンチも同時に始まる。
    """
    my_port = sock.getsockname()[1]
    try:
        relay_ip = socket.gethostbyname(AUTOPUNCH_RELAY[0])
    except OSError:
        return None
    relay = (relay_ip, AUTOPUNCH_RELAY[1])
    lookup = struct.pack("!H", my_port) + socket.inet_aton(host[0]) + struct.pack("!H", host[1])
    for _ in range(3):
        try:
            sock.sendto(lookup, relay)
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                sock.settimeout(deadline - time.monotonic())
                data, addr = sock.recvfrom(4096)
                if addr[0] != relay_ip or len(data) != 8:
                    continue
                nat_port = struct.unpack("!H", data[2:4])[0]
                if socket.inet_ntoa(data[4:8]) == host[0]:
                    return nat_port, relay
        except OSError:
            pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="非想天則ホストのリプレイを観戦接続で取得する")
    parser.add_argument("ipport", help="ホストの IP:Port (例 1.2.3.4:10800)")
    parser.add_argument("--autopunch", action="store_true",
                        help="autopunch ホストに対しリレーで NAT ポートを解決してから接続する")
    parser.add_argument("--out", default=".", help="保存先ディレクトリ (default: カレント)")
    parser.add_argument("--once", action="store_true", help="1 試合保存したら終了する")
    parser.add_argument("-v", "--verbose", action="store_true", help="デバッグログを出す")
    args = parser.parse_args()

    ip, _, port_s = args.ipport.partition(":")
    try:
        host = (socket.gethostbyname(ip), int(port_s))
    except (OSError, ValueError):
        parser.error(f"invalid IP:Port: {args.ipport}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = Spectator(host, out_dir, args.verbose)
    if args.autopunch:
        result = autopunch_nat_port(spec.sock, host)
        spec.sock.settimeout(0.05)
        if result is None:
            spec.log("autopunch リレーから NAT ポートを解決できませんでした")
            raise SystemExit(1)
        nat_port, relay = result
        spec.log(f"autopunch NAT port: {nat_port}")
        spec.host = (host[0], nat_port)
        # NAT ポートで届かないルータもあるので内部ポートにも並行プローブする
        spec.probe_targets = [(host[0], nat_port), host]
        spec.relay = relay
        spec.last_relay_send = time.monotonic()

    try:
        spec.run(once=args.once)
    except KeyboardInterrupt:
        spec.quit()
        print("\nbye")


if __name__ == "__main__":
    main()
