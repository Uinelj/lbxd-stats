from scraper import popular_movies, score, PopularPeriod, popular_movies_v2
import toml
import logging
import random
from utils import DateTimeEncoder


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

watchlist_path = "res/watchlist.toml"
measures_path = "res/measures.jsonl"

# we want to have everything updated at least once a week (=168h)
# we update each 12 hours
# we update 14 times each week
# we want each movie to have a 1/14th chance of being updated
# we want to update 1/14th of the whole movieset (= len(watchlist) * 1/14).
#
# One drawback: we add movies to the watchlist
# at each refresh so idk if we should account for that.. not sure

# put here the time (in hours) between 2 runs
update_period = 12.0

# put here the time (in hours) when you want
# each film to have a 1 probability of being updated
full_update_period = 168.0

# put here the minimum number of movies to update at each run
min_number_updates = 10

prob_query = update_period / full_update_period


class Watchlist:
    def __init__(self, path):
        self.path = path
        self.watchlist = toml.load(path)
        log.info(f"watchlist len: {len(self)}")

    def save(self):
        len(self.watchlist["movies"])
        self.watchlist["movies"] = set(self.watchlist["movies"])
        log.info(f"watchlist len: {len(self)}")
        len(self.watchlist["movies"])
        with open(self.path, "w") as f:
            toml.dump(self.watchlist, f)

    def add(self, movieid):
        log.info(f"adding {movieid} to watchlist")
        self.watchlist["movies"].append(movieid)

    def add_multiple(self, movieids):
        self.watchlist["movies"].extend(movieids)

    def getn(self, n):
        log.info(f"getting {n} movies from watchlist")
        return self.watchlist["movies"][:n]

    def __len__(self):
        return len(self.watchlist["movies"])

    def shuffle(self):
        log.info("shuffling watchlist")
        random.shuffle(self.watchlist)


class Measures:
    def __init__(self, path):
        self.path = path
        self.measures = list()
        pass

    def query_add(self, movieid):
        m = score(movieid)
        self.measures.append(m)
        return m

    def append_to_file(self):
        with open(self.path, "a+") as f:
            log.info(f"adding {len(self.measures)} new measures")
            for measure in self.measures:
                ser = DateTimeEncoder().encode(measure)
                # ser = json.dumps(measure)
                f.writelines(ser + "\n")


if __name__ == "__main__":
    log.info("hello")
    # load watchlist
    wl = Watchlist(watchlist_path)
    m = Measures(measures_path)

    # get popular movies
    new_movies = popular_movies()
    new_movies.extend(popular_movies_v2(PopularPeriod.Week))
    new_movies.extend(popular_movies_v2(PopularPeriod.Month))
    new_movies.extend(popular_movies_v2(PopularPeriod.Year))
    new_movies.extend(popular_movies_v2(PopularPeriod.AllTime))

    # query measures for new movies
    for movieid in new_movies:
        m.query_add(movieid)

    # query measures for old movies

    nb_query = int(prob_query * len(wl))
    if nb_query < min_number_updates:
        log.info(f"computed query number too short, using {min_number_updates}.")
        nb_query = min_number_updates
    log.info(f"updating {nb_query} movies")
    for movieid in wl.getn(nb_query):
        m.query_add(movieid)

    # add new movies to watchlist
    wl.add_multiple(new_movies)

    # shuffle list
    wl.shuffle()

    wl.save()
    m.append_to_file()
