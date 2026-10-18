import { Injectable, signal } from '@angular/core';

import { isCatalogueKey } from '../missions';

export interface CustomMission {
  id: string;
  text: string;
}

const KEY = 'murder.custom-missions';

/**
 * On-device library of the player's custom missions, persisted in localStorage (no account
 * needed — consistent with the mobile-ready guardrails and the Session service). Reused across
 * games; feeds the per-game mission pool (issue #13).
 */
@Injectable({ providedIn: 'root' })
export class MissionLibrary {
  readonly missions = signal<CustomMission[]>(this.read());

  /** Adds the mission; false when it is blank or shaped like a catalogue key (reserved). */
  add(text: string): boolean {
    const value = text.trim();
    if (!value || isCatalogueKey(value)) return false;
    this.persist([...this.missions(), { id: this.newId(), text: value }]);
    return true;
  }

  /** Same rules as `add`. */
  update(id: string, text: string): boolean {
    const value = text.trim();
    if (!value || isCatalogueKey(value)) return false;
    this.persist(this.missions().map((m) => (m.id === id ? { ...m, text: value } : m)));
    return true;
  }

  remove(id: string): void {
    this.persist(this.missions().filter((m) => m.id !== id));
  }

  private persist(next: CustomMission[]): void {
    this.missions.set(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Storage unavailable (private mode / WebView quirks) — keep the in-memory list.
    }
  }

  private read(): CustomMission[] {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as CustomMission[]) : [];
    } catch {
      return [];
    }
  }

  private newId(): string {
    return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
  }
}
