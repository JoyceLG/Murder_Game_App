// Production: empty bases => same-origin relative URLs, proxied by nginx to the API.
// The Realtime service derives the ws(s):// scheme + host from window.location at runtime.
export const environment = {
  production: true,
  apiBase: '',
  wsBase: '',
};
