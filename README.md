# Starter kit: The $100k Insights Manager You Can Run Yourself

The scripts, agents and settings that go with the free guide. Copy everything in this folder
into your `buyer-research` folder (Phase 1, step D of the guide).

- `CLAUDE.md`: the project rules Claude Code reads at the start of every session.
- `.claude/settings.json`: what Claude may do without asking, and what it may never read
  (your `.env` keys and the key that hides usernames).
- `.claude/agents/`: the reader (Opus), coder (Sonnet) and checker (Opus) sub-agents.
- `scripts/`: 18 small Python scripts. Run each with `uv run scripts/<name>.py --help`.
  uv installs Python and each script's packages the first time. Nothing else to install.
- `.env.example`: copy to `.env` if you use Apify for TikTok or Instagram.

Everything here is free to run except `collect_social.py`, which uses Apify and prints the
most it can cost before it runs. Reddit data comes from the free Arctic Shift archive.

Licence: MIT.
