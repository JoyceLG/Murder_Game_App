import {
  Directive,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  inject,
  input,
  untracked,
} from '@angular/core';

/** Picks the animation for a change from `prev` to `next`, or null for none. */
export type ReplayPicker = (prev: unknown, next: unknown) => string | null;

/**
 * Replays a CSS animation class each time a value changes — not on first render, so opening a
 * screen stays calm. The animation itself lives in SCSS (`styles/_motion.scss`), where the global
 * `prefers-reduced-motion` rule switches it off.
 *
 *   <div class="dossier" [appReplay]="dealKey()" replayClass="anim-deal">
 *   <span [appReplay]="score()" [replayClass]="trend">   (trend: ReplayPicker)
 */
@Directive({ selector: '[appReplay]' })
export class Replay {
  readonly appReplay = input.required<unknown>();
  readonly replayClass = input.required<string | ReplayPicker>();

  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly injector = inject(Injector);
  private applied: string | null = null;

  constructor() {
    let first = true;
    let prev: unknown;
    effect(() => {
      const next = this.appReplay(); // the only tracked read
      untracked(() => {
        if (first) {
          first = false;
        } else if (!Object.is(prev, next)) {
          const pick = this.replayClass();
          const cls = typeof pick === 'function' ? pick(prev, next) : pick;
          // After the view is rendered (new text in place): one layout, not two.
          afterNextRender({ write: () => this.play(cls) }, { injector: this.injector });
        }
        prev = next;
      });
    });
  }

  private play(cls: string | null): void {
    if (this.applied) this.el.classList.remove(this.applied);
    this.applied = cls;
    if (!cls) return;
    void this.el.offsetWidth; // restart the animation even if the same class comes back
    this.el.classList.add(cls);
  }
}

/** Score went up: bump; down: dip; unchanged: nothing. */
export const scoreTrend: ReplayPicker = (prev, next) =>
  Number(next) > Number(prev) ? 'anim-bump' : Number(next) < Number(prev) ? 'anim-dip' : null;
