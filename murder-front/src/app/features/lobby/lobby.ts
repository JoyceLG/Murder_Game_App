import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';

import { MissionMode } from '../../core/models/game.dto';
import { GameStore } from '../../core/services/game-store';
import { MissionLibrary } from '../../core/services/mission-library';
import { Session } from '../../core/services/session';
import { Toast } from '../../core/services/toast';
import { IdLine } from '../../shared/id-line/id-line';
import { Roster } from '../../shared/roster/roster';
import { Seal } from '../../shared/seal/seal';

@Component({
  selector: 'app-lobby',
  imports: [FormsModule, TranslocoPipe, IdLine, Roster, Seal],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state(); as s) {
      <app-id-line [name]="me()?.name ?? ''" [code]="s.code" />
      <div class="card">
        <h2>{{ 'lobby.waiting' | transloco }}</h2>
        <app-seal [code]="s.code" />
      </div>
      <div class="card">
        <h2>{{ 'lobby.recruited' | transloco: { count: s.players.length } }}</h2>
        <app-roster [players]="s.players" [meId]="playerId()" [hostId]="s.host_id" />
      </div>

      @if (isHost()) {
        <div class="card">
          <h2>{{ 'lobby.settings' | transloco }}</h2>
          <label class="field">
            <span class="lbl">{{ 'lobby.duration' | transloco }}</span>
            <input type="number" min="1" max="240" inputmode="numeric" [(ngModel)]="duration" />
          </label>
          <label class="field">
            <span class="lbl">{{ 'lobby.maxPlayers' | transloco }}</span>
            <input
              type="number"
              min="2"
              max="12"
              inputmode="numeric"
              [(ngModel)]="maxPlayers"
              (change)="applyConfig()"
            />
          </label>
          <label class="field">
            <span class="lbl">{{ 'lobby.maxScore' | transloco }}</span>
            <input
              type="number"
              min="1"
              inputmode="numeric"
              [placeholder]="'lobby.noLimit' | transloco"
              [(ngModel)]="maxScore"
              (change)="applyConfig()"
            />
          </label>
          <button class="btn danger" [disabled]="s.players.length < 2" (click)="start()">
            {{ 'lobby.start' | transloco }}
          </button>
          @if (s.players.length < 2) {
            <div class="foot">{{ 'lobby.minPlayers' | transloco }}</div>
          }
        </div>
      } @else {
        <div class="card center">
          <span class="eyebrow">{{ 'lobby.standby' | transloco }}</span>
          <p class="lead" style="margin: 8px 0 0">{{ 'lobby.waitingHost' | transloco }}</p>
        </div>
      }

      <!-- Custom mission pool — any player can contribute -->
      <div class="card">
        <h2>{{ 'lobby.missionsTitle' | transloco }}</h2>

        @if (isHost()) {
          <div class="lang" style="margin-bottom: 10px">
            <button
              type="button"
              class="lang-btn"
              [class.on]="missionMode === 'augment'"
              (click)="setMode('augment')"
            >
              {{ 'lobby.modeAugment' | transloco }}
            </button>
            <button
              type="button"
              class="lang-btn"
              [class.on]="missionMode === 'replace'"
              (click)="setMode('replace')"
            >
              {{ 'lobby.modeReplace' | transloco }}
            </button>
          </div>
        }

        <div class="mission-row">
          <input
            class="mission-edit"
            maxlength="200"
            [placeholder]="'lobby.poolPlaceholder' | transloco"
            [(ngModel)]="draft"
            (keyup.enter)="addToPool()"
          />
          <button class="btn ghost small" (click)="addToPool()">
            {{ 'lobby.addToPool' | transloco }}
          </button>
        </div>

        @if (s.mission_pool.length === 0) {
          <p class="foot" style="margin-top: 10px">{{ 'lobby.poolEmpty' | transloco }}</p>
        } @else {
          <ul class="mission-list">
            @for (m of s.mission_pool; track m.id) {
              <li class="mission-row">
                <span class="mission-edit">{{ m.text }}</span>
                @if (m.by === playerId() || isHost()) {
                  <button class="btn ghost small" (click)="removeFromPool(m.id)">
                    {{ 'lobby.removeMission' | transloco }}
                  </button>
                }
              </li>
            }
          </ul>
        }

        @if (lib.missions().length > 0) {
          <p class="foot" style="margin-top: 12px">{{ 'lobby.fromLibrary' | transloco }}</p>
          <ul class="mission-list">
            @for (m of lib.missions(); track m.id) {
              <li class="mission-row">
                <span class="mission-edit">{{ m.text }}</span>
                <button class="btn ghost small" (click)="addToPool(m.text)">
                  {{ 'lobby.addToPool' | transloco }}
                </button>
              </li>
            }
          </ul>
        }
      </div>

      <div class="card">
        <div class="foot">{{ 'lobby.rulesPlayers' | transloco: { count: s.max_players } }}</div>
        <div class="foot">
          @if (s.max_score) {
            {{ 'lobby.rulesGoalPoints' | transloco: { count: s.max_score } }}
          } @else {
            {{ 'lobby.rulesGoalTime' | transloco }}
          }
        </div>
      </div>
      <button class="btn ghost" (click)="leave()">{{ 'common.leave' | transloco }}</button>
    }
  `,
})
export class Lobby {
  private store = inject(GameStore);
  private session = inject(Session);
  private toast = inject(Toast);
  private i18n = inject(TranslocoService);
  protected readonly lib = inject(MissionLibrary);

  duration = 15;
  maxPlayers = 12;
  maxScore: number | null = null;
  missionMode: MissionMode = 'augment';
  draft = '';

  readonly state = this.store.state;
  readonly me = this.store.me;
  readonly isHost = this.store.isHost;
  readonly playerId = this.session.playerId;

  constructor() {
    // Seed the host inputs from the current game config so they reflect any prior setting.
    const s = this.store.state();
    if (s) {
      this.maxPlayers = s.max_players;
      this.maxScore = s.max_score;
      this.missionMode = s.mission_mode;
    }
  }

  setMode(mode: MissionMode): void {
    this.missionMode = mode;
    void this.applyConfig();
  }

  async applyConfig(): Promise<void> {
    const players = Math.max(2, Math.min(12, Number(this.maxPlayers) || 12));
    this.maxPlayers = players;
    const score = this.maxScore && this.maxScore >= 1 ? Math.floor(this.maxScore) : null;
    this.maxScore = score;
    try {
      await this.store.updateConfig(players, score, this.missionMode);
    } catch {
      this.toast.show(this.i18n.translate('lobby.configError'), 'bad');
    }
  }

  async addToPool(text = this.draft): Promise<void> {
    const value = text.trim();
    if (!value) return;
    try {
      await this.store.addMission(value);
      if (text === this.draft) this.draft = '';
    } catch {
      this.toast.show(this.i18n.translate('lobby.missionError'), 'bad');
    }
  }

  async removeFromPool(missionId: string): Promise<void> {
    try {
      await this.store.removeMission(missionId);
    } catch {
      this.toast.show(this.i18n.translate('lobby.missionError'), 'bad');
    }
  }

  start(): void {
    void this.store.start(Number(this.duration) || 15);
  }

  leave(): void {
    void this.store.leave();
  }
}
