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
  // One interpolation, no surrounding text nodes: the mission sits flush inside quotes.
  template: `{{ key() ? (key()! | transloco) : mission() }}`,
})
export class MissionText {
  readonly mission = input<string | null | undefined>('');
  readonly key = computed(() => missionTranslationKey(this.mission()));
}
