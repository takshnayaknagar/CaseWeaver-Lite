# CaseWeaver Lite Timeline Engine

Extracts events from witness statements, validates source quotations, sorts events chronologically, and supports non-mutating What-If time adjustments.

## Functions
- extract_events(case_data)
- sort_events(events)
- sort_events_with_adjustments(events, adjusted_times)
- validate_event(event, statements_by_id)

## Integration
Requires the shared core.gemma_client.ask_gemma(prompt) function to return a JSON array. Coordinate the schema with the integration developer.

## Tests
Run: python -m pytest -v

Extraction tests use a mocked Gemma client; live Ollama integration remains to be verified.
