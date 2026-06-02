import { Injectable } from '@angular/core';
import { Observable, retry } from 'rxjs';

import { environment } from '../../../environments/environment';
import { GameStateDto } from '../models/game.dto';

/** Live game-state stream over WebSocket. Each push is the full GameStateDto. */
@Injectable({ providedIn: 'root' })
export class Realtime {
  connect(code: string): Observable<GameStateDto> {
    const base = environment.wsBase || `${this.scheme()}//${location.host}`;
    const url = `${base}/games/${code}/live`;
    return new Observable<GameStateDto>((subscriber) => {
      const socket = new WebSocket(url);
      socket.onmessage = (event) => subscriber.next(JSON.parse(event.data) as GameStateDto);
      socket.onerror = () => subscriber.error(new Error('websocket error'));
      // Any close while subscribed is unexpected (the server keeps the socket open for the whole
      // game) -> surface it as an error so retry() reconnects. A `complete` would NOT retry.
      // On our own teardown we unsubscribe first, so this error is harmlessly ignored.
      socket.onclose = () => subscriber.error(new Error('websocket closed'));
      return () => {
        if (socket.readyState <= WebSocket.OPEN) socket.close();
      };
    }).pipe(retry({ delay: 1500 })); // auto-reconnect; the first push after reconnect is full state
  }

  private scheme(): string {
    return location.protocol === 'https:' ? 'wss:' : 'ws:';
  }
}
