import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Session } from '../services/session';

/** Bounce deep links to in-game routes back to home when there is no active session. */
export const inGameGuard: CanActivateFn = () => {
  const session = inject(Session);
  const router = inject(Router);
  return session.session() ? true : router.createUrlTree(['/home']);
};
