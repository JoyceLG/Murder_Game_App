import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';

import { Lang, Language } from '../../core/services/language';
import { isCatalogueKey } from '../../core/missions';
import { MissionLibrary } from '../../core/services/mission-library';
import { Toast } from '../../core/services/toast';

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
            [attr.aria-pressed]="lang.current() === l"
            [attr.lang]="l"
            (click)="setLang(l)"
          >
            {{ 'settings.langName.' + l | transloco }}
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
              <input
                class="mission-edit"
                maxlength="120"
                [value]="m.text"
                [attr.aria-label]="'settings.missionLabel' | transloco"
                #ed
              />
              <button class="btn ghost small" (click)="save(m.id, ed.value)">
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
  private toast = inject(Toast);
  private i18n = inject(TranslocoService);

  draft = '';

  setLang(lang: Lang): void {
    this.lang.set(lang);
  }

  add(): void {
    if (this.refuseReserved(this.draft)) return;
    this.lib.add(this.draft);
    this.draft = '';
  }

  save(id: string, text: string): void {
    if (this.refuseReserved(text)) return;
    this.lib.update(id, text);
  }

  /** Custom missions may not look like catalogue keys (`core.NN`), which clients translate. */
  private refuseReserved(text: string): boolean {
    if (!isCatalogueKey(text)) return false;
    this.toast.show(this.i18n.translate('common.missionReserved'), 'bad');
    return true;
  }

  back(): void {
    void this.router.navigateByUrl('/home');
  }
}
