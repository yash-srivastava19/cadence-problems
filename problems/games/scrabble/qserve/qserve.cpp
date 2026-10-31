// Quackle as a move server for scrabble.quackle.
//
//   qserve <player name> <seconds per turn or 0> <inferring 0|1>
//
// Each request is a GCG of the game so far, then four lines, then END:
//   SEED <n>         seeds Quackle's random numbers, so a position always gets the same move
//   ME <id>          Quackle's player id (0 moves first)
//   RACK <tiles>     Quackle's rack, ? for a blank
//   UNSEEN <tiles>   every tile not on the board and not on Quackle's rack
//   OPP <n>          tiles on the opponent's rack
//   END
// The opponent's real rack is never sent. When the bag is not empty Quackle
// is given a random guess of the right size, so its bag count is right; with
// the bag empty the unseen tiles are the opponent's rack, as in a real game.
// Reply: MOVE <kind> <where> <tiles> <score> <my score> <their score> <moves rescored> <1 if its first choice was an illegal exchange>.

#include <QtCore>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>
#include <iostream>
#include <sstream>
#include <string>

#include <computerplayer.h>
#include <computerplayercollection.h>
#include <datamanager.h>
#include <game.h>
#include <lexiconparameters.h>
#include <strategyparameters.h>
#include <boardparameters.h>
#include "trademarkedboards.h"
#include <quackleio/flexiblealphabet.h>
#include <quackleio/gcgio.h>
#include <quackleio/util.h>

using namespace std;
using QuackleIO::Util;

static Quackle::LetterString encoded(const string &s) { return Util::encode(QString::fromStdString(s)); }

static Quackle::Bag bagOf(const string &s)
{
	Quackle::LongLetterString tiles;
	for (char c : s) tiles += encoded(string(1, c))[0];
	Quackle::Bag bag{Quackle::LetterString()};
	bag.toss(tiles);
	return bag;
}

int main(int argc, char **argv)
{
	QCoreApplication app(argc, argv);
	// Quackle talks on stdout; replies get their own copy of it.
	FILE *reply = fdopen(dup(1), "w");
	dup2(open("/dev/null", O_WRONLY), 1);
	if (argc != 4) { cerr << "usage: qserve <player> <seconds|0> <inferring>" << endl; return 2; }

	Quackle::DataManager dm;
	dm.setComputerPlayers(Quackle::ComputerPlayerCollection::fullCollection());
	dm.setAppDataDirectory("../data");
	auto *abc = new QuackleIO::FlexibleAlphabetParameters;
	if (!abc->load(QString::fromStdString(Quackle::AlphabetParameters::findAlphabetFile("english")))) { cerr << "no alphabet" << endl; return 2; }
	dm.setAlphabetParameters(abc);
	dm.setBoardParameters(new ScrabbleBoard());
	dm.lexiconParameters()->loadDawg(Quackle::LexiconParameters::findDictionaryFile("enable.dawg"));
	dm.lexiconParameters()->loadGaddag(Quackle::LexiconParameters::findDictionaryFile("enable.gaddag"));
	dm.setBackupLexicon("default_english");
	dm.strategyParameters()->initialize("enable");

	bool found = false;
	Quackle::ComputerPlayer *player = dm.computerPlayers().playerForName(argv[1], found).computerPlayer();
	if (!found) { cerr << "no player " << argv[1] << endl; return 2; }
	player = player->clone();
	if (atoi(argv[2]) > 0) player->setParameters({atoi(argv[2]), atoi(argv[3]) != 0});
	player->setThreadCount(1, player->threadQoS());
	const auto *sp = dm.strategyParameters();
	fprintf(reply, "READY %s superleaves=%d syn2=%d worths=%d vcplace=%d bogowin=%d\n", player->name().c_str(),
	        sp->hasSuperleaves(), sp->hasSyn2(), sp->hasWorths(), sp->hasVcPlace(), sp->hasBogowin());
	fflush(reply);

	string line;
	while (true)
	{
		QString gcg;
		string rack, unseen;
		int me = -1, opp = 0;
		unsigned seed = 0;
		bool got = false;
		while (getline(cin, line))
		{
			if (line == "END") { got = true; break; }
			istringstream in(line);
			string key; in >> key;
			if (key == "SEED") in >> seed;
			else if (key == "ME") in >> me;
			else if (key == "RACK") in >> rack;
			else if (key == "UNSEEN") in >> unseen;
			else if (key == "OPP") in >> opp;
			else gcg += QString::fromStdString(line) + "\n";
		}
		if (!got) return 0;

		dm.seedRandomNumbers(seed);
		QTextStream stream(&gcg);
		QuackleIO::GCGIO io;
		Quackle::Game *game = io.read(stream, QuackleIO::Logania::MaintainBoardPreparation);
		if (game->players().size() != 2)  // no moves yet: the reader left its one dummy player
		{
			delete game;
			game = new Quackle::Game;
			Quackle::PlayerList players;
			players.push_back(Quackle::Player(MARK_UV("p0"), Quackle::Player::ComputerPlayerType, 0));
			players.push_back(Quackle::Player(MARK_UV("p1"), Quackle::Player::ComputerPlayerType, 1));
			game->setPlayers(players);
			game->addPosition();
		}
		else if (game->currentPosition().moveMade().isAMove())
			game->commitCandidate(true);

		// GCG scores that Quackle disagrees with become score additions: count them
		int rescored = 0;
		for (const auto &past : game->history())
			if (past.committedMove().isAMove() && past.committedMove().scoreAddition() != 0)
				++rescored;

		Quackle::GamePosition &pos = game->currentPosition();
		if (pos.currentPlayer().id() != me)
		{
			fprintf(reply, "ERROR turn %d not %d\n", pos.currentPlayer().id(), me);
			fflush(reply);
			delete game;
			continue;
		}

		Quackle::Bag left = bagOf(unseen);
		Quackle::LetterString theirs;
		if ((int)left.size() <= opp)
			theirs = encoded(unseen), left = bagOf("");
		else
			while ((int)theirs.length() < opp) theirs.push_back(left.pluck());
		pos.setBag(left);
		pos.setCurrentPlayerRack(Quackle::Rack(encoded(rack)), false);
		pos.setOppRack(Quackle::Rack(theirs), false);

		player->setPosition(pos);
		// Quackle's endgame code can rank an exchange first with under 7 in the bag, which its
		// own rules forbid: only then ask for its ranking and take the best legal move, and say
		// so. Asking for more moves every turn would change how much it sims.
		Quackle::Move m = player->move();
		int skipped = 0;
		if (m.action == Quackle::Move::Exchange && !pos.exchangeAllowed())
		{
			skipped = 1;
			player->setPosition(pos);
			Quackle::MoveList ranked = player->moves(10);
			m = Quackle::Move::createPassMove();
			for (const auto &candidate : ranked)
			{
				if (candidate.action == Quackle::Move::Exchange) continue;
				m = candidate;
				break;
			}
		}
		const char *kind = m.action == Quackle::Move::Place ? "play" : m.action == Quackle::Move::Exchange ? "exch" : "pass";
		string where = m.action == Quackle::Move::Place ? m.positionString() : "-";
		string tiles = Util::qstringToStdString(Util::letterStringToQString(m.tiles()));
		if (tiles.empty()) tiles = "-";
		int mine = pos.currentPlayer().score(), other = 0;
		for (const auto &p : pos.players()) if (p.id() != me) other = p.score();
		fprintf(reply, "MOVE %s %s %s %d %d %d %d %d\n", kind, where.c_str(), tiles.c_str(), m.score, mine, other, rescored, skipped);
		fflush(reply);
		delete game;
	}
}
