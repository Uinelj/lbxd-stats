import sys
from scraper import parse_list
from watchlist import Watchlist
from main import Measures
from movie_info import MovieInfo, MovieNotFound

watchlist_path = "res/watchlist_new.json"
measures_path = "res/measures.jsonl"


# add new movies to watchlist
# copied from main 😬
def getid(movie):
    try:
        movie_title = mi.get_update(movie)["title"]
    except (MovieNotFound, TypeError) as e:
        print(e)
        movie_title = movie
    return (movie, movie_title)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_from_list.py LIST_URL")
        sys.exit(1)

    # load watchlist and measures
    # get movies from list
    # if they're not in watchlist, add them and add first measure
    # done :)

    wl = Watchlist(watchlist_path)
    m = Measures(measures_path)
    mi = MovieInfo()
    list_url = sys.argv[1]
    print(f"getting from list {list_url}")
    movies_from_list = parse_list(list_url)
    new_movies = list(filter(lambda movie: not wl.contains(movie), movies_from_list))
    print(f"got {len(new_movies)}/{len(movies_from_list)} new movies")
    for movie in new_movies:
        print(f"adding {movie} rating and info")
        m.query_add(movie)
        mi.refresh(movie)
    print("Adding to watchlist")
    wl.add_multiple(map(lambda movie: getid(movie), new_movies))

    wl.save()
    m.append_to_file()
    print("✨ done!")
