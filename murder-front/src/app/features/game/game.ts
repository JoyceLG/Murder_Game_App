import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';

import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';
import { Dossier } from '../../shared/dossier/dossier';
import { Hud } from '../../shared/hud/hud';
import { IdLine } from '../../shared/id-line/id-line';
import { Notice } from '../../shared/notice/notice';
import { Roster } from '../../shared/roster/roster';

type Confirming = 'swap' | 'end' | null;

@Component({
  selector: 'app-game',
  imports: [TranslocoPipe, IdLine, Hud, Dossier, Roster, Notice],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state(); as s) {
      @if (me(); as m) {
        <app-id-line [name]="m.name" [code]="s.code" />
        <app-hud [remaining]="remaining()" [score]="m.score" [rank]="myRank()" />
        <app-dossier
          [mission]="m.mission"
          [targetName]="target()?.name ?? '—'"
          [code]="s.code"
          [killNo]="m.score + 1"
        />

        @if (incoming(); as inc) {
          <div class="card confirm" role="alert">
            <span class="stamp">{{ 'game.attempt' | transloco }}</span>
            <p class="ctext">
              <b>{{ inc.atk_name }}</b> {{ 'game.claimedBy' | transloco }}<br />
              <span class="muted">{{
                'game.quotedMission' | transloco: { mission: inc.mission }
              }}</span>
            </p>
            <div class="btn-row">
              <button class="btn ghost" [disabled]="busy()" (click)="confirm(false)">
                {{ 'game.deny' | transloco }}
              </button>
              <button class="btn ok" [disabled]="busy()" (click)="confirm(true)">
                {{ 'game.confirm' | transloco }}
              </button>
            </div>
          </div>
        }

        @if (isPending()) {
          <div class="card">
            <div class="pending" role="status">
              <span class="pulse"></span>
              {{
                'game.waitingFor'
                  | transloco: { name: target()?.name ?? ('game.yourTarget' | transloco) }
              }}
            </div>
          </div>
        } @else if (confirming() === 'swap') {
          <div class="card">
            <p class="lead" style="margin-top: 0">{{ 'game.swapConfirm' | transloco }}</p>
            <div class="btn-row">
              <button class="btn ghost" (click)="confirming.set(null)">
                {{ 'common.cancel' | transloco }}
              </button>
              <button class="btn danger" [disabled]="busy()" (click)="swap()">
                {{ 'game.swapYes' | transloco }}
              </button>
            </div>
          </div>
        } @else {
          <div class="card">
            <button class="btn danger" [disabled]="busy()" (click)="kill()">
              {{ 'game.kill' | transloco }}
            </button>
            <button class="btn ghost" [disabled]="busy()" (click)="confirming.set('swap')">
              {{ 'game.swap' | transloco }}&nbsp;&nbsp;<span class="muted">{{
                'game.swapCost' | transloco
              }}</span>
            </button>
          </div>
        }

        <div class="card">
          <h2>{{ 'game.ranking' | transloco }}</h2>
          <app-roster [players]="ranking()" [withScore]="true" [meId]="m.id" [hostId]="s.host_id" />
        </div>

        @if (isHost()) {
          @if (confirming() === 'end') {
            <div class="card">
              <p class="lead" style="margin-top: 0">{{ 'game.endConfirm' | transloco }}</p>
              <div class="btn-row">
                <button class="btn ghost" (click)="confirming.set(null)">
                  {{ 'common.cancel' | transloco }}
                </button>
                <button class="btn danger" [disabled]="busy()" (click)="end()">
                  {{ 'game.endYes' | transloco }}
                </button>
              </div>
            </div>
          } @else {
            <button class="btn ghost" [disabled]="busy()" (click)="confirming.set('end')">
              {{ 'game.endGame' | transloco }}
            </button>
          }
        }
        <button class="btn ghost" [disabled]="busy()" (click)="leave()">
          {{ 'common.leave' | transloco }}
        </button>
      } @else {
        <app-notice messageKey="common.notInGame" [withHome]="true" (home)="exit()" />
      }
    } @else {
      <app-notice messageKey="app.restoring" />
    }
  `,
})
export class Game {
  private store = inject(GameStore);
  private toast = inject(Toast);
  private i18n = inject(TranslocoService);

  readonly state = this.store.state;
  readonly me = this.store.me;
  readonly target = this.store.target;
  readonly remaining = this.store.remaining;
  readonly myRank = this.store.myRank;
  readonly incoming = this.store.incoming;
  readonly isPending = this.store.isPending;
  readonly isHost = this.store.isHost;
  readonly ranking = this.store.ranking;

  /** One action at a time: a double tap must not swap twice (2 points) or claim twice (409). */
  readonly busy = signal(false);
  readonly confirming = signal<Confirming>(null);

  kill(): Promise<void> {
    return this.run(() => this.store.claimKill(), 'game.claimFailed');
  }

  swap(): Promise<void> {
    return this.run(() => this.store.swap());
  }

  confirm(ok: boolean): Promise<void> {
    return this.run(() => this.store.confirm(ok));
  }

  end(): Promise<void> {
    return this.run(() => this.store.end());
  }

  leave(): Promise<void> {
    return this.run(() => this.store.leave());
  }

  exit(): void {
    this.store.exit();
  }

  private async run(action: () => Promise<unknown>, errorKey = 'common.actionFailed') {
    if (this.busy()) return;
    this.busy.set(true);
    try {
      await action();
      this.confirming.set(null);
    } catch {
      this.toast.show(this.i18n.translate(errorKey), 'bad');
    } finally {
      this.busy.set(false);
    }
  }
}
