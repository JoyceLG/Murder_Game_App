import { Injectable, signal } from '@angular/core';

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

  add(text: string): void {
    const value = text.trim();
    if (!value) return;
    this.persist([...this.missions(), { id: this.newId(), text: value }]);
  }

  update(id: string, text: string): void {
    const value = text.trim();
    if (!value) return;
    this.persist(this.missions().map((m) => (m.id === id ? { ...m, text: value } : m)));
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
