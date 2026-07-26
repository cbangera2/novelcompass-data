# NovelCompass Static Recommendation Dataset

This repository contains the normalized, pre-computed static JSON projection dataset for the [NovelCompass](https://github.com/cbangera2/NovelCompass) web application covering 24,791 web novels.

## Dataset Structure

- `catalog.json`: Full catalog search index (~24.7k novel metadata, titles, ratings, genres, tags).
- `facets.json`: Taxonomies, genre counts, and tag frequency indexes.
- `options.json`: UI drop-down filter definitions.
- `recommendation-index/`: 256 compact bucket JSON files (`00.json` to `ff.json`) providing candidate recommendation pointers for all 24.7k novels.
- `recs/`: Pre-computed rich recommendation candidate pools for top popular novels.
- `details/`: Individual novel detail JSON files.

## Algorithm Specifications

- Multi-source weighted tag similarity (IDF-weighted).
- Normalized rating distribution quantile transformations.
- Cosine vector similarity across pre-encoded synopsis embeddings (`all-MiniLM-L6-v2`).
- AniList recommendation upvote logarithmic scaling.

Published for use with [NovelCompass](https://github.com/cbangera2/NovelCompass).
