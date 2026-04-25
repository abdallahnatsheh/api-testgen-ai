# PokéAPI — GET /api/v2/pokemon/{name}

Returns full data for a Pokémon by name or numeric ID.

## Success response (200)
Content-Type: application/json; charset=utf-8

Top-level fields:
- id: integer (e.g. 25)
- name: string (e.g. "pikachu")
- base_experience: integer
- height: integer
- weight: integer
- is_default: boolean
- order: integer
- abilities: array of { ability: { name: string, url: string }, is_hidden: boolean, slot: integer }
- types: array of { slot: integer, type: { name: string, url: string } }
- stats: array of { base_stat: integer, effort: integer, stat: { name: string, url: string } }
- sprites: object with keys front_default, back_default, front_shiny, back_shiny (strings or null)
- species: { name: string, url: string }
- forms: array of { name: string, url: string }
- moves: array of objects
- cries: { latest: string, legacy: string }

## Error responses
- 404: name/id not found — Content-Type: text/plain; charset=utf-8, body: "Not Found"
- 400: invalid characters in name — Content-Type: text/plain; charset=utf-8, body: "Bad Request"
- Wrong HTTP methods (POST, PUT, DELETE): returns 404, NOT 405

## Notes
- Valid examples: pikachu, charizard, bulbasaur, ditto, 1, 25
- Invalid examples: "unknownxyz", "pika chu!" (space+special chars)
- Numeric IDs work (e.g. /api/v2/pokemon/25 returns pikachu)
- No authentication required
- Do NOT assert Content-Type for 404/400 responses (it's text/plain, not JSON)
- Do NOT assert 405 for wrong HTTP methods (API returns 404 instead)
