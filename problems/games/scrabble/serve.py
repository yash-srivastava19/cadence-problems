"""A game against the bot in the browser: play.html plus a small JSON API.

    uv run --with numpy python -m scrabble.engine serve --port 8765

    GET  /                 the page
    GET  /api/state        the game as you see it
    POST /api/new          {"seed": 1, "you_first": true, "player": "steady"}
    POST /api/move         {"move": "8H WORD"} or {"tiles": [[row, col, "A", false], ...]}
    POST /api/hint         the bot's top moves for your rack
    POST /api/analyse      {"cgp": "...", "top": 5, "time": 2.0}

One game at a time, one request at a time: the players keep module state.
The state never holds the bot's rack or the bag, only what you may see:
the leaves in the bot's top moves would give its rack away, so they are
left out until the game is over.
"""

import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from scrabble import engine
from scrabble.game import Game

PAGE = Path(__file__).with_name("play.html")


class Session:
    def __init__(self, name: str, seed: int, you_first: bool):
        engine.player(name)
        self.name, self.seed = name, seed
        self.g = Game(engine.rules(), seed)
        self.you = 0 if you_first else 1
        self.log: list[dict] = []
        self.bot: dict | None = None
        self.last = None
        self.reply()

    def apply(self, who: str, move, took: float | None = None) -> None:
        self.g.apply(move)
        self.last = move
        self.log.append({"who": who, "move": engine.notation(move), "score": move.score,
                         "scores": list(self.g.scores), "time": took})

    def reply(self) -> None:
        if not self.g.over and self.g.to_move != self.you:
            a = engine.from_view(self.name, self.g, top=8, seed=self.seed)
            self.bot = engine.public(a)
            self.apply("bot", a["best"], a["time"])

    def move(self, body: dict) -> None:
        if self.g.over:
            raise ValueError("the game is over: start a new one")
        moves = self.g.legal()
        if "tiles" in body:
            want = sorted((int(r), int(c), str(t).upper(), bool(b)) for r, c, t, b in body["tiles"])
            found = [m for m in moves if m.kind == "play" and sorted(m.tiles) == want]
            if not found:
                raise ValueError("those tiles do not make a legal play")
            move = found[0]
        else:
            move = engine.parse_move(str(body.get("move", "")), moves, self.g.rs)
        self.apply("you", move)
        self.reply()

    def state(self) -> dict:
        g, rs = self.g, self.g.rs
        out = {
            "player": self.name, "seed": self.seed, "you": self.you,
            "premiums": list(rs.premiums), "values": rs.values,
            "grid": g.grid, "rack": g.racks[self.you], "scores": g.scores,
            "bag": len(g.bag), "held": len(g.racks[1 - self.you]),
            "to_move": g.to_move, "over": g.over, "end": g.end,
            "log": self.log, "bot": self.bot if g.over or not self.bot else
            self.bot | {"moves": [{k: v for k, v in m.items() if k != "leave"} for m in self.bot["moves"]]},
            "last": [[r, c] for r, c, _, _ in self.last.tiles] if self.last else [],
        }
        if g.over:
            out["bot_rack"] = g.racks[1 - self.you]
        return out


def run(port: int, name: str) -> None:
    session = {"now": None}

    class Handler(BaseHTTPRequestHandler):
        def send(self, code: int, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                if session["now"] is None:
                    session["now"] = Session(name, random.randrange(10**6), True)
                self.send(200, session["now"].state())
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise TypeError("send a JSON object")
                if self.path == "/api/new":
                    session["now"] = Session(body.get("player") or name,
                                             int(body.get("seed") or random.randrange(10**6)),
                                             bool(body.get("you_first", True)))
                    self.send(200, session["now"].state())
                elif self.path == "/api/move":
                    if session["now"] is None:
                        raise ValueError("no game: POST /api/new first")
                    session["now"].move(body)
                    self.send(200, session["now"].state())
                elif self.path == "/api/hint":
                    s = session["now"]
                    if s is None or s.g.over:
                        raise ValueError("no game in progress")
                    self.send(200, engine.public(engine.from_view(s.name, s.g, top=8, seed=s.seed)))
                elif self.path == "/api/analyse":
                    rs = engine.rules()
                    g = engine.rebuild(rs, engine.position(rs, str(body.get("cgp", ""))), 0)
                    t = body.get("time")
                    a = engine.analyse(body.get("player") or name, g, int(body.get("top", 5)),
                                       float(t) if t is not None else None)
                    self.send(200, engine.public(a))
                else:
                    self.send(404, {"error": "not found"})
            except (ValueError, TypeError, KeyError) as e:
                self.send(400, {"error": str(e)})
            except Exception as e:  # noqa: BLE001 - say what broke instead of dropping the connection
                self.send(500, {"error": f"{type(e).__name__}: {e}"})

    engine.player(name)
    engine.rules()
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"playing {name} at http://127.0.0.1:{port}/  (ctrl-c to stop)", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
