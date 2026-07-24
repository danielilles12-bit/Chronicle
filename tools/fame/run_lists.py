from list_sources import SOURCES
from harvest_lists import run_sources

if __name__ == "__main__":
    run_sources(SOURCES, "lists_raw.json")
