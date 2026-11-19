# Buyer research project

This folder is an insights project. We collect public posts from the people who buy in one
category, read them without bias, code them against a codebook, rank what matters, and turn
it into persona packs, a message bank, a hook bank and a small test.

The study question is in `brief.md`. Read it at the start of every session.

## Rules for every session

1. **Counts come from scripts only.** Never type a number you didn't read from a script's
   output in this session. If a number is needed and no script gives it, say so.
2. **Stay blind until Phase 4.** Don't ask what the user sells, what they believe about their
   buyers, or which audience they hope for. If they offer it, say: "Save that for Phase 4, so
   it can't steer what I find." `brief.md` says who and where to study, and that's all you need.
3. **Never quote a person in anything meant for publishing.** Paraphrase. A phrase used by 5 or
   more different people (check with `scripts/phrases.py`) is fine to use word for word.
4. **Never name or identify anyone.** Usernames are already replaced by ids in the corpus.
   Don't try to work out who someone is.
5. **Collect only through the scripts.** Reddit goes through `scripts/collect_reddit.py`, which
   uses the free Arctic Shift archive and paces itself. Never fetch reddit.com directly.
   TikTok and Instagram go through `scripts/collect_social.py`, which costs money: run it
   without `--yes` first, show the user the cost line, and add `--yes` only after they say yes.
6. **Sub-agents write files; you don't edit them.** Coding agents write to `labels/`. Never
   change a label file by hand. If a batch is wrong, re-run that batch.
7. **At most 8 sub-agents at once.** More than that gets throttled and wastes the user's usage.
   If agents start failing with "temporarily limiting requests", stop, wait 10 minutes, and
   restart at 4.
8. **Judge each person yourself.** When coding or reading, never write a keyword script to do
   the judging. Scripts count; agents judge.
9. **Save before you clear.** Write any brief, plan or instruction to a file before the user
   runs `/clear`, so nothing has to be reconstructed.

## Folder map

| Folder or file | What's in it |
|---|---|
| `brief.md` | The study question, who to study, where, and the stop rule (Phase 1) |
| `mode.txt` | `problem` or `moment` (Phase 1) |
| `data/raw/` | What the collectors downloaded. Never edit it |
| `data/corpus/v<N>/` | Clean, versioned corpus: `rows.parquet` and `manifest.json` |
| `samples/` | People drawn for reading and coding, with seeds in `log.csv` |
| `readers/` | Themes proposed by the reader agents (Phase 3) |
| `codebook.md`, `codebook.json` | The codebook, in words and as a code list (Phase 3) |
| `batches/`, `labels/`, `coded/` | Coding inputs, agent outputs, merged results |
| `agreement/` | Agreement reports |
| `ranking.csv`, `phrases.csv` | Ranked codes and phrase counts (Phase 4) |
| `packs/` | Persona packs (Phase 4) |
| `hooks/` | Posts, scores, transcripts and templates for the hook bank (Phase 5) |
| `positioning.md`, `message-bank.md`, `channels.md`, `briefs/` | Activation work (Phase 5) |
| `tests/`, `interviews/`, `price.md`, `decision.md` | Validation work (Phase 6) |
| `phase0/` | Your first readout. Claude can't read it, because it mentions what you sell |

## Scripts

Run every script as `uv run scripts/<name>.py`. Each one prints `--help`.

| Script | What it does |
|---|---|
| `browse.py` | How busy each candidate subreddit is, and 8 posts from it |
| `collect_reddit.py` | Collect posts and comments from one subreddit (free, paced, resumable) |
| `collect_social.py` | Collect TikTok or Instagram comments or posts through Apify (costs money) |
| `clean.py` | Build a new corpus version from everything collected |
| `sample.py` | Draw people, or top posts, for reading and coding |
| `batches.py` | Split a sample into batches of about 25 people |
| `merge.py` | Check coded batches against their input and merge them |
| `checkset.py` | Draw a check set for a second, independent coder |
| `agreement.py` | Cohen's kappa between the coder and the checker |
| `rank.py` | Rank codes by the mode's formula |
| `phrases.py` | Count how many different people use each phrase |
| `score_posts.py` | Score posts against their neighbours, to find real outliers |
| `transcribe.py` | Transcribe the opening of top posts locally, for free |
| `peek.py` | Show a few random rows from the newest corpus |
| `channels.py` | Count where one group of people posts |
| `youtube_posts.py` | List a YouTube channel's posts with view counts, for free |
| `templates.py` | Count each hook template and its median score |
| `price_range.py` | Work out a price range from Van Westendorp's four questions |

## Agents

| Agent | Model | Job |
|---|---|---|
| `reader` | Opus | Reads a discovery batch and proposes themes in the members' own terms |
| `coder` | Sonnet | Codes one batch against the codebook |
| `checker` | Opus | Codes a check batch from the codebook alone, without seeing the coder's labels |
