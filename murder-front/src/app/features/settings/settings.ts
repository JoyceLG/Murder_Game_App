import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';

import { Lang, Language } from '../../core/services/language';
import { MissionLibrary } from '../../core/services/mission-library';

@Component({
  selector: 'app-settings',
  imports: [FormsModule, TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card">
      <h2>{{ 'settings.language' | transloco }}</h2>
      <div class="lang">
        @for (l of lang.supported; track l) {
          <button
            type="button"
            class="lang-btn"
            [class.on]="lang.current() === l"
            (click)="setLang(l)"
          >
            {{ l }}
          </button>
        }
      </div>
    </div>

    <div class="card">
      <h2>{{ 'settings.missionsTitle' | transloco }}</h2>
      <p class="foot">{{ 'settings.missionsHint' | transloco }}</p>

      <label class="field">
        <span class="lbl">{{ 'settings.newMission' | transloco }}</span>
        <input
          maxlength="120"
          [placeholder]="'settings.newPlaceholder' | transloco"
          [(ngModel)]="draft"
          (keyup.enter)="add()"
        />
      </label>
      <button class="btn primary" (click)="add()">{{ 'settings.add' | transloco }}</button>

      @if (lib.missions().length === 0) {
        <p class="foot" style="margin-top: 12px">{{ 'settings.empty' | transloco }}</p>
      } @else {
        <ul class="mission-list">
          @for (m of lib.missions(); track m.id) {
            <li class="mission-row">
              <input class="mission-edit" maxlength="120" [value]="m.text" #ed />
              <button class="btn ghost small" (click)="lib.update(m.id, ed.value)">
                {{ 'settings.save' | transloco }}
              </button>
              <button class="btn ghost small" (click)="lib.remove(m.id)">
                {{ 'settings.delete' | transloco }}
              </button>
            </li>
          }
        </ul>
      }
    </div>

    <button class="btn ghost" (click)="back()">{{ 'settings.back' | transloco }}</button>
  `,
})
export class Settings {
  protected readonly lang = inject(Language);
  protected readonly lib = inject(MissionLibrary);
  private router = inject(Router);

  draft = '';

  setLang(lang: Lang): void {
    this.lang.set(lang);
  }

  add(): void {
    this.lib.add(this.draft);
    this.draft = '';
  }

  back(): void {
    void this.router.navigateByUrl('/home');
  }
}
