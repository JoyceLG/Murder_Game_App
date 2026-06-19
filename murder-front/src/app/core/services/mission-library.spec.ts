import { TestBed } from '@angular/core/testing';

import { MissionLibrary } from './mission-library';

describe('MissionLibrary', () => {
  let lib: MissionLibrary;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    lib = TestBed.inject(MissionLibrary);
  });

  it('starts empty', () => {
    expect(lib.missions()).toEqual([]);
  });

  it('adds a trimmed mission and persists it', () => {
    lib.add('  Fais rire ta cible  ');
    expect(lib.missions().length).toBe(1);
    expect(lib.missions()[0].text).toBe('Fais rire ta cible');

    const reloaded = new MissionLibrary();
    expect(reloaded.missions()[0].text).toBe('Fais rire ta cible');
  });

  it('ignores blank additions', () => {
    lib.add('   ');
    expect(lib.missions()).toEqual([]);
  });

  it('updates a mission by id', () => {
    lib.add('Ancienne');
    const id = lib.missions()[0].id;
    lib.update(id, 'Nouvelle');
    expect(lib.missions()[0].text).toBe('Nouvelle');
  });

  it('removes a mission by id', () => {
    lib.add('A');
    lib.add('B');
    const firstId = lib.missions()[0].id;
    lib.remove(firstId);
    expect(lib.missions().map((m) => m.text)).toEqual(['B']);
  });

  it('recovers from corrupt storage', () => {
    localStorage.setItem('murder.custom-missions', '{not json');
    const lib2 = new MissionLibrary();
    expect(lib2.missions()).toEqual([]);
  });
});
