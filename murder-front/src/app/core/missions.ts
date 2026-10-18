/**
 * Default missions travel as catalogue keys (`core.01` … `core.30`) and are translated here;
 * custom missions travel as the literal text their author typed and are shown as is.
 * Mirrors murder-api/src/domain/missions.py.
 */
// Exact match, ASCII digits only: must agree character for character with the API's rule.
const CATALOGUE_KEY = /^core\.[0-9]+$/;

export function isCatalogueKey(mission: string): boolean {
  return CATALOGUE_KEY.test(mission);
}

/** The translation key for a catalogue mission, or null for a custom (literal) mission. */
export function missionTranslationKey(mission: string | null | undefined): string | null {
  return mission && isCatalogueKey(mission) ? `missions.${mission}` : null;
}
