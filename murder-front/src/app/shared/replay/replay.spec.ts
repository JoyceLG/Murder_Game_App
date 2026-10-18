import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Replay, ReplayPicker, scoreTrend } from './replay';

@Component({
  imports: [Replay],
  template: `<div [appReplay]="value()" [replayClass]="cls()"></div>`,
})
class Host {
  readonly value = signal<unknown>(1);
  readonly cls = signal<string | ReplayPicker>('anim-x');
}

describe('Replay', () => {
  let fixture: ComponentFixture<Host>;
  const el = () => (fixture.nativeElement as HTMLElement).querySelector('div')!;
  const set = (value: unknown) => {
    fixture.componentInstance.value.set(value);
    fixture.detectChanges();
  };

  beforeEach(() => {
    fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
  });

  it('stays still on first render', () => {
    expect(el().className).toBe('');
  });

  it('plays the class when the value changes', () => {
    set(2);
    expect(el().classList).toContain('anim-x');
  });

  it('does nothing when the value is unchanged', () => {
    set(1);
    expect(el().className).toBe('');
  });

  it('uses a picker to choose the animation, and swaps classes between plays', () => {
    fixture.componentInstance.cls.set(scoreTrend);
    fixture.detectChanges();
    set(3);
    expect(el().className).toBe('anim-bump');
    set(2);
    expect(el().className).toBe('anim-dip'); // previous class removed
  });

  it('a picker may decide not to animate', () => {
    fixture.componentInstance.cls.set(() => null);
    fixture.detectChanges();
    set(5);
    expect(el().className).toBe('');
  });
});

describe('scoreTrend', () => {
  it('bumps up, dips down, ignores no change', () => {
    expect(scoreTrend(1, 2)).toBe('anim-bump');
    expect(scoreTrend(2, 1)).toBe('anim-dip');
    expect(scoreTrend(2, 2)).toBeNull();
  });
});
