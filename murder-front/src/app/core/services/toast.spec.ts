import { TestBed, fakeAsync, tick } from '@angular/core/testing';

import { Toast } from './toast';

describe('Toast', () => {
  it('shows a message then hides it after 2.2 s', fakeAsync(() => {
    const toast = TestBed.inject(Toast);
    toast.show('Hello', 'good');
    expect(toast.current()).toEqual({ text: 'Hello', kind: 'good' });
    tick(2199);
    expect(toast.current()).not.toBeNull();
    tick(1);
    expect(toast.current()).toBeNull();
  }));

  it('restarts the timer for a new message', fakeAsync(() => {
    const toast = TestBed.inject(Toast);
    toast.show('first');
    tick(2000);
    toast.show('second', 'bad');
    tick(2000);
    expect(toast.current()?.text).toBe('second');
    tick(200);
    expect(toast.current()).toBeNull();
  }));
});
