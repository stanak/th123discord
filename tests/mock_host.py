#!/usr/bin/env python3
"""fetch_replay.py 検証用のモック親ノード。

実在の .rep から入力列とメタ情報を読み、観戦プロトコル
(HELLO/OLLEH, INIT, GAME_MATCH, GAME_REPLAY) で配信する。
プローブには REDIRECT で自分自身へ誘導し、パンチ経路も通す。

使い方: python tests/mock_host.py <replay.rep> [port] [noend] [ahead]
  noend: end_frame を一切送らない (救済保存パスの検証用)
  ahead: 一部の要求に対し要求位置より先の入力だけを返す (歯抜けガードの検証用)
"""
import socket
import struct
import sys
import zlib
from pathlib import Path

REP = Path(sys.argv[1]).read_bytes()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 10800
NO_END = "noend" in sys.argv[3:]
AHEAD = "ahead" in sys.argv[3:]

H = REP[:0x7B]
BODY = REP[0x7B:]
TOTAL_INPUTS = int.from_bytes(H[0x77:0x7B], "little")
MATCH_ID = 3  # 適当な試合番号

# 入力番号 1 始まり (Go 実装観測に合わせ、末尾番号 = TOTAL_INPUTS)
INPUTS = [BODY[2 * i: 2 * i + 2] for i in range(TOTAL_INPUTS)]


def sockaddr_in(ip: str, port: int) -> bytes:
    return b"\x02\x00" + struct.pack("!H", port) + socket.inet_aton(ip) + bytes(8)


def game_match_packet() -> bytes:
    def player(base: int) -> bytes:
        char, skin, size = H[base], H[base + 1], H[base + 2]
        deck = H[base + 6: base + 6 + 2 * size]
        simul = H[base + 0x30]
        return bytes([char, skin, 0, size]) + deck + bytes([simul])

    p1 = player(0x0E)
    p2 = player(0x3F)
    return (
        b"\x0d\x04" + p1 + p2
        + bytes([H[0x71], H[0x72]]) + H[0x73:0x77] + bytes([MATCH_ID])
    )


_req_count = 0


def replay_packet(req_from: int) -> bytes:
    # req_from = 観戦者が持っていない最小の入力番号 (1 始まり)
    global _req_count
    _req_count += 1
    per = 60  # 1 パケットの最大入力数
    if AHEAD and _req_count % 3 == 0:
        # 実ホストで観測される「要求より先の入力だけを含む応答」を模擬
        req_from = min(req_from + 300, TOTAL_INPUTS)
    hi = min(req_from + per - 1, TOTAL_INPUTS)
    if hi < req_from:
        hi = TOTAL_INPUTS
    lo = max(1, hi - per + 1)
    if req_from > TOTAL_INPUTS:
        lo, hi = TOTAL_INPUTS + 1, TOTAL_INPUTS  # 空
    chunk = b"".join(INPUTS[i - 1] for i in range(hi, lo - 1, -1))  # 降順
    n = hi - lo + 1 if hi >= lo else 0
    end = 0 if NO_END else (TOTAL_INPUTS if hi >= TOTAL_INPUTS else 0)
    raw = (
        hi.to_bytes(4, "little") + end.to_bytes(4, "little")
        + bytes([MATCH_ID, n & 0xFF]) + chunk
    )
    comp = zlib.compress(raw)
    return b"\x0d\x09" + bytes([len(comp) & 0xFF]) + comp


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", PORT))
    print(f"mock host on 127.0.0.1:{PORT}, {TOTAL_INPUTS} inputs", flush=True)
    probed = set()
    while True:
        data, addr = sock.recvfrom(4096)
        head = data[0]
        if head == 0x05:  # INIT_REQUEST
            if addr not in probed:
                # プローブ段階: REDIRECT で自分自身へ誘導 (punch 経路を通すため)
                probed.add(addr)
                pkt = (
                    b"\x08" + (1).to_bytes(4, "little")
                    + sockaddr_in("127.0.0.1", PORT) + bytes(48)
                )
                sock.sendto(pkt, addr)
            else:
                # INIT_SUCCESS (観戦者向け, プロファイル名つき)
                names = b"mockP1".ljust(32, b"\x00") + b"mockP2".ljust(32, b"\x00")
                pkt = (
                    b"\x06\x00\x00\x00\x00" + (0x11).to_bytes(4, "little")
                    + (68).to_bytes(2, "little") + b"\x00\x00"
                    + names + (0).to_bytes(4, "little")
                )
                sock.sendto(pkt, addr)
        elif head == 0x01:  # HELLO (punch 依頼 or 直接)
            sock.sendto(b"\x03", addr)  # OLLEH
        elif head == 0x0E and len(data) >= 7 and data[1] == 0x0B:
            frame = int.from_bytes(data[2:6], "little")
            req_match = data[6]
            if req_match != MATCH_ID or frame == 0xFFFFFFFF:
                sock.sendto(game_match_packet(), addr)
            else:
                sock.sendto(replay_packet(max(frame, 1)), addr)
        elif head == 0x0B:
            print("spectator quit", flush=True)


if __name__ == "__main__":
    main()
