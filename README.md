# NovelCompass Static Recommendation Dataset

This repository contains the normalized, pre-computed static JSON projection dataset for the [NovelCompass](https://github.com/cbangera2/NovelCompass) web application covering 30,696 web novels (generated 2026-07-26).

## Dataset Structure

- `manifest.json`: schema/algorithm/dataset versions, generation timestamp, novel counts, and file URLs.
- `catalog.json`: full catalog search index (30,696 novels: titles, authors, ratings, genres, tags, status, chapters).
- `facets.json`: genre/tag taxonomies plus a per-novel genre/tag index.
- `options.json`: UI drop-down filter definitions (genres, tags, languages, statuses).
- `details/`: 256 bucket JSON files (`00.json` to `ff.json`) with per-novel detail records (synopsis, rating breakdown, tag/genre ids, recommendation counts).
- `recommendation-index/`: 256 compact bucket JSON files (`00.json` to `ff.json`) with per-novel recommendation candidate pools (up to 50 candidates each).
- `bootstrap-catalog.json`: leftover small fast-load catalog subset from an earlier bounded export; not referenced by the current manifest.

## Algorithm

The compact recommendation index is computed per novel from four populated channels (a fifth, `vector`, is reserved and empty in the compact index):

- `tag`: IDF-weighted tag overlap (Jaccard over tag weights, with priority-tag boost).
- `direct_rec`: direct recommendations between novels, weighted by votes and mutual links.
- `rec_list`: novels co-occurring on curated recommendation lists.
- `structural`: same author, related series, plus genre peers as a fallback for sparsely linked titles.

Candidates are ranked by how many channels they appear in, ties broken by best channel rank and novel id. Each pool also carries the shared tag ids used as evidence.

Published for use with [NovelCompass](https://github.com/cbangera2/NovelCompass).
