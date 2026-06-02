import { Injectable, signal } from '@angular/core';

export type ToastKind = 'good' | 'bad' | '';

export interface ToastMessage {
  text: string;
  kind: ToastKind;
}

/** Transient bottom toast (auto-dismiss after 2.2s), mirroring the legacy UI. */
@Injectable({ providedIn: 'root' })
export class Toast {
  readonly current = signal<ToastMessage | null>(null);
  private timer: ReturnType<typeof setTimeout> | null = null;

  show(text: string, kind: ToastKind = ''): void {
    this.current.set({ text, kind });
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.current.set(null), 2200);
  }
}
