import { Routes } from '@angular/router';

import { inGameGuard } from './core/guards/in-game-guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'home' },
  { path: 'home', loadComponent: () => import('./features/home/home').then((m) => m.Home) },
  {
    path: 'g/:code',
    canActivate: [inGameGuard],
    loadComponent: () => import('./features/lobby/lobby').then((m) => m.Lobby),
  },
  {
    path: 'g/:code/play',
    canActivate: [inGameGuard],
    loadComponent: () => import('./features/game/game').then((m) => m.Game),
  },
  {
    path: 'g/:code/end',
    canActivate: [inGameGuard],
    loadComponent: () => import('./features/end/end').then((m) => m.End),
  },
  { path: 'gone', loadComponent: () => import('./features/gone/gone').then((m) => m.Gone) },
  { path: '**', redirectTo: 'home' },
];
