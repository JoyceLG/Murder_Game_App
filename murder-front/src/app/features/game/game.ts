import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { GameStore } from '../../core/services/game-store';
import { Session } from '../../core/services/session';
import { Dossier } from '../../shared/dossier/dossier';
import { Hud } from '../../shared/hud/hud';
import { IdLine } from '../../shared/id-line/id-line';
import { Roster } from '../../shared/roster/roster';

@Component({
  selector: 'app-game',
  imports: [IdLine, Hud, Dossier, Roster],
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
          <div class="card confirm">
            <span class="stamp">Tentative d'élimination</span>
            <p class="ctext">
              <b>{{ inc.atk_name }}</b> prétend t'avoir éliminé.<br />
              <span class="muted">« {{ inc.mission }} »</span>
            </p>
            <div class="btn-row">
              <button class="btn ghost" (click)="confirm(false)">Refuser</button>
              <button class="btn ok" (click)="confirm(true)">Confirmer</button>
            </div>
          </div>
        }

        @if (isPending()) {
          <div class="card">
            <div class="pending">
              <span class="pulse"></span> En attente de {{ target()?.name ?? 'ta cible' }}…
            </div>
          </div>
        } @else {
          <div class="card">
            <button class="btn danger" (click)="kill()">J'ai éliminé ma cible</button>
            <button class="btn ghost" (click)="swap()">
              Changer de mission&nbsp;&nbsp;<span class="muted">−1 pt</span>
            </button>
          </div>
        }

        <div class="card">
          <h2>Classement</h2>
          <app-roster
            [players]="ranking()"
            [withScore]="true"
            [meId]="playerId()"
            [hostId]="s.host_id"
          />
        </div>
        <button class="btn ghost" (click)="leave()">Quitter</button>
      }
    }
  `,
})
export class Game {
  private store = inject(GameStore);
  private session = inject(Session);

  readonly state = this.store.state;
  readonly me = this.store.me;
  readonly target = this.store.target;
  readonly remaining = this.store.remaining;
  readonly myRank = this.store.myRank;
  readonly incoming = this.store.incoming;
  readonly isPending = this.store.isPending;
  readonly ranking = this.store.ranking;
  readonly playerId = this.session.playerId;

  kill(): void {
    void this.store.claimKill();
  }

  swap(): void {
    void this.store.swap();
  }

  confirm(ok: boolean): void {
    void this.store.confirm(ok);
  }

  leave(): void {
    void this.store.leave();
  }
}
