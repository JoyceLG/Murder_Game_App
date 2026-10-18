import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

import { missionTranslationKey } from '../../core/missions';

/**
 * Renders a mission in the viewer's language: catalogue keys are translated, custom missions
 * are shown exactly as typed (never fed to Transloco, which would treat them as keys).
 */
@Component({
  selector: 'app-mission-text',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { style: 'display: contents' },
  template: `@if (key(); as k) {
      {{ k | transloco }}
    } @else {
      {{ mission() }}
    }`,
})
export class MissionText {
  readonly mission = input<string | null | undefined>('');
  readonly key = computed(() => missionTranslationKey(this.mission()));
}
