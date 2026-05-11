# NewsSnek Provider Chain & Deployment - Progress Tracker

## Goal
Implement named providers with chain fallback, refactor for clean deployment (Docker/GitHub), and verify routing via dedicated channel/provider mappings.

## Current State (as of 2026-05-07 16:25 MDT)
- [x] **Provider Infrastructure**: Base `Provider` class, `OllamaProvider`, `OpenRouterProvider`, and `ProviderChain` implemented.
- [x] **Runtime Config**: `NewsReaderConfig` successfully reloads settings/sources on each access.
- [x] **Channel/Provider Routing**: `sources.json` now defines specific `providers` and `channels` per group. `settings.json` defines global provider and channel definitions.
- [x] **UI/Labeling**: Labels updated from "Source:" to "Channel:".
- [x] **YouTube Support**: High-res thumbnail extraction (`maxresdefault.jpg`) implemented.
- [x] **Data Extraction**: Improved content extraction and implemented fallback to Internet Archive.
- [x] **Deployment Readiness**: `Dockerfile`, `docker-entrypoint.sh`, `docker-compose.yml`, and `.gitignore` updated for GitHub/Docker deployment.
- [x] **Testing**: Verified end-to-end processing (Extraction -> Summarization -> Discord/Console) with OpenRouter (via testing placeholder) and Ollama providers.

## TODO List

### Phase 1: Final Deployment Polish
- [ ] Step 1.1: Verify `sources.json` and `settings.json` structure for production-ready routing.
- [ ] Step 1.2: Finalize `README.md` for GitHub users (Docker instructions/config patterns).
- [ ] Step 1.3: Finalize `.gitignore` (ensure all sensitive/output files are covered).

### Phase 2: Production Switch (Manual)
- [ ] Step 2.1: User replaces "test" routing with real production channel names/IDs in `sources.json`.
- [ ] Step 2.2: User wipes/resets production `news_reader.db` to clear old history.
- [ ] Step 2.3: Deploy updated config/code and start continuous loop.

## Decisions Made
- **Source vs. Channel**: `source` param in dispatch now represents the *publisher* (e.g., "NY Post") for article content, but can be configured to show the *group/channel* in `--debug` mode.
- **Routing Architecture**: `settings.json` holds "Tools" (Providers) and "Destinations" (Channels). `sources.json` holds "Jobs" (Groups) that link tools to destinations.
- **Deployment**: Uses Docker with volume mounting for persistence of the SQLite DB and JSON configs.

## Next Step
Final validation of the current "everything-is-linked" state.


### Session Wrap-up (2026-05-07)
- [x] Verified routing via `test` channel for all groups
- [x] Implemented `<think>` tag stripping for all output channels
- [x] Implemented error-summary filtering to prevent spamming channels with extraction errors
- [x] Cleared orphaned background processes

## Session 2026-05-08: Source Attribution & YouTube Channel Names

### Changes Made
- [x] **Source Attribution for Overviews**: Modified `generate_daily_overview` in `newsnek.py` to collect source list from DB and pass to `send_overview` calls. Updated `ConsoleOutputChannel.send_overview` and `DiscordOutputChannel.send_overview` in `src/output_channels.py` to accept `sources` parameter and prepend "Sources: ..." line to overview output.
- [x] **Console Output for Individual Summaries**: Added `send_summary` method to `ConsoleOutputChannel` class in `src/output_channels.py` to properly output per-article summaries with Source, Title, Author, Summary, and URL fields.
- [x] **YouTube Channel Names**: Updated `_get_publisher_name` in `newsnek.py` to accept an `author` parameter. For YouTube URLs, it now uses the author/channel name from the RSS feed instead of just displaying "YouTube".
- [x] **Generic Domain Handling**: Made domain parsing more generic - only hardcodes a few common domains (NY Post, Hackaday, Ars Technica, ZDNet, Bleeping Computer), falls back to capitalizing the main domain name for everything else.

### Current Issue
- None. All major dispatch errors resolved.

### Next Steps
- Verify end-to-end source attribution for YouTube channel names in the final output.
- Test the aggregated overview generation with real-world data.
- Commit all current changes to the git repository.
- Test YouTube channel name extraction (TimPool, etc.)
- Verify source attribution appears correctly in output files
