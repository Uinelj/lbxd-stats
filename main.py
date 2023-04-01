from scraper import popular_movies, score, PopularPeriod, popular_movies_v2
from movie_info import MovieInfo, MovieNotFound
import front
import logging
from utils import DateTimeEncoder
from watchlist import Watchlist

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

watchlist_path = "res/watchlist_new.json"
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


class Measures:
    def __init__(self, path):
        self.path = path
        self.measures = list()
        pass

    def query_add(self, movieid):
        m = score(movieid)

        if m is not None:
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
    mi = MovieInfo()
    # keep trace of movies where we got new measures
    updated_movies = list()

    # get popular movies
    pop_movies = popular_movies()
    pop_movies.extend(popular_movies_v2(PopularPeriod.Week))
    pop_movies.extend(popular_movies_v2(PopularPeriod.Month))
    pop_movies.extend(popular_movies_v2(PopularPeriod.Year))
    pop_movies.extend(popular_movies_v2(PopularPeriod.AllTime))

    # convert to set to remove duplicates
    pop_movies = set(pop_movies)
    # TODO: ensure that new movies were not yet present

    # query measures for new movies that are not yet watchlisted
    for movieid in filter(lambda newmovie: not wl.contains(newmovie), pop_movies):
        log.info(f"New movie monitored: {movieid}")
        m.query_add(movieid)
        mi.refresh(movieid)
        updated_movies.append(movieid)

    # query measures for old movies
    nb_query = int(prob_query * len(wl))
    if nb_query < min_number_updates:
        log.info(
            f"computed query number too short ({nb_query}), using {min_number_updates}."
        )
        nb_query = min_number_updates
    log.info(f"updating {nb_query} movies")
    for movieid in wl.getn(nb_query):
        m.query_add(movieid)
        updated_movies.append(movieid)

    # add new movies to watchlist
    def getid(movie):
        try:
            movie_title = mi.get_update(movie)["title"]
        except MovieNotFound:
            movie_title = movie
        return (movie, movie_title)

    pop_movies = map(lambda movie: getid(movie), pop_movies)

    wl.add_multiple(pop_movies)

    # shuffle list
    # wl.shuffle()

    # save watchlist and measures
    wl.save()
    m.append_to_file()

    # gen graph info
    front.gen_graph_info(updated_movies)
