# Import a blog on behalf of its author

`scripts/migrate_legacy_blogs_to_ublog.py` imports into the current `ublog_post2`
collection. It defaults to a dry run without connecting to MongoDB. Existing posts
are skipped, preserving browser edits, publication state, views, and likes.

For a Markdown file that is absent from `server/blog_legacy_metadata.json`, provide
the author's exact PyChess username and explicit metadata. For example:

```bash
env PYTHONPATH=server uv run python scripts/migrate_legacy_blogs_to_ublog.py \
  --markdown-file 'static/blogs/Yokai Halloween.md' \
  --author CouchTomato87 \
  --title 'Yokai Shogi Arrives for Halloween!' \
  --intro 'New variants' \
  --date 2026-10-31 \
  --image /static/images/Hyakki.jpg \
  --image-alt 'Yokai parade' \
  --topics announcement,shogi \
  --official --sticky --publish
```

Review the preview, set `MONGO_HOST` in your environment to the production MongoDB
URI, and repeat with `--apply` to write. The database defaults to `pychess-variants`;
use `--mongo-db` to override it. The author must already have an enabled account.
Run the command from a checkout containing the intended version of the Markdown
file and its images.

Omit `--publish` to create an unpublished draft owned by the author. With
`--publish`, the post becomes visible immediately; `--date` sets its date and does
not schedule publication. Choose the intended date explicitly: dates embedded in
the old HTML preamble are discarded. `--official` includes the post in the site
blog stream while retaining the supplied author. Add `--sticky` to pin it above
unpinned posts. The lobby shows only three site posts, with pinned posts first,
so existing pins can otherwise push a new announcement out of the lobby.
This utility does not emit a follower timeline event or create a discussion topic.

The file name determines the stable legacy ID (`Yokai_Halloween` above). Use
`--blog-id` with a file to override that ID, or use `--blog-id ID` alone to select
exactly one existing catalog entry. Without either selector, the script imports
the legacy catalog, with optional `--from-id`, `--limit`, and `--author-policy`.
Legacy HTML is converted to the strict Markdown format used by the current site.
